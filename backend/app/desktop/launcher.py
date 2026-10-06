"""HakiAI desktop launcher: the packaged app's entry point, also `python -m backend.app.desktop` (D34).

A plain run opens HakiAI in the browser: it reuses a running instance, else starts Ollama when it is installed but
down, runs the first-time setup (a child process allowed online) when a local model is missing, then serves the API
and the built frontend on 127.0.0.1. `--setup` is that child: it caches the Hugging Face models and pulls the Ollama
model. `--self-test` checks the bundled corpus, indexes and frontend, then answers one question on the fake backends
over real HTTP; CI runs it on every packaged build.
"""

import argparse
import asyncio
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from backend.app.config import Settings, get_settings
from backend.app.generation.llm import OllamaClient
from backend.app.offline import OFFLINE_ENV, Step, cache_models, hf_models, real_tools, report
from backend.app.preflight import index_problems

if TYPE_CHECKING:
    import uvicorn

SELF_TEST_QUESTION = "My employer fired me and did not pay my wages. What are my rights?"
APP_HEADERS = {"X-Haki": "1"}
WEIGHT_FILES = ("model.safetensors", "pytorch_model.bin")
_POLL_S = 0.2


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    """Command-line flags of the launcher."""
    parser = argparse.ArgumentParser(prog="hakiai", description="Start HakiAI and open it in the browser.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--setup", action="store_true", help="download the AI models now (needs internet), then exit")
    mode.add_argument("--self-test", action="store_true", help="check this installation on built-in test data")
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    return parser.parse_args(argv)


def self_command() -> list[str]:
    """How to start this launcher again: the packaged executable, or this package under the current Python."""
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, "-m", "backend.app.desktop"]


def online_env(env: Mapping[str, str]) -> dict[str, str]:
    """env for the setup child: online, plain HTTP downloads, and no hub warnings the user cannot act on."""
    quiet = {"HF_HUB_DISABLE_XET": "1", "HF_HUB_VERBOSITY": "error"}
    return {key: value for key, value in env.items() if key not in OFFLINE_ENV} | quiet


def find_ollama(which: Callable[[str], str | None], env: Mapping[str, str]) -> str | None:
    """The ollama executable on PATH, else where Ollama's Windows installer puts it (PATH is stale right after it)."""
    found = which("ollama")
    if found:
        return found
    local = env.get("LOCALAPPDATA")
    candidate = Path(local) / "Programs" / "Ollama" / "ollama.exe" if local else None
    return str(candidate) if candidate is not None and candidate.is_file() else None


def ollama_status(settings: Settings) -> tuple[bool, bool]:
    """(reachable, model present) of the configured Ollama."""
    return asyncio.run(OllamaClient(settings).status())


def start_ollama(executable: str, log_path: Path) -> None:
    """`ollama serve` in the background, detached so it outlives this window; its output goes to log_path."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as log:
        command = [executable, "serve"]
        if sys.platform == "win32":
            flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
            subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=log, creationflags=flags)
        else:
            subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)


def wait_for_ollama(settings: Settings, status: Callable[[], tuple[bool, bool]]) -> tuple[bool, bool]:
    """Poll Ollama until it answers or settings.ollama_start_wait_s passes; the last status."""
    deadline = time.monotonic() + settings.ollama_start_wait_s
    current = status()
    while not current[0] and time.monotonic() < deadline:
        time.sleep(1.0)
        current = status()
    return current


def hf_cached(model: str) -> bool:
    """True if the model's config and PyTorch weights are in the local cache (what an offline load reads)."""
    from huggingface_hub import try_to_load_from_cache

    def cached(filename: str) -> bool:
        return isinstance(try_to_load_from_cache(model, filename), str)

    return cached("config.json") and any(cached(name) for name in WEIGHT_FILES)


def missing_models(models: Sequence[str], cached: Callable[[str], bool]) -> list[str]:
    """The models not yet in the local cache."""
    return [model for model in models if not cached(model)]


def _progress_line(data: Mapping[str, object]) -> str:
    """One status line of an Ollama pull: the step, with a percentage while a layer downloads."""
    status = str(data.get("status", ""))
    total, completed = data.get("total"), data.get("completed")
    if isinstance(total, int) and isinstance(completed, int) and total > 0:
        return f"{status[:40]}: {completed * 100 // total}% of {total / 1e9:.1f} GB"
    return status


