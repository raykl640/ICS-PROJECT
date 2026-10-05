"""/api/auth and /api/account over the app: cookies, guards, lock/unlock, restart, no plaintext at rest, clean logs."""

from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.tests.api_support import APP_HEADERS, FakeClock, captured_logs
from backend.tests.fakes import FakeLLM

PW = "a long enough password"
MARKER = "Zawadi-Plaintext-Marker-7731"


class Wall:
    """Epoch-seconds clock advanced by hand."""

    def __init__(self) -> None:
        self.now = 1_800_000_000.0

    def __call__(self) -> float:
        return self.now


def app_at(tmp_path: Path, wall: Wall | None = None, **overrides: Any) -> FastAPI:
    from backend.app.devstack import fake_deps
    from backend.app.main import create_app
    from backend.tests.api_support import api_settings

    settings = api_settings(tmp_path, app_db_path=tmp_path / "app.db", **overrides)
    return create_app(
        fake_deps(settings, tmp_path / "work", llm=FakeLLM()), clock=FakeClock(), wall_clock=wall or Wall()
    )


def client(app: FastAPI, **kwargs: Any) -> TestClient:
    return TestClient(app, raise_server_exceptions=False, headers=APP_HEADERS, **kwargs)


def register(c: TestClient, username: str = "wanjiku", display_name: str = "Wanjiku") -> dict[str, Any]:
    r = c.post("/api/auth/register", json={"username": username, "password": PW, "display_name": display_name})
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


def error_code(r: Any) -> str:
    code: str = r.json()["error"]["code"]
    return code


def test_register_sets_a_strict_http_only_api_cookie_and_returns_the_code_once(tmp_path: Path) -> None:
    with client(app_at(tmp_path)) as c:
        assert c.get("/api/auth/me").json() == {"user": None, "locked": False, "lock_in_s": 0}
        r = c.post("/api/auth/register", json={"username": "Wanjiku", "password": PW, "display_name": "Wanjiku K"})
        assert r.status_code == 200
        cookie = r.headers["set-cookie"]
        for part in ("haki_auth=", "HttpOnly", "Path=/api", "SameSite=strict", "Max-Age=43200"):
            assert part.lower() in cookie.lower()
        assert "secure" not in cookie.lower()  # plain http on localhost
        body = r.json()
        assert body["user"]["username"] == "wanjiku" and len(body["recovery_code"]) == 24
        me = c.get("/api/auth/me").json()
        assert me["user"]["display_name"] == "Wanjiku K" and me["locked"] is False and me["lock_in_s"] == 900
        assert "recovery_code" not in str(c.get("/api/auth/me").json())
        assert (
            error_code(c.post("/api/auth/register", json={"username": "wanjiku", "password": PW})) == "username_taken"
        )


def test_cookie_is_secure_over_https(tmp_path: Path) -> None:
    with client(app_at(tmp_path), base_url="https://localhost") as c:
        r = c.post("/api/auth/register", json={"username": "amina", "password": PW})
        assert "secure" in r.headers["set-cookie"].lower()


def test_guards_bad_host_and_missing_header(tmp_path: Path) -> None:
    app = app_at(tmp_path)
    with TestClient(app, raise_server_exceptions=False) as plain:
        r = plain.post("/api/auth/register", json={"username": "amina", "password": PW})
        assert (r.status_code, error_code(r)) == (403, "missing_header")
        assert plain.get("/api/auth/me").status_code == 200  # reads need no header
    with TestClient(app, raise_server_exceptions=False, base_url="http://evil.example:8000") as rebinding:
        r = rebinding.get("/api/health")
        assert (r.status_code, error_code(r)) == (400, "bad_host")
        assert r.headers["content-security-policy"]  # hardening headers still applied


def test_login_errors_are_generic_and_lockout_sends_retry_after(tmp_path: Path) -> None:
    wall = Wall()
    with client(app_at(tmp_path, wall, login_max_attempts=2)) as c:
        register(c)
        c.post("/api/auth/logout")
        unknown = c.post("/api/auth/login", json={"username": "nobody", "password": PW})
        wrong = c.post("/api/auth/login", json={"username": "wanjiku", "password": "the wrong password"})
        assert unknown.status_code == wrong.status_code == 401
        assert unknown.json() == wrong.json()
        c.post("/api/auth/login", json={"username": "wanjiku", "password": "the wrong password"})
        locked = c.post("/api/auth/login", json={"username": "wanjiku", "password": PW})
        assert (locked.status_code, error_code(locked), locked.headers["retry-after"]) == (429, "locked_out", "30")
        wall.now += 30
        assert c.post("/api/auth/login", json={"username": "wanjiku", "password": PW}).status_code == 200


