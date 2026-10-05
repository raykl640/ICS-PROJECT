"""Account rules with an injected clock: lockout, auto-lock, restart, recovery, password change, profile, delete."""

from pathlib import Path

import pytest

from backend.app.accounts.auth import AuthSessions, token_hash
from backend.app.accounts.db import Database
from backend.app.accounts.service import AccountError, Accounts, Prefs
from backend.app.config import Settings

PW = "a long enough password"


class Clock:
    """Epoch seconds, advanced by hand."""

    def __init__(self) -> None:
        self.now = 1_800_000_000.0

    def __call__(self) -> float:
        return self.now


def make(tmp_path: Path, clock: Clock, **overrides: object) -> Accounts:
    settings = Settings(app_db_path=tmp_path / "app.db", **overrides)  # type: ignore[arg-type]
    return Accounts(settings, Database(settings.app_db_path), AuthSessions(clock), clock)


def code_of(error: pytest.ExceptionInfo[AccountError]) -> str:
    return error.value.code


def test_register_validates_and_rejects_duplicates(tmp_path: Path) -> None:
    accounts = make(tmp_path, Clock())
    with pytest.raises(AccountError) as bad_name:
        accounts.register("x!", PW, "")
    assert code_of(bad_name) == "invalid_username"
    with pytest.raises(AccountError) as weak:
        accounts.register("wanjiku", "short", "")
    assert code_of(weak) == "weak_password"
    signed = accounts.register("  Wanjiku ", PW, "  Wanjiku\x00 K. ")
    assert signed.user.username == "wanjiku"
    assert signed.user.display_name == "Wanjiku K."
    assert signed.recovery_code
    with pytest.raises(AccountError) as taken:
        accounts.register("WANJIKU", PW, "")
    assert taken.value.status == 409


def test_login_is_generic_for_unknown_users_and_wrong_passwords(tmp_path: Path) -> None:
    accounts = make(tmp_path, Clock())
    accounts.register("amina", PW, "Amina")
    with pytest.raises(AccountError) as unknown:
        accounts.login("nobody", PW)
    with pytest.raises(AccountError) as wrong:
        accounts.login("amina", "a wrong password!!")
    assert (unknown.value.code, unknown.value.message) == (wrong.value.code, wrong.value.message)
    assert accounts.login("AMINA", PW).user.username == "amina"


def test_lockout_grows_exponentially_and_clears_after_success(tmp_path: Path) -> None:
    clock = Clock()
    accounts = make(tmp_path, clock, login_max_attempts=3, login_lockout_s=30)
    accounts.register("otieno", PW, "")
    for _ in range(3):
        with pytest.raises(AccountError):
            accounts.login("otieno", "wrong password here")
    with pytest.raises(AccountError) as locked:
        accounts.login("otieno", PW)  # even the right password waits
    assert (locked.value.code, locked.value.retry_after) == ("locked_out", 30)
    clock.now += 30
    with pytest.raises(AccountError):
        accounts.login("otieno", "wrong again, again")  # 4th failure: 60 s
    with pytest.raises(AccountError) as longer:
        accounts.login("otieno", PW)
    assert longer.value.retry_after == 60
    clock.now += 60
    accounts.login("otieno", PW)
    for _ in range(2):  # counter was reset by the success
        with pytest.raises(AccountError) as again:
            accounts.login("otieno", "wrong password here")
        assert again.value.code == "invalid_credentials"


def test_lockout_is_capped(tmp_path: Path) -> None:
    clock = Clock()
    accounts = make(tmp_path, clock, login_max_attempts=1, login_lockout_s=30, login_lockout_max_s=50)
    accounts.register("kip", PW, "")
    for _ in range(4):
        with pytest.raises(AccountError):
            accounts.login("kip", "wrong password here")
        clock.now += 60
    with pytest.raises(AccountError):
        accounts.login("kip", "wrong password here")
    with pytest.raises(AccountError) as capped:
        accounts.login("kip", PW)
    assert capped.value.retry_after == 50


def test_idle_auto_lock_drops_the_key_and_unlock_restores_it(tmp_path: Path) -> None:
    clock = Clock()
    accounts = make(tmp_path, clock, auto_lock_s=600)
    signed = accounts.register("njeri", PW, "")
    session = accounts.session(signed.token)
    assert session is not None and session.dek is not None
    assert accounts.sessions.lock_in(session) == 600
    clock.now += 599
    accounts.sessions.touch(session)
    clock.now += 599
    assert accounts.session(signed.token).dek is not None  # type: ignore[union-attr]
    clock.now += 2
    locked = accounts.session(signed.token)
    assert locked is not None and locked.locked
    with pytest.raises(AccountError):
        accounts.unlock(locked, "not the password!")
    accounts.unlock(locked, PW)
    assert not locked.locked


def test_prefs_change_auto_lock_of_live_sessions(tmp_path: Path) -> None:
    clock = Clock()
    accounts = make(tmp_path, clock)
    signed = accounts.register("baraka", PW, "")
    session = accounts.session(signed.token)
    assert session is not None
    assert accounts.prefs(session) == Prefs(True, 15)
    accounts.save_prefs(session, Prefs(False, 1))
    assert accounts.prefs(session) == Prefs(False, 1)
    clock.now += 61
    assert accounts.session(signed.token).locked  # type: ignore[union-attr]
    with pytest.raises(AccountError):
        accounts.save_prefs(session, Prefs(True, 0))


