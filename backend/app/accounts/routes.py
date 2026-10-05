"""/api/auth and /api/account (DESIGN_V2 "API v2"). Session cookie haki_auth: HttpOnly, SameSite=Strict, Path=/api,
Secure over https. Every response here is no-store (SecurityHeadersMiddleware) and errors use the uniform schema."""

import json
import logging
from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from backend.app.accounts.auth import AuthSession
from backend.app.accounts.service import PROFILE_FIELDS, AccountError, Accounts, Prefs, SignedIn, UserView
from backend.app.security import RateLimiter

COOKIE = "haki_auth"
log = logging.getLogger("hakiai.accounts")

auth = APIRouter(prefix="/api/auth")
account = APIRouter(prefix="/api/account")


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegisterIn(_Body):
    """Sign-up form."""

    username: str = Field(max_length=200)
    password: str = Field(max_length=256)
    display_name: str = Field("", max_length=200)


class LoginIn(_Body):
    """Sign-in form."""

    username: str = Field(max_length=200)
    password: str = Field(max_length=256)


class PasswordIn(_Body):
    """Unlock or delete confirmation."""

    password: str = Field(max_length=256)


class RecoverIn(_Body):
    """Password reset with the recovery code."""

    username: str = Field(max_length=200)
    recovery_code: str = Field(max_length=64)
    new_password: str = Field(max_length=256)


class ChangePasswordIn(_Body):
    """Password change while unlocked."""

    current_password: str = Field(max_length=256)
    new_password: str = Field(max_length=256)


class ProfileIn(_Body):
    """Letter profile (every field optional text)."""

    name: str = Field("", max_length=1000)
    address: str = Field("", max_length=1000)
    phone: str = Field("", max_length=1000)
    email: str = Field("", max_length=1000)
    id_number: str = Field("", max_length=1000)


class PrefsIn(_Body):
    """Preferences."""

    save_history: bool
    auto_lock_minutes: int


class UserOut(BaseModel):
    """The user as the client sees it."""

    id: str
    username: str
    display_name: str


class AuthOut(BaseModel):
    """After register/login/recover/unlock: the user and, once, the recovery code."""

    user: UserOut
    recovery_code: str | None = None


class MeOut(BaseModel):
    """GET /api/auth/me: never 404; user is null for guests."""

    user: UserOut | None
    locked: bool
    lock_in_s: int


def _accounts(request: Request) -> Accounts:
    accounts: Accounts | None = getattr(request.app.state, "accounts", None)
    if accounts is None:
        raise AccountError(503, "not_ready", "The service is still starting. Please try again shortly.")
    return accounts


def _limiter(request: Request) -> RateLimiter:
    limiter: RateLimiter = request.app.state.auth_limiter
    return limiter


AccountsDep = Annotated[Accounts, Depends(_accounts)]


def current_session(request: Request, accounts: AccountsDep) -> AuthSession | None:
    """The caller's sign-in, if any (locked or not)."""
    return accounts.session(request.cookies.get(COOKIE))


def require_session(session: Annotated[AuthSession | None, Depends(current_session)]) -> AuthSession:
    """A signed-in caller (401 otherwise)."""
    if session is None:
        raise AccountError(401, "auth_required", "Please sign in.")
    return session


def require_unlocked(
    session: Annotated[AuthSession, Depends(require_session)], accounts: AccountsDep
) -> tuple[AuthSession, bytes]:
    """A signed-in, unlocked caller and their data key (423 when locked); counts as activity."""
    if session.dek is None:
        raise AccountError(423, "locked", "HakiAI is locked. Enter your password to continue.")
    accounts.sessions.touch(session)
    return session, session.dek


Session = Annotated[AuthSession, Depends(require_session)]
Unlocked = Annotated[tuple[AuthSession, bytes], Depends(require_unlocked)]


def _throttle(request: Request) -> None:
    """Per-IP budget for the password-checking endpoints (on top of the per-account lockout)."""
    limiter = _limiter(request)
    key = request.client.host if request.client else "unknown"
    if not limiter.allow(key):
        raise AccountError(
            429, "rate_limited", "Too many requests. Please wait and try again.", limiter.retry_after(key)
        )


Throttled = Depends(_throttle)


def _user_out(user: UserView) -> UserOut:
    return UserOut(**asdict(user))


def _set_cookie(request: Request, response: Response, accounts: Accounts, token: str) -> None:
    response.set_cookie(
        COOKIE,
        token,
        max_age=accounts.settings.auth_session_ttl_s,
        path="/api",
        httponly=True,
        samesite="strict",
        secure=request.url.scheme == "https",
    )


def _clear_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE, path="/api", httponly=True, samesite="strict")


def _signed_in(request: Request, response: Response, accounts: Accounts, result: SignedIn, event: str) -> AuthOut:
    _set_cookie(request, response, accounts, result.token)
    log.info(event, extra={"user_id": result.user.id})
    return AuthOut(user=_user_out(result.user), recovery_code=result.recovery_code)


