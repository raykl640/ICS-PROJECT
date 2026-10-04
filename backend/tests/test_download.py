import hashlib
import json
from pathlib import Path

import pytest
import requests

from backend.app.config import ActSpec, Settings
from backend.app.ingestion.download import MissingPDFError, download, ensure_pdfs, load_manifest, main

PDF_BYTES = b"%PDF-1.4 synthetic"
SPEC = ActSpec(name="Sample Act", year=2001, file="Sample Act.pdf")
WITH_URL = ActSpec(name="Other Act", year=2002, file="Other Act.pdf", url="https://example.invalid/other.pdf")


def settings_for(tmp_path: Path, *acts: ActSpec) -> Settings:
    (tmp_path / "raw").mkdir(exist_ok=True)
    return Settings(raw_pdf_dir=tmp_path / "raw", manifest_path=tmp_path / "manifest.json", acts=list(acts))


def never_called(url: str) -> bytes:
    raise AssertionError(f"unexpected download of {url}")


def test_existing_pdf_is_kept_and_its_sha256_recorded(tmp_path: Path) -> None:
    settings = settings_for(tmp_path, SPEC)
    (settings.raw_pdf_dir / SPEC.file).write_bytes(PDF_BYTES)
    paths = ensure_pdfs([SPEC], settings, fetch=never_called)
    assert paths == [settings.raw_pdf_dir / SPEC.file]
    entry = load_manifest(settings.manifest_path)["sample-act"]
    assert entry["sha256"] == hashlib.sha256(PDF_BYTES).hexdigest()
    assert entry["bytes"] == len(PDF_BYTES)
    assert entry["file"] == SPEC.file


def test_manifest_update_keeps_other_fields(tmp_path: Path) -> None:
    settings = settings_for(tmp_path, SPEC)
    (settings.raw_pdf_dir / SPEC.file).write_bytes(PDF_BYTES)
    settings.manifest_path.write_text(json.dumps({"acts": {"sample-act": {"pages": 3}}}))
    ensure_pdfs([SPEC], settings, fetch=never_called)
    assert load_manifest(settings.manifest_path)["sample-act"]["pages"] == 3


def test_missing_pdf_without_url_lists_every_missing_file(tmp_path: Path) -> None:
    settings = settings_for(tmp_path, SPEC, WITH_URL)
    with pytest.raises(MissingPDFError) as err:
        ensure_pdfs([SPEC, WITH_URL], settings, offline=True, fetch=never_called)
    assert err.value.files == ["Sample Act.pdf", "Other Act.pdf"]
    assert "Sample Act.pdf" in str(err.value)


def test_download_retries_then_writes_the_file(tmp_path: Path) -> None:
    settings = settings_for(tmp_path, WITH_URL)
    calls: list[str] = []

    def flaky(url: str) -> bytes:
        calls.append(url)
        if len(calls) < 3:
            raise requests.ConnectionError("down")
        return PDF_BYTES

    ensure_pdfs([WITH_URL], settings, fetch=flaky)
    assert len(calls) == 3
    assert (settings.raw_pdf_dir / WITH_URL.file).read_bytes() == PDF_BYTES


def test_non_pdf_response_is_rejected_and_nothing_is_written(tmp_path: Path) -> None:
    dest = tmp_path / "x.pdf"
    with pytest.raises(MissingPDFError):
        download("https://example.invalid/x.pdf", dest, lambda url: b"<html>not found</html>", retries=2)
    assert list(tmp_path.iterdir()) == []


def test_download_never_overwrites_an_existing_file(tmp_path: Path) -> None:
    dest = tmp_path / "x.pdf"
    dest.write_bytes(b"original")
    download("https://example.invalid/x.pdf", dest, never_called, retries=1)
    assert dest.read_bytes() == b"original"


def test_main_offline_reports_missing_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--offline"], settings_for(tmp_path, SPEC)) == 2
    assert "Sample Act.pdf" in capsys.readouterr().err


def test_main_succeeds_when_all_present(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    settings = settings_for(tmp_path, SPEC)
    (settings.raw_pdf_dir / SPEC.file).write_bytes(PDF_BYTES)
    assert main(["--offline"], settings) == 0
    assert "1 PDFs present" in capsys.readouterr().out