def test_validation_errors_do_not_echo_the_password(tmp_path: Path) -> None:
    with client(app_at(tmp_path)) as c:
        r = c.post("/api/auth/register", json={"username": "amina", "password": "x" * 300})
        assert r.status_code == 422 and "xxxx" not in r.text
        r = c.post("/api/auth/register", json={"username": "amina", "password": PW, "extra": 1})
        assert r.status_code == 422


def test_lock_unlock_and_locked_content_is_423(tmp_path: Path) -> None:
    with client(app_at(tmp_path)) as c:
        assert error_code(c.get("/api/account/profile")) == "auth_required"
        register(c)
        assert c.put("/api/account/profile", json={"name": "Wanjiku"}).status_code == 200
        assert c.post("/api/auth/lock").json()["locked"] is True
        r = c.get("/api/account/profile")
        assert (r.status_code, error_code(r)) == (423, "locked")
        assert c.post("/api/auth/unlock", json={"password": "the wrong password"}).status_code == 401
        assert c.post("/api/auth/unlock", json={"password": PW}).status_code == 200
        assert c.get("/api/account/profile").json()["name"] == "Wanjiku"


def test_idle_auto_lock_and_activity_ping(tmp_path: Path) -> None:
    wall = Wall()
    with client(app_at(tmp_path, wall)) as c:
        register(c)
        c.put("/api/account/prefs", json={"save_history": True, "auto_lock_minutes": 2})
        wall.now += 100
        assert c.get("/api/auth/me").json()["lock_in_s"] == 20
        assert c.get("/api/auth/me", params={"active": "true"}).json()["lock_in_s"] == 120
        wall.now += 121
        me = c.get("/api/auth/me").json()
        assert me["locked"] is True and me["user"]["username"] == "wanjiku"
        assert c.get("/api/account/prefs").status_code == 423


def test_restart_requires_unlock(tmp_path: Path) -> None:
    wall = Wall()
    with client(app_at(tmp_path, wall)) as c:
        register(c)
        c.put("/api/account/profile", json={"name": "Before restart"})
        cookies = dict(c.cookies)
    with client(app_at(tmp_path, wall), cookies=cookies) as restarted:
        me = restarted.get("/api/auth/me").json()
        assert me["user"]["username"] == "wanjiku" and me["locked"] is True
        assert restarted.get("/api/account/profile").status_code == 423
        restarted.post("/api/auth/unlock", json={"password": PW})
        assert restarted.get("/api/account/profile").json()["name"] == "Before restart"


def test_logout_clears_the_cookie(tmp_path: Path) -> None:
    with client(app_at(tmp_path)) as c:
        register(c)
        r = c.post("/api/auth/logout")
        assert 'haki_auth=""' in r.headers["set-cookie"] or "max-age=0" in r.headers["set-cookie"].lower()
        assert c.get("/api/auth/me").json()["user"] is None
        assert c.post("/api/auth/logout").status_code == 200  # idempotent


def test_recover_and_password_change_over_http(tmp_path: Path) -> None:
    with client(app_at(tmp_path)) as c:
        code = register(c)["recovery_code"]
        changed = c.post("/api/auth/password", json={"current_password": PW, "new_password": "second password!"})
        assert changed.status_code == 200
        c.post("/api/auth/logout")
        r = c.post(
            "/api/auth/recover", json={"username": "wanjiku", "recovery_code": code, "new_password": "third password!!"}
        )
        assert r.status_code == 200 and r.json()["recovery_code"] != code
        c.post("/api/auth/logout")
        assert (
            c.post("/api/auth/login", json={"username": "wanjiku", "password": "second password!"}).status_code == 401
        )
        assert (
            c.post("/api/auth/login", json={"username": "wanjiku", "password": "third password!!"}).status_code == 200
        )


