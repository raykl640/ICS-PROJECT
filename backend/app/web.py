"""HTTP plumbing: request body limit, security headers, and the built frontend served with an SPA fallback."""

from collections.abc import Mapping

from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_BODYLESS = frozenset({"GET", "HEAD", "OPTIONS"})
_MUTATING = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_HEADERS = (
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
    (b"cross-origin-opener-policy", b"same-origin"),
)
# sha256 of the one inline script in frontend/index.html (applies theme/text settings before first paint);
# test_frontend_contract.py recomputes it, so editing that script without updating this hash fails the tests.
PREPAINT_SCRIPT_SHA256 = "VfkE1Zc3MzC7WjYhoxEUH1BGZj7Ee6FNUzHB7gBwt0I="
_CSP = (
    b"default-src 'self'; script-src 'self' 'sha256-" + PREPAINT_SCRIPT_SHA256.encode() + b"'; "
    b"img-src 'self' data:; style-src 'self' 'unsafe-inline'; connect-src 'self'; "
    b"frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)
# FastAPI's Swagger/ReDoc pages load their assets from a CDN, which the CSP would block.
_DOCS_PREFIXES = ("/docs", "/redoc")


def error_response(status: int, code: str, message: str, headers: Mapping[str, str] | None = None) -> JSONResponse:
    """The uniform error body {"error": {"code", "message"}}."""
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status, headers=headers)


class BodyLimitMiddleware:
    """Reads request bodies up to max_bytes (413 beyond that) and hands the buffered body to the app."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Buffer and size-check the body of non-GET HTTP requests."""
        if scope["type"] != "http" or scope["method"] in _BODYLESS:
            await self.app(scope, receive, send)
            return
        body = b""
        more = True
        while more:
            message = await receive()
            if message["type"] != "http.request":
                return  # client went away before sending the body
            body += message.get("body", b"")
            more = message.get("more_body", False)
            if len(body) > self.max_bytes:
                response = error_response(413, "body_too_large", f"Request body is larger than {self.max_bytes} bytes.")
                await response(scope, receive, send)
                return
        sent = False

        async def replay() -> Message:
            nonlocal sent
            if sent:
                return await receive()
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, replay, send)


def host_name(host_header: str) -> str:
    """The host part of a Host header, lower-cased: "LocalHost:8000" → "localhost", "[::1]:8000" → "[::1]"."""
    host = host_header.strip().lower()
    if host.startswith("["):
        return host.split("]", 1)[0] + "]"
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


class RequestGuardMiddleware:
    """Localhost hardening: the Host header must be allow-listed (DNS rebinding), and mutating /api requests must carry
    X-Haki: 1, which a cross-site form cannot send and a cross-site fetch cannot send without a refused preflight."""

    def __init__(self, app: ASGIApp, allowed_hosts: list[str]) -> None:
        self.app = app
        self.allowed = {h.lower() for h in allowed_hosts}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Reject a bad Host (400) or a mutating API call without the header (403)."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {name.lower(): value for name, value in scope.get("headers", [])}
        if host_name(headers.get(b"host", b"").decode("latin-1")) not in self.allowed:
            await error_response(400, "bad_host", "This address is not served by HakiAI.")(scope, receive, send)
            return
        if scope["method"] in _MUTATING and scope["path"].startswith("/api/") and headers.get(b"x-haki") != b"1":
            await error_response(403, "missing_header", "Requests must come from the HakiAI app.")(scope, receive, send)
            return
        await self.app(scope, receive, send)


class SecurityHeadersMiddleware:
    """Adds hardening headers to every HTTP response, and Cache-Control: no-store to API responses."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Wrap send to extend the response headers."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope["path"]

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                names = {name.lower() for name, _ in headers}
                headers += [h for h in _HEADERS if h[0] not in names]
                if not path.startswith(_DOCS_PREFIXES):
                    headers.append((b"content-security-policy", _CSP))
                if path.startswith("/api/") and b"cache-control" not in names:
                    headers.append((b"cache-control", b"no-store"))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)


class SPAStaticFiles(StaticFiles):
    """Static build of the React app; unknown non-API paths get index.html so client-side routes work."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        """The file at path, else index.html (API paths keep their 404)."""
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404 or path.split("/", 1)[0] == "api":
                raise
            return await super().get_response("index.html", scope)