def pull_model(settings: Settings, out: Callable[[str], None], transport: httpx.BaseTransport | None = None) -> Step:
    """Pull the configured model through Ollama's HTTP API (no CLI on PATH needed), printing progress."""
    name = f"download {settings.ollama_model} with Ollama"
    timeout = httpx.Timeout(settings.ollama_connect_timeout_s, read=None)
    last = ""
    try:
        with (
            httpx.Client(base_url=settings.ollama_url, timeout=timeout, transport=transport) as client,
            client.stream("POST", "/api/pull", json={"model": settings.ollama_model}) as response,
        ):
            response.raise_for_status()
            for line in response.iter_lines():
                data = json.loads(line) if line.strip() else {}
                if "error" in data:
                    return Step(name, False, f"Ollama: {data['error']}")
                text = _progress_line(data)
                if text and text != last:
                    out(text)
                    last = text
    except (httpx.HTTPError, ValueError) as exc:
        return Step(name, False, f"{type(exc).__name__}: check the internet connection, then start HakiAI again")
    return Step(name, True)


def run_setup(settings: Settings, download: Callable[[str], object], out: Callable[[str], None]) -> int:
    """First-time setup: cache the Hugging Face models, then pull the Ollama model if Ollama answers."""
    steps = cache_models(hf_models(settings), download)
    if ollama_status(settings)[0]:
        steps.append(pull_model(settings, out))
    else:
        out(f"Ollama is not running, so {settings.ollama_model} was not downloaded; HakiAI does it on the next start.")
    return report(steps)


def free_port(host: str) -> int:
    """A TCP port nobody listens on right now."""
    with socket.socket() as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def port_available(host: str, port: int) -> bool:
    """True if port can be bound on host."""
    with socket.socket() as sock:
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def is_hakiai(base_url: str, transport: httpx.BaseTransport | None = None) -> bool:
    """True if a HakiAI server already answers at base_url (health carries its own keys, 200 or 503)."""
    try:
        with httpx.Client(base_url=base_url, timeout=2.0, transport=transport) as client:
            body = client.get("/api/health").json()
    except (httpx.HTTPError, ValueError):
        return False
    return isinstance(body, dict) and "indexes_loaded" in body


def _server(settings: Settings, port: int) -> "uvicorn.Server":
    """uvicorn serving the app (as configured by the environment at this point) on settings.api_host:port."""
    import uvicorn

    from backend.app.main import app

    return uvicorn.Server(uvicorn.Config(app, host=settings.api_host, port=port, log_level="warning"))


def _wait_started(server: "uvicorn.Server", thread: threading.Thread | None = None) -> bool:
    """Block until the server accepts requests (True) or stops, or its thread dies, first (False)."""
    while not server.started:
        if server.should_exit or (thread is not None and not thread.is_alive()):
            return False
        time.sleep(_POLL_S)
    return True


def serve(settings: Settings, port: int, open_browser: bool) -> int:
    """Serve HakiAI until Ctrl+C or the window closes; open the browser once it is up."""
    server = _server(settings, port)
    url = f"http://{settings.api_host}:{port}"

    def announce() -> None:
        if _wait_started(server):
            print(f"HakiAI is running at {url}\nKeep this window open while you use it; close it to quit.", flush=True)
            if open_browser:
                webbrowser.open(url)

    print("Starting HakiAI: loading the laws and the language models (up to a minute)...", flush=True)
    threading.Thread(target=announce, daemon=True).start()
    server.run()
    return 0


def smoke_checks(client: httpx.Client) -> list[Step]:
    """Health, the frontend page, and one question streamed to the end, through any HTTP client of the app."""
    health = client.get("/api/health")
    steps = [Step("health", health.status_code == 200, health.text[:200])]
    page = client.get("/")
    html = page.status_code == 200 and "text/html" in page.headers.get("content-type", "")
    steps.append(Step("frontend served", html))
    asked = client.post("/api/query", json={"question": SELF_TEST_QUESTION, "language": "en"}, headers=APP_HEADERS)
    if asked.status_code != 200:
        return [*steps, Step("question accepted", False, asked.text[:200])]
    stream = client.get(f"/api/stream/{asked.json()['session_id']}")
    return [*steps, Step("question accepted", True), Step("answer streamed", "event: done" in stream.text)]


