"""OllamaClient against httpx.MockTransport: NDJSON parsing, error mapping, cancellation, health."""

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest

from backend.app.config import Settings
from backend.app.generation.llm import GenerationTimeout, ModelNotLoaded, OllamaClient, OllamaError, OllamaUnavailable
from backend.app.interfaces import LLMClient

SETTINGS = Settings()
MODEL = SETTINGS.ollama_model


def _ndjson(*objs: dict[str, Any]) -> bytes:
    return b"".join(json.dumps(o).encode() + b"\n" for o in objs)


TOKENS = _ndjson(
    {"response": "## RIGHTS", "done": False},
    {"response": " EXPLANATION\n", "done": False},
    {"response": "", "done": False},
    {"response": "You have rights.", "done": False},
    {"response": "", "done": True, "done_reason": "stop"},
)


class ChunkedStream(httpx.AsyncByteStream):
    """Response body delivered in arbitrary byte pieces; records whether it was closed."""

    def __init__(self, pieces: list[bytes], fail: Exception | None = None) -> None:
        self.pieces = pieces
        self.fail = fail
        self.closed = False
        self.sent = 0

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for piece in self.pieces:
            self.sent += 1
            yield piece
            await asyncio.sleep(0)
        if self.fail:
            raise self.fail

    async def aclose(self) -> None:
        self.closed = True


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> OllamaClient:
    return OllamaClient(SETTINGS, transport=httpx.MockTransport(handler))


def _collect(client: OllamaClient, prompt: str = "p") -> list[str]:
    async def run() -> list[str]:
        return [token async for token in client.stream(prompt)]

    return asyncio.run(run())


def test_client_satisfies_the_protocol() -> None:
    assert isinstance(OllamaClient(SETTINGS), LLMClient)


def test_request_carries_model_options_and_keep_alive() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=TOKENS)

    _collect(_client(handler), "PROMPT")
    body = json.loads(seen[0].content)
    assert seen[0].url.path == "/api/generate"
    assert body["model"] == MODEL
    assert body["prompt"] == "PROMPT"
    assert body["stream"] is True
    assert body["keep_alive"] == SETTINGS.ollama_keep_alive
    assert body["options"] == {"temperature": 0.1, "num_ctx": 8192, "num_predict": 1500}


@pytest.mark.parametrize("size", [1, 5, 17, len(TOKENS)])
def test_ndjson_split_into_partial_lines_is_parsed(size: int) -> None:
    pieces = [TOKENS[i : i + size] for i in range(0, len(TOKENS), size)]
    tokens = _collect(_client(lambda r: httpx.Response(200, stream=ChunkedStream(pieces))))
    assert tokens == ["## RIGHTS", " EXPLANATION\n", "You have rights."]


def test_stops_at_done_even_if_more_lines_follow() -> None:
    body = TOKENS + _ndjson({"response": "ignored", "done": False})
    assert _collect(_client(lambda r: httpx.Response(200, content=body)))[-1] == "You have rights."


def test_connection_refused_is_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(OllamaUnavailable, match="not reachable"):
        _collect(_client(handler))


def test_connect_timeout_is_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow", request=request)

    with pytest.raises(OllamaUnavailable):
        _collect(_client(handler))


def test_missing_model_names_the_pull_command() -> None:
    body = {"error": f"model '{MODEL}' not found, try pulling it first"}
    with pytest.raises(ModelNotLoaded, match=f"ollama pull {MODEL}"):
        _collect(_client(lambda r: httpx.Response(404, json=body)))


def test_other_http_error_is_ollama_error() -> None:
    with pytest.raises(OllamaError, match="HTTP 500: boom"):
        _collect(_client(lambda r: httpx.Response(500, json={"error": "boom"})))
    with pytest.raises(OllamaError, match="HTTP 502: bad gateway"):
        _collect(_client(lambda r: httpx.Response(502, text="bad gateway")))


def test_read_timeout_between_tokens_is_generation_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        stream = ChunkedStream([TOKENS[:20]], fail=httpx.ReadTimeout("idle", request=request))
        return httpx.Response(200, stream=stream)

    with pytest.raises(GenerationTimeout):
        _collect(_client(handler))


def test_dropped_connection_mid_stream_is_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=ChunkedStream([TOKENS[:30]], fail=httpx.ReadError("reset")))

    with pytest.raises(OllamaUnavailable, match="dropped"):
        _collect(_client(handler))


def test_error_line_in_stream() -> None:
    body = _ndjson({"response": "a", "done": False}, {"error": "out of memory"})
    with pytest.raises(OllamaError, match="out of memory"):
        _collect(_client(lambda r: httpx.Response(200, content=body)))
    missing = _ndjson({"error": f"model '{MODEL}' not found"})
    with pytest.raises(ModelNotLoaded):
        _collect(_client(lambda r: httpx.Response(200, content=missing)))


def test_malformed_line_is_ollama_error() -> None:
    with pytest.raises(OllamaError, match="malformed"):
        _collect(_client(lambda r: httpx.Response(200, content=b"{not json\n")))


def _many_tokens(n: int) -> list[bytes]:
    return [_ndjson({"response": f"t{i}", "done": False}) for i in range(n)]


def test_closing_the_consumer_closes_the_response() -> None:
    stream = ChunkedStream(_many_tokens(100))
    client = _client(lambda r: httpx.Response(200, stream=stream))

    async def run() -> str:
        tokens = client.stream("p")
        first = await anext(tokens)
        await tokens.aclose()  # type: ignore[attr-defined]
        return first

    assert asyncio.run(run()) == "t0"
    assert stream.closed
    assert stream.sent < 100


def test_cancelling_the_task_closes_the_response() -> None:
    stream = ChunkedStream(_many_tokens(1000))
    client = _client(lambda r: httpx.Response(200, stream=stream))
    received: list[str] = []

    async def consume() -> None:
        async for token in client.stream("p"):
            received.append(token)

    async def run() -> None:
        task = asyncio.create_task(consume())
        while not received:
            await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    assert stream.closed
    assert stream.sent < 1000


@pytest.mark.parametrize(
    ("models", "expected"),
    [
        ([{"name": MODEL}], (True, True)),
        ([{"model": MODEL}], (True, True)),
        ([{"name": "llama3:latest"}], (True, False)),
        ([], (True, False)),
    ],
)
def test_status_checks_tags_for_the_model(models: list[dict[str, str]], expected: tuple[bool, bool]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": models})

    client = _client(handler)
    assert asyncio.run(client.status()) == expected
    assert asyncio.run(client.health()) is all(expected)


def test_untagged_model_name_matches_latest() -> None:
    settings = Settings(ollama_model="mistral")
    client = OllamaClient(
        settings,
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"models": [{"name": "mistral:latest"}]})),
    )
    assert asyncio.run(client.health()) is True


@pytest.mark.parametrize(
    "respond",
    [
        lambda r: (_ for _ in ()).throw(httpx.ConnectError("refused", request=r)),
        lambda r: httpx.Response(500),
        lambda r: httpx.Response(200, text="not json"),
    ],
)
def test_status_is_false_when_ollama_is_down_or_broken(respond: Callable[[httpx.Request], httpx.Response]) -> None:
    assert asyncio.run(_client(respond).status()) == (False, False)


@pytest.mark.real
@pytest.mark.enable_socket
def test_real_ollama_short_generation() -> None:
    client = OllamaClient(Settings(num_predict=8))
    if not asyncio.run(client.health()):
        pytest.skip(f"Ollama not running or {MODEL} not pulled")
    tokens = _collect(client, "Reply with the single word OK.")
    assert "".join(tokens).strip()
