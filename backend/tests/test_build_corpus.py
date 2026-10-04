import json
from pathlib import Path

import pytest

from backend.app.config import ActSpec, Settings
from backend.app.ingestion.build_corpus import main
from backend.app.ingestion.download import load_manifest, sha256_file
from backend.tests.fakes import FakeOcrEngine
from backend.tests.fixtures.synthetic_pdf import SAMPLE_ACT_PAGES, write_pdf

SPEC = ActSpec(name="Sample Act", year=2001, file="Sample Act.pdf", cap="999")
SCANNED = ActSpec(name="Scanned Act", year=1990, file="Scanned Act.pdf")


def settings_for(tmp_path: Path, *acts: ActSpec) -> Settings:
    raw = tmp_path / "raw"
    raw.mkdir(exist_ok=True)
    return Settings(
        raw_pdf_dir=raw,
        processed_dir=tmp_path / "processed",
        chunks_path=tmp_path / "processed" / "chunks.json",
        parse_report_path=tmp_path / "processed" / "parse_report.md",
        manifest_path=tmp_path / "manifest.json",
        acts=list(acts),
    )


def outputs(settings: Settings) -> tuple[bytes, bytes, bytes]:
    return (
        settings.chunks_path.read_bytes(),
        settings.parse_report_path.read_bytes(),
        settings.manifest_path.read_bytes(),
    )


def test_build_writes_chunks_report_and_manifest(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    settings = settings_for(tmp_path, SPEC)
    pdf = write_pdf(settings.raw_pdf_dir / SPEC.file, SAMPLE_ACT_PAGES)
    assert main([], settings) == 0
    chunks = json.loads(settings.chunks_path.read_text())
    assert [c["chunk_id"] for c in chunks][:2] == ["sample-act-1", "sample-act-2"]
    assert {c["source_sha256"] for c in chunks} == {sha256_file(pdf)}
    assert "| Sample Act | 7 | 2 | 2 |" in settings.parse_report_path.read_text()
    entry = load_manifest(settings.manifest_path)["sample-act"]
    assert (entry["pages"], entry["needs_ocr"], entry["ocr"]) == (5, False, "not_needed")
    assert entry["sha256"] == sha256_file(pdf)
    assert "7 chunks" in capsys.readouterr().out


def test_build_is_byte_for_byte_deterministic(tmp_path: Path) -> None:
    settings = settings_for(tmp_path, SPEC)
    write_pdf(settings.raw_pdf_dir / SPEC.file, SAMPLE_ACT_PAGES)
    main([], settings)
    first = outputs(settings)
    main([], settings)
    assert outputs(settings) == first


def test_missing_pdf_stops_with_exit_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([], settings_for(tmp_path, SPEC)) == 2
    assert "Sample Act.pdf" in capsys.readouterr().err


def test_scanned_pdf_without_ocr_is_an_empty_parse(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    settings = settings_for(tmp_path, SPEC, SCANNED)
    write_pdf(settings.raw_pdf_dir / SPEC.file, SAMPLE_ACT_PAGES)
    write_pdf(settings.raw_pdf_dir / SCANNED.file, [[], []])
    assert main([], settings) == 1
    assert "Scanned Act" in capsys.readouterr().err
    report = settings.parse_report_path.read_text()
    assert "EMPTY PARSE" in report and "needs_ocr" in report
    entry = load_manifest(settings.manifest_path)["scanned-act"]
    assert (entry["needs_ocr"], entry["ocr"], entry["low_density_pages"]) == (True, "disabled", [1, 2])


def test_ocr_text_is_parsed_when_confident(tmp_path: Path) -> None:
    settings = settings_for(tmp_path, SCANNED)
    write_pdf(settings.raw_pdf_dir / SCANNED.file, [[], []])
    engine = FakeOcrEngine({1: "1. Short title\nThis Act may be cited as the Scanned Act."}, confidence=88.0)
    assert main(["--ocr"], settings, ocr_engine=engine) == 0
    (chunk,) = json.loads(settings.chunks_path.read_text())
    assert chunk["chunk_id"] == "scanned-act-1"
    entry = load_manifest(settings.manifest_path)["scanned-act"]
    assert (entry["ocr"], entry["ocr_confidence"]) == ("applied", 88.0)


def test_low_confidence_ocr_excludes_the_document(tmp_path: Path) -> None:
    settings = settings_for(tmp_path, SCANNED)
    write_pdf(settings.raw_pdf_dir / SCANNED.file, [[]])
    engine = FakeOcrEngine({1: "1. Sh0rt t1tle"}, confidence=35.0)
    assert main(["--ocr"], settings, ocr_engine=engine) == 1
    assert json.loads(settings.chunks_path.read_text()) == []
    assert load_manifest(settings.manifest_path)["scanned-act"]["ocr"] == "excluded_low_confidence"