def test_restart_keeps_the_sign_in_but_requires_unlock(tmp_path: Path) -> None:
    clock = Clock()
    first = make(tmp_path, clock)
    signed = first.register("halima", PW, "")
    second = make(tmp_path, clock)  # new process: empty memory, same database
    restored = second.session(signed.token)
    assert restored is not None and restored.locked and restored.user_id == signed.user.id
    assert second.unlock(restored, PW).username == "halima"
    assert second.session("not-a-token") is None
    clock.now += second.settings.auth_session_ttl_s
    assert make(tmp_path, clock).session(signed.token) is None


def test_logout_forgets_the_token_everywhere(tmp_path: Path) -> None:
    clock = Clock()
    accounts = make(tmp_path, clock)
    signed = accounts.register("juma", PW, "")
    session = accounts.session(signed.token)
    assert session is not None
    accounts.logout(session)
    assert accounts.session(signed.token) is None
    assert make(tmp_path, clock).session(signed.token) is None


def test_recovery_resets_password_old_password_and_code_stop_working(tmp_path: Path) -> None:
    clock = Clock()
    accounts = make(tmp_path, clock)
    signed = accounts.register("mwangi", PW, "")
    session = accounts.session(signed.token)
    assert session is not None and session.dek is not None
    accounts.save_profile(session, session.dek, {"name": "Mwangi Kariuki"})
    assert signed.recovery_code is not None
    with pytest.raises(AccountError) as wrong_code:
        accounts.recover("mwangi", "AAAA-BBBB-CCCC-DDDD-EEEE", "a brand new password")
    assert wrong_code.value.code == "invalid_credentials"
    recovered = accounts.recover("mwangi", signed.recovery_code.lower().replace("-", " "), "a brand new password")
    assert recovered.recovery_code and recovered.recovery_code != signed.recovery_code
    assert accounts.session(signed.token) is None  # old sign-ins ended
    with pytest.raises(AccountError):
        accounts.login("mwangi", PW)
    clock.now += 3600
    fresh = accounts.login("mwangi", "a brand new password")
    new_session = accounts.session(fresh.token)
    assert new_session is not None and new_session.dek is not None
    assert accounts.profile(new_session, new_session.dek)["name"] == "Mwangi Kariuki"  # same data key
    with pytest.raises(AccountError):
        accounts.recover("mwangi", signed.recovery_code, "yet another password")


def test_password_change_rewraps_and_ends_other_sign_ins(tmp_path: Path) -> None:
    accounts = make(tmp_path, Clock())
    signed = accounts.register("akinyi", PW, "")
    other = accounts.login("akinyi", PW)
    session = accounts.session(signed.token)
    assert session is not None and session.dek is not None
    accounts.save_profile(session, session.dek, {"phone": "0700 000 000"})
    with pytest.raises(AccountError):
        accounts.change_password(session, "wrong current pw", "a different password")
    accounts.change_password(session, PW, "a different password")
    assert accounts.session(other.token) is None
    assert accounts.session(signed.token) is not None
    again = accounts.login("akinyi", "a different password")
    s2 = accounts.session(again.token)
    assert s2 is not None and s2.dek is not None
    assert accounts.profile(s2, s2.dek)["phone"] == "0700 000 000"
    assert signed.recovery_code is not None
    accounts.recover("akinyi", signed.recovery_code, "recovered password")  # the recovery code still works


def test_profile_is_cleaned_capped_and_exported(tmp_path: Path) -> None:
    accounts = make(tmp_path, Clock(), profile_field_max_chars=10)
    signed = accounts.register("chebet", PW, "Chebet")
    session = accounts.session(signed.token)
    assert session is not None and session.dek is not None
    assert accounts.profile(session, session.dek) == dict.fromkeys(
        ("name", "address", "phone", "email", "id_number"), ""
    )
    saved = accounts.save_profile(session, session.dek, {"name": "Chebet​   Rono Kiprotich", "unknown": "x"})
    assert saved["name"] == "Chebet Ron"
    exported = accounts.export(session, session.dek)
    assert exported["profile"]["name"] == "Chebet Ron"
    assert exported["user"]["username"] == "chebet"
    assert "pw_hash" not in str(exported)


def test_delete_needs_the_password_and_removes_everything(tmp_path: Path) -> None:
    accounts = make(tmp_path, Clock())
    signed = accounts.register("wairimu", PW, "")
    session = accounts.session(signed.token)
    assert session is not None
    with pytest.raises(AccountError):
        accounts.delete(session, "not my password!")
    accounts.delete(session, PW)
    assert accounts.session(signed.token) is None
    with pytest.raises(AccountError):
        accounts.login("wairimu", PW)
    with accounts.db.read() as conn:
        assert conn.execute("SELECT count(*) FROM users").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM auth_tokens").fetchone()[0] == 0


def test_purge_drops_expired_sign_ins(tmp_path: Path) -> None:
    clock = Clock()
    accounts = make(tmp_path, clock, auth_session_ttl_s=100)
    signed = accounts.register("kamau", PW, "")
    clock.now += 101
    assert accounts.purge() == 1
    assert len(accounts.sessions) == 0
    with accounts.db.read() as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM auth_tokens WHERE token_hash = ?", (token_hash(signed.token),)
            ).fetchone()[0]
            == 0
        )
