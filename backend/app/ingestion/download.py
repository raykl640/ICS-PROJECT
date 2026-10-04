"""Make sure every corpus PDF is in data/raw_pdfs: verify, download missing ones (never overwrite), record sha256."""

import argparse
import contextlib
import hashlib
import json
import logging
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import requests

from backend.app.config import ActSpec, Settings, get_settings

log = logging.getLogger(__name__)

Fetcher = Callable[[str], bytes]
ManifestEntry = dict[str, Any]


class MissingPDFError(FileNotFoundError):
    """Corpus PDFs that are absent and could not be downloaded."""

    def __init__(self, files: list[str]) -> None:
        super().__init__(f"missing corpus PDFs: {', '.join(files)}")
        self.files = files


def sha256_file(path: Path) -> str:
    """Hex sha256 of a file, read in blocks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_manifest(path: Path) -> dict[str, ManifestEntry]:
    """Per-Act manifest entries keyed by slug; empty when the file does not exist yet."""
    if not path.exists():
        return {}
    acts: dict[str, ManifestEntry] = json.loads(path.read_text(encoding="utf-8"))["acts"]
    return acts


def update_manifest(path: Path, entries: Mapping[str, ManifestEntry]) -> None:
    """Merge fields into the manifest and rewrite it with sorted keys (deterministic, no timestamps)."""
    acts = load_manifest(path)
    for slug, fields in entries.items():
        acts.setdefault(slug, {}).update(fields)
    path.write_text(json.dumps({"acts": acts}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def http_fetcher(settings: Settings) -> Fetcher:
    """GET with the configured user agent and timeout; raises on HTTP errors."""

    def fetch(url: str) -> bytes:
        headers = {"User-Agent": settings.download_user_agent}
        response = requests.get(url, headers=headers, timeout=settings.download_timeout_s)
        response.raise_for_status()
        return response.content

    return fetch


def download(url: str, dest: Path, fetch: Fetcher, retries: int) -> None:
    """Fetch a PDF into dest via a temporary file; an existing dest is never touched."""
    if dest.exists():
        return
    for attempt in range(1, retries + 1):
        try:
            data = fetch(url)
        except (requests.RequestException, OSError) as exc:
            log.warning("download_failed", extra={"file": dest.name, "attempt": attempt, "error": type(exc).__name__})
            continue
        if not data.startswith(b"%PDF"):
            log.warning("download_not_pdf", extra={"file": dest.name, "attempt": attempt})
            continue
        partial = dest.with_name(dest.name + ".part")
        partial.write_bytes(data)
        partial.rename(dest)
        return
    raise MissingPDFError([dest.name])


def ensure_pdfs(
    specs: Sequence[ActSpec], settings: Settings | None = None, offline: bool = False, fetch: Fetcher | None = None
) -> list[Path]:
    """Paths of all corpus PDFs, downloading missing ones that have a URL unless offline; records sha256."""
    settings = settings or get_settings()
    fetcher = fetch or http_fetcher(settings)
    missing = []
    for spec in specs:
        path = settings.pdf_path(spec)
        if not path.exists() and spec.url and not offline:
            with contextlib.suppress(MissingPDFError):
                download(spec.url, path, fetcher, settings.download_retries)
        if not path.exists():
            missing.append(spec.file)
    if missing:
        raise MissingPDFError(missing)
    paths = [settings.pdf_path(spec) for spec in specs]
    entries = {
        s.slug: {"file": s.file, "sha256": sha256_file(p), "bytes": p.stat().st_size}
        for s, p in zip(specs, paths, strict=True)
    }
    update_manifest(settings.manifest_path, entries)
    return paths


def main(argv: Sequence[str] | None = None, settings: Settings | None = None) -> int:
    """CLI: verify (and unless --offline, download) the corpus PDFs. Exit 2 when any is missing."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="only verify presence; never download")
    args = parser.parse_args(argv)
    settings = settings or get_settings()
    try:
        paths = ensure_pdfs(settings.acts, settings, offline=args.offline)
    except MissingPDFError as err:
        print(f"{err}. Put them in {settings.raw_pdf_dir} (see data/sources.yaml).", file=sys.stderr)
        return 2
    print(f"{len(paths)} PDFs present; sha256 recorded in {settings.manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