def bundle_checks(settings: Settings) -> list[Step]:
    """The corpus, its indexes and the frontend build that ship with this installation."""
    problems = index_problems(settings)
    built = (settings.frontend_dist / "index.html").is_file()
    return [
        Step("corpus and indexes", not problems, "; ".join(problems)),
        Step("frontend build", built, "" if built else f"{settings.frontend_dist} has no index.html"),
    ]


def _served_checks(settings: Settings) -> list[Step]:
    """smoke_checks against a real uvicorn server on a free port, stopped afterwards."""
    server = _server(settings, free_port(settings.api_host))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    if not _wait_started(server, thread):
        return [Step("server started", False, "see the error above")]
    base_url = f"http://{settings.api_host}:{server.config.port}"
    try:
        with httpx.Client(base_url=base_url, timeout=settings.self_test_timeout_s) as client:
            return smoke_checks(client)
    finally:
        server.should_exit = True
        thread.join(settings.self_test_timeout_s)


def self_test() -> int:
    """bundle_checks, then smoke_checks on the fake backends (no models, no Ollama); writes only to a temp folder."""
    steps = bundle_checks(get_settings())
    with tempfile.TemporaryDirectory(prefix="hakiai-selftest-", ignore_cleanup_errors=True) as scratch:
        os.environ["HAKI_FAKE_BACKENDS"] = "1"
        os.environ["HAKI_APP_DB_PATH"] = str(Path(scratch) / "app.db")
        os.environ["HAKI_FEEDBACK_PATH"] = str(Path(scratch) / "feedback.jsonl")
        get_settings.cache_clear()
        steps += _served_checks(get_settings())
    return report(steps)


def ensure_ollama(settings: Settings, open_browser: bool) -> tuple[bool, bool]:
    """Start an installed but stopped Ollama; when Ollama is missing, say how to get it. (reachable, model present)."""
    status = ollama_status(settings)
    if status[0]:
        return status
    executable = find_ollama(shutil.which, os.environ)
    if executable is None:
        print(
            "Ollama, the local AI engine HakiAI writes its answers with, is not installed.\n"
            f"Install it from {settings.ollama_download_url}, then start HakiAI again. Until then you can read and\n"
            "search the laws, but questions cannot be answered.",
            flush=True,
        )
        if open_browser:
            webbrowser.open(settings.ollama_download_url)
        return status
    print("Starting Ollama...", flush=True)
    start_ollama(executable, settings.ollama_log_path)
    return wait_for_ollama(settings, lambda: ollama_status(settings))


def launch(settings: Settings, open_browser: bool) -> int:
    """The plain run: reuse a running HakiAI, else set up what is missing and serve."""
    existing = f"http://{settings.api_host}:{settings.api_port}"
    if is_hakiai(existing):
        print(f"HakiAI is already running at {existing}", flush=True)
        if open_browser:
            webbrowser.open(existing)
        return 0
    reachable, present = ensure_ollama(settings, open_browser)
    if missing_models(hf_models(settings), hf_cached) or (reachable and not present):
        print("First-time setup: downloading the AI models (about 5 GB, needs internet once).", flush=True)
        child = subprocess.run([*self_command(), "--setup"], env=online_env(os.environ), check=False)
        if child.returncode != 0:
            print("Setup did not finish (see the lines above). Start HakiAI again to retry.", flush=True)
            return 1
    host, port = settings.api_host, settings.api_port
    return serve(settings, port if port_available(host, port) else free_port(host), open_browser)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry: --self-test, --setup, or launch."""
    args = parse_args(argv)
    if args.self_test:
        return self_test()
    if args.setup:
        return run_setup(get_settings(), real_tools().download, lambda text: print(text, flush=True))
    # Everything after this point runs offline: models load from the local cache only. The window shows warnings only.
    for key, value in {**OFFLINE_ENV, "HAKI_LOG_LEVEL": "WARNING"}.items():
        os.environ.setdefault(key, value)
    return launch(get_settings(), open_browser=not args.no_browser)


def run() -> int:
    """main(), keeping a double-clicked window open on failure so its message can be read."""
    code = main()
    if code != 0 and getattr(sys, "frozen", False) and sys.stdin is not None and sys.stdin.isatty():
        input("Press Enter to close this window.")
    return code
