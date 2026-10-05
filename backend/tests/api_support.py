"""API test wiring: fake stack via devstack, an in-process ASGI driver (no sockets) and an SSE parser."""

import asyncio
import io
import json
import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict

from fastapi import FastAPI
from starlette.types import Message

from backend.app.config import Settings
from backend.app.devstack import fake_deps
from backend.app.interfaces import LLMClient, Translator
from backend.app.logging_setup import configure_logging
from backend.app.main import Runtime, create_app
from backend.tests.fakes import FakeTranslator

EN_QUESTION = "My employer fired me and did not pay my wages. What are my rights?"
SW_QUESTION = "Mwajiri wangu alinifukuza kazi na hakunilipa mshahara wangu. Nina haki gani?"
GARBAGE = "qxzv blorp zzkt wqmmf"
# Mutating /api requests must carry this header (RequestGuardMiddleware).
APP_HEADERS = {"X-Haki": "1"}
SW_WORDS = {"mwajiri": "employer", "alinifukuza": "fired", "mshahara": "wages"}


class Translators(TypedDict):
    """Keyword arguments of make_app for a Kiswahili-capable fake stack."""

    sw_en: FakeTranslator
    en_sw: FakeTranslator


def sw_translators() -> Translators:
    """Fake sw→en (maps SW_QUESTION onto corpus words) and en→sw translators, as make_app keyword arguments."""
    return {"sw_en": FakeTranslator("en", SW_WORDS), "en_sw": FakeTranslator("sw")}


class FakeClock:
    """Manually advanced monotonic clock."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class TickingClock:
    """Epoch seconds that advance one second per reading, so stored times are distinct and ordered."""

    def __init__(self, start: float = 1_800_000_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        self.now += 1
        return self.now


def api_settings(tmp_path: Path, **overrides: Any) -> Settings:
    """Settings for API tests: feedback and frontend paths under tmp_path."""
    fields: dict[str, Any] = {"feedback_path": tmp_path / "feedback.jsonl", "frontend_dist": tmp_path / "no-dist"}
    return Settings(**(fields | overrides))


def make_app(
    tmp_path: Path,
    llm: LLMClient,
    *,
    clock: Callable[[], float] | None = None,
    wall_clock: Callable[[], float] | None = None,
    sw_en: Translator | None = None,
    en_sw: Translator | None = None,
    **overrides: Any,
) -> FastAPI:
    """App over the synthetic corpus with the given fake LLM (and optional translators/clocks)."""
    deps = fake_deps(api_settings(tmp_path, **overrides), tmp_path / "work", llm=llm, sw_en=sw_en, en_sw=en_sw)
    clocks: dict[str, Callable[[], float]] = {"clock": clock} if clock else {}
    if wall_clock:
        clocks["wall_clock"] = wall_clock
    return create_app(deps, **clocks)


def runtime(app: FastAPI) -> Runtime:
    """The app's runtime state (sessions, gate, limiters)."""
    rt: Runtime = app.state.runtime
    return rt


def sse_events(text: str) -> list[tuple[str, dict[str, Any]]]:
    """(event name, JSON data) per SSE block; comments (pings) are skipped."""
    events = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        name, data = "message", []
        for line in block.split("\n"):
            if line.startswith("event:"):
                name = line.removeprefix("event:").strip()
            elif line.startswith("data:"):
                data.append(line.removeprefix("data:").removeprefix(" "))
        if data:
            events.append((name, json.loads("\n".join(data))))
    return events


def tokens_text(events: list[tuple[str, dict[str, Any]]]) -> str:
    """All streamed token text joined."""
    return "".join(str(data["text"]) for name, data in events if name == "token")


@dataclass
class Reply:
    """Status, headers and body of one in-process ASGI call."""

    status: int
    headers: dict[str, str]
    body: bytes

    @property
    def text(self) -> str:
        return self.body.decode()

    def json(self) -> Any:
        return json.loads(self.body)


async def call(
    app: FastAPI,
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    disconnect_when: Callable[[str], bool] | None = None,
    disconnect_after: float | None = None,
    cookie: str | None = None,
) -> Reply:
    """Drive the ASGI app directly; disconnect_when(body so far) or disconnect_after (seconds) triggers an
    http.disconnect; cookie ("name=value") is sent as the Cookie header."""
    path, _, query = path.partition("?")
    payload = json.dumps(body).encode() if body is not None else b""
    disconnect = asyncio.Event()
    if disconnect_after is not None:
        asyncio.get_running_loop().call_later(disconnect_after, disconnect.set)
    request_sent = False
    status, headers, chunks = 0, {}, []

    async def receive() -> Message:
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": payload, "more_body": False}
        await disconnect.wait()
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        nonlocal status
        if message["type"] == "http.response.start":
            status = message["status"]
            headers.update({k.decode(): v.decode() for k, v in message["headers"]})
        elif message["type"] == "http.response.body":
            chunks.append(message.get("body", b""))
            if disconnect_when and disconnect_when(b"".join(chunks).decode()):
                disconnect.set()

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": query.encode(),
        "root_path": "",
        "headers": [
            (b"host", b"test"),
            (b"content-type", b"application/json"),
            (b"x-haki", b"1"),
            *([(b"cookie", cookie.encode())] if cookie else []),
        ],
        "client": ("127.0.0.1", 50000),
        "server": ("test", 80),
    }
    await app(scope, receive, send)
    return Reply(status, headers, b"".join(chunks))


async def sign_up(app: FastAPI, username: str, password: str = "a long enough password") -> str:
    """Register a user through the API; returns the sign-in cookie as "haki_auth=…"."""
    reply = await call(app, "POST", "/api/auth/register", body={"username": username, "password": password})
    assert reply.status == 200, reply.text
    return reply.headers["set-cookie"].split(";", 1)[0]


async def sign_in(app: FastAPI, username: str, password: str = "a long enough password") -> str:
    """A further sign-in of an existing user; returns its cookie."""
    reply = await call(app, "POST", "/api/auth/login", body={"username": username, "password": password})
    assert reply.status == 200, reply.text
    return reply.headers["set-cookie"].split(";", 1)[0]


async def wait_until(condition: Callable[[], bool], timeout_s: float = 5.0) -> None:
    """Poll condition() while letting the event loop (and worker threads) run; fail after timeout_s."""
    for _ in range(int(timeout_s / 0.001)):
        if condition():
            return
        await asyncio.sleep(0.001)
    raise AssertionError("condition not reached")


@contextmanager
def captured_logs() -> Iterator[io.StringIO]:
    """Route the app's JSON logs (content redaction on, as in production) into a buffer."""
    buffer = io.StringIO()
    root = logging.getLogger()
    saved = (root.handlers[:], root.level)
    configure_logging(Settings(), buffer)
    try:
        yield buffer
    finally:
        root.handlers[:], level = saved
        root.setLevel(level)