def test_prefs_validation_and_export_download(tmp_path: Path) -> None:
    with client(app_at(tmp_path)) as c:
        register(c)
        assert c.get("/api/account/prefs").json() == {"save_history": True, "auto_lock_minutes": 15}
        assert (
            error_code(c.put("/api/account/prefs", json={"save_history": True, "auto_lock_minutes": 999}))
            == "invalid_prefs"
        )
        assert (
            c.put("/api/account/prefs", json={"save_history": False, "auto_lock_minutes": 30}).json()["save_history"]
            is False
        )
        c.put("/api/account/profile", json={"email": "w@example.org"})
        r = c.get("/api/account/export")
        assert r.headers["content-disposition"].startswith("attachment")
        assert r.headers["cache-control"] == "no-store"
        data = r.json()
        assert data["profile"]["email"] == "w@example.org" and data["prefs"]["auto_lock_minutes"] == 30


def _db_bytes(tmp_path: Path) -> bytes:
    return b"".join(p.read_bytes() for p in tmp_path.glob("app.db*"))


def test_no_plaintext_at_rest_and_no_identity_in_logs(tmp_path: Path) -> None:
    with captured_logs() as logs, client(app_at(tmp_path)) as c:
        register(c, username="mlinzi", display_name="Display")
        profile = {
            "name": MARKER,
            "address": f"{MARKER} street",
            "phone": "0711 222 333",
            "email": "m@x.org",
            "id_number": "12345678",
        }
        assert c.put("/api/account/profile", json=profile).status_code == 200
        c.post("/api/auth/lock")
        c.post("/api/auth/unlock", json={"password": PW})
        assert c.get("/api/account/profile").json()["name"] == MARKER
        stored = _db_bytes(tmp_path)
        assert stored  # file and WAL exist
        for secret in (MARKER, "0711 222 333", "12345678", PW):
            assert secret.encode() not in stored
            assert secret.encode("utf-16-le") not in stored
        text = logs.getvalue()
        assert text  # sign-up was logged
        for secret in (MARKER, PW, "mlinzi", "Display"):
            assert secret not in text


def test_delete_account_removes_rows_and_compacts(tmp_path: Path) -> None:
    with client(app_at(tmp_path)) as c:
        register(c, username="tobedeleted")
        c.put("/api/account/profile", json={"name": "Someone"})
        assert c.request("DELETE", "/api/account", json={"password": "the wrong password"}).status_code == 401
        r = c.request("DELETE", "/api/account", json={"password": PW})
        assert r.status_code == 200 and r.json()["user"] is None
        assert c.get("/api/auth/me").json()["user"] is None
        assert b"tobedeleted" not in _db_bytes(tmp_path)
        assert c.post("/api/auth/login", json={"username": "tobedeleted", "password": PW}).status_code == 401


def test_auth_endpoints_are_rate_limited_per_ip(tmp_path: Path) -> None:
    with client(app_at(tmp_path, auth_rate_limit_per_min=2)) as c:
        for _ in range(2):
            c.post("/api/auth/login", json={"username": "nobody", "password": PW})
        r = c.post("/api/auth/login", json={"username": "nobody", "password": PW})
        assert (r.status_code, error_code(r)) == (429, "rate_limited") and r.headers["retry-after"]


@pytest.mark.parametrize("path", ["/api/auth/lock", "/api/auth/password"])
def test_session_endpoints_need_sign_in(tmp_path: Path, path: str) -> None:
    with client(app_at(tmp_path)) as c:
        r = c.post(path, json={"current_password": PW, "new_password": PW})
        assert (r.status_code, error_code(r)) == (401, "auth_required")


def test_accounts_not_ready_before_startup(tmp_path: Path) -> None:
    c = client(app_at(tmp_path))  # no lifespan
    r = c.get("/api/account/prefs")
    assert (r.status_code, error_code(r)) == (503, "not_ready")


@pytest.mark.parametrize(
    ("header", "host"),
    [
        ("LocalHost:8000", "localhost"),
        ("[::1]:8000", "[::1]"),
        ("[::1]", "[::1]"),
        ("127.0.0.1", "127.0.0.1"),
        ("", ""),
    ],
)
def test_host_name_strips_the_port(header: str, host: str) -> None:
    from backend.app.web import host_name

    assert host_name(header) == host