@auth.post("/register", dependencies=[Throttled])
def register(body: RegisterIn, request: Request, response: Response, accounts: AccountsDep) -> AuthOut:
    """Create an account; the recovery code is in this response only."""
    result = accounts.register(body.username, body.password, body.display_name)
    return _signed_in(request, response, accounts, result, "account_created")


@auth.post("/login", dependencies=[Throttled])
def login(body: LoginIn, request: Request, response: Response, accounts: AccountsDep) -> AuthOut:
    """Sign in (unlocked)."""
    return _signed_in(request, response, accounts, accounts.login(body.username, body.password), "signed_in")


@auth.post("/logout")
def logout(
    response: Response, accounts: AccountsDep, session: Annotated[AuthSession | None, Depends(current_session)]
) -> MeOut:
    """Sign out (always succeeds; clears the cookie)."""
    if session is not None:
        accounts.logout(session)
    _clear_cookie(response)
    return MeOut(user=None, locked=False, lock_in_s=0)


@auth.post("/lock")
def lock(session: Session, accounts: AccountsDep) -> MeOut:
    """Drop the data key now."""
    accounts.lock(session)
    return MeOut(user=_user_out(accounts.user(session)), locked=True, lock_in_s=0)


@auth.post("/unlock", dependencies=[Throttled])
def unlock(body: PasswordIn, session: Session, accounts: AccountsDep) -> AuthOut:
    """Unlock with the password."""
    return AuthOut(user=_user_out(accounts.unlock(session, body.password)))


@auth.get("/me")
def me(
    accounts: AccountsDep,
    session: Annotated[AuthSession | None, Depends(current_session)],
    active: Annotated[bool, Query()] = False,
) -> MeOut:
    """Who is signed in and whether locked; active=true reports user activity (resets the idle timer)."""
    if session is None:
        return MeOut(user=None, locked=False, lock_in_s=0)
    if active and not session.locked:
        accounts.sessions.touch(session)
    return MeOut(
        user=_user_out(accounts.user(session)), locked=session.locked, lock_in_s=accounts.sessions.lock_in(session)
    )


@auth.post("/recover", dependencies=[Throttled])
def recover(body: RecoverIn, request: Request, response: Response, accounts: AccountsDep) -> AuthOut:
    """New password via the recovery code; returns a new recovery code (the old one stops working)."""
    result = accounts.recover(body.username, body.recovery_code, body.new_password)
    return _signed_in(request, response, accounts, result, "account_recovered")


@auth.post("/password", dependencies=[Throttled])
def change_password(body: ChangePasswordIn, unlocked: Unlocked, accounts: AccountsDep) -> MeOut:
    """Change the password; other sign-ins end."""
    session, _ = unlocked
    accounts.change_password(session, body.current_password, body.new_password)
    return MeOut(user=_user_out(accounts.user(session)), locked=False, lock_in_s=accounts.sessions.lock_in(session))


@account.get("/profile")
def get_profile(unlocked: Unlocked, accounts: AccountsDep) -> dict[str, str]:
    """The letter profile."""
    return accounts.profile(*unlocked)


@account.put("/profile")
def put_profile(body: ProfileIn, unlocked: Unlocked, accounts: AccountsDep) -> dict[str, str]:
    """Save the letter profile (stored encrypted)."""
    return accounts.save_profile(*unlocked, body.model_dump(include=set(PROFILE_FIELDS)))


@account.get("/prefs")
def get_prefs(unlocked: Unlocked, accounts: AccountsDep) -> dict[str, Any]:
    """Save-history switch and auto-lock minutes."""
    return asdict(accounts.prefs(unlocked[0]))


@account.put("/prefs")
def put_prefs(body: PrefsIn, unlocked: Unlocked, accounts: AccountsDep) -> dict[str, Any]:
    """Save preferences."""
    return asdict(accounts.save_prefs(unlocked[0], Prefs(body.save_history, body.auto_lock_minutes)))


@account.get("/export")
def export(unlocked: Unlocked, accounts: AccountsDep) -> Response:
    """Everything stored for the user, decrypted, as a JSON download."""
    body = json.dumps(accounts.export(*unlocked), ensure_ascii=False, indent=2)
    headers = {"Content-Disposition": 'attachment; filename="hakiai-export.json"'}
    return Response(body, media_type="application/json", headers=headers)


@account.delete("")
def delete_account(body: PasswordIn, response: Response, session: Session, accounts: AccountsDep) -> MeOut:
    """Delete the account and everything in it (password confirmed); the file is compacted."""
    user_id = session.user_id
    accounts.delete(session, body.password)
    _clear_cookie(response)
    log.info("account_deleted", extra={"user_id": user_id})
    return MeOut(user=None, locked=False, lock_in_s=0)
