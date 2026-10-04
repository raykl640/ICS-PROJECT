from pathlib import Path

import pytest

from backend.app.ingestion.extract import (
    OcrEngine,
    TesseractEngine,
    apply_ocr,
    extract_pages,
    low_density_pages,
    needs_ocr,
)
from backend.tests.fakes import FakeOcrEngine
from backend.tests.fixtures.synthetic_pdf import write_pdf


def test_extract_pages_returns_numbered_page_text(tmp_path: Path) -> None:
    pdf = write_pdf(tmp_path / "a.pdf", [["First page line"], [], ["Third page line"]])
    assert extract_pages(pdf) == [(1, "First page line"), (2, ""), (3, "Third page line")]


def test_low_density_pages_and_needs_ocr() -> None:
    pages = [(1, "x" * 100), (2, "  "), (3, "short"), (4, "y" * 100)]
    assert low_density_pages(pages, min_chars=25) == [2, 3]
    assert needs_ocr(pages, min_chars=25, max_low_ratio=0.2)
    assert not needs_ocr(pages, min_chars=25, max_low_ratio=0.5)
    assert needs_ocr([], min_chars=25, max_low_ratio=0.5)


def test_apply_ocr_replaces_only_low_density_pages(tmp_path: Path) -> None:
    engine = FakeOcrEngine({2: "ocr text"}, confidence=91.0)
    result = apply_ocr(tmp_path / "a.pdf", [(1, "z" * 50), (2, "")], engine, min_chars=25, min_confidence=60.0)
    assert result.pages == [(1, "z" * 50), (2, "ocr text")]
    assert engine.calls == [2]
    assert result.accepted
    assert result.confidence == 91.0


def test_apply_ocr_rejects_low_confidence(tmp_path: Path) -> None:
    engine = FakeOcrEngine({1: "n0isy"}, confidence=40.0)
    assert not apply_ocr(tmp_path / "a.pdf", [(1, "")], engine, min_chars=25, min_confidence=60.0).accepted


def test_engines_satisfy_the_protocol() -> None:
    engine: OcrEngine = FakeOcrEngine({}, confidence=0.0)
    assert engine.page_text(Path("a.pdf"), 1) == ("", 0.0)
    assert callable(TesseractEngine().page_text)


@pytest.mark.real
def test_tesseract_reads_a_rendered_page(tmp_path: Path) -> None:
    pytest.importorskip("pytesseract")
    pdf = write_pdf(tmp_path / "a.pdf", [["Employment contract notice period"]])
    text, confidence = TesseractEngine().page_text(pdf, 1)
    assert "notice" in text.lower()
    assert confidence > 50
