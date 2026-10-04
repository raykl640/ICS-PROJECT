"""Ollama streaming client (implements interfaces.LLMClient) with typed errors."""

import json
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from backend.app.config import Settings


class OllamaError(RuntimeError):
    """Ollama returned an error or an unreadable response."""


class OllamaUnavailable(OllamaError):
    """Ollama is not reachable (not running, wrong URL, or the connection dropped)."""


class ModelNotLoaded(OllamaError):
    """The configured model is not available in Ollama."""


class GenerationTimeout(OllamaError):
    """No token arrived within the read timeout."""


class OllamaClient:
    """POST /api/generate with stream=true; yields response tokens as they arrive."""

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self._transport = transport
        # Short connect; generous read, since prompt evaluation on CPU can take minutes before the first token.
        self._timeout = httpx.Timeout(settings.ollama_read_timeout_s, connect=settings.ollama_connect_timeout_s)

    def _client(self, timeout: httpx.Timeout) -> httpx.AsyncClient:
        """Fresh client per call, so no connection pool outlives the event loop that made it."""
        return httpx.AsyncClient(base_url=self.settings.ollama_url, timeout=timeout, transport=self._transport)

    def _payload(self, prompt: str) -> dict[str, Any]:
        """Generate request with the configured sampling and context options."""
        s = self.settings
        return {
            "model": s.ollama_model,
            "prompt": prompt,
            "stream": True,
            "keep_alive": s.ollama_keep_alive,
            "options": {"temperature": s.temperature, "num_ctx": s.num_ctx, "num_predict": s.num_predict},
        }

    def _not_loaded(self) -> ModelNotLoaded:
        """Error naming the exact pull command."""
        model = self.settings.ollama_model
        return ModelNotLoaded(f"Model {model!r} is not available in Ollama. Run: ollama pull {model}")

    async def stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """Yield generated tokens; closing or cancelling the consumer closes the HTTP response, which stops Ollama."""
        try:
            async with (
                self._client(self._timeout) as client,
                client.stream("POST", "/api/generate", json=self._payload(prompt)) as response,
            ):
                await self._raise_for_status(response)
                async for line in response.aiter_lines():
                    token, done = self._parse_line(line)
                    if token:
                        yield token
                    if done:
                        return
        except httpx.ConnectError as exc:
            raise OllamaUnavailable(f"Ollama is not reachable at {self.settings.ollama_url}") from exc
        except httpx.ConnectTimeout as exc:
            raise OllamaUnavailable(f"Ollama did not accept a connection at {self.settings.ollama_url}") from exc
        except httpx.TimeoutException as exc:
            raise GenerationTimeout(f"no token from Ollama within {self.settings.ollama_read_timeout_s} s") from exc
        except (httpx.RemoteProtocolError, httpx.ReadError) as exc:
            raise OllamaUnavailable("connection to Ollama dropped during generation") from exc

    async def _raise_for_status(self, response: httpx.Response) -> None:
        """Map a non-200 response to a typed error (404 = model missing)."""
        if response.status_code == 200:
            return
        await response.aread()
        if response.status_code == 404:
            raise self._not_loaded()
        raise OllamaError(f"Ollama returned HTTP {response.status_code}: {_error_text(response)}")

    def _parse_line(self, line: str) -> tuple[str, bool]:
        """One NDJSON line -> (token, done)."""
        if not line.strip():
            return "", False
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise OllamaError("malformed line in Ollama stream") from exc
        if "error" in data:
            message = str(data["error"])
            raise self._not_loaded() if "not found" in message else OllamaError(f"Ollama error: {message}")
        return str(data.get("response", "")), bool(data.get("done", False))

    async def status(self) -> tuple[bool, bool]:
        """(reachable, model available) from GET /api/tags."""
        timeout = httpx.Timeout(self.settings.ollama_health_timeout_s)
        try:
            async with self._client(timeout) as client:
                response = await client.get("/api/tags")
                response.raise_for_status()
                models = response.json().get("models", [])
        except (httpx.HTTPError, ValueError):
            return False, False
        names = {m.get(key, "") for m in models for key in ("name", "model")}
        wanted = self.settings.ollama_model
        return True, wanted in names or f"{wanted}:latest" in names

    async def health(self) -> bool:
        """True if Ollama is reachable and the configured model is pulled."""
        return all(await self.status())


def _error_text(response: httpx.Response) -> str:
    """The "error" field of an Ollama error body, else a short slice of the body."""
    try:
        return str(response.json()["error"])
    except (ValueError, KeyError, TypeError):
        return response.text[:200]
