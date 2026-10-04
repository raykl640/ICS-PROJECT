"""PDF page text via pdfplumber, a text-density check, and optional OCR behind a small interface."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pdfplumber

Pages = list[tuple[int, str]]


def extract_pages(pdf: Path) -> Pages:
    """(1-based page number, text) for every page; a page without a text layer gives ""."""
    with pdfplumber.open(pdf) as doc:
        return [(number, page.extract_text() or "") for number, page in enumerate(doc.pages, start=1)]


def low_density_pages(pages: Pages, min_chars: int) -> list[int]:
    """Page numbers whose extracted text is shorter than min_chars (likely scanned images)."""
    return [number for number, text in pages if len(text.strip()) < min_chars]


def needs_ocr(pages: Pages, min_chars: int, max_low_ratio: float) -> bool:
    """True when the document is empty or more than max_low_ratio of its pages are low-density."""
    return not pages or len(low_density_pages(pages, min_chars)) / len(pages) > max_low_ratio


class OcrEngine(Protocol):
    """OCR for one rendered PDF page."""

    def page_text(self, pdf: Path, page_no: int) -> tuple[str, float]:
        """Return (text, mean word confidence 0-100) for a 1-based page."""
        ...


class TesseractEngine:
    """pytesseract-backed OCR; an optional extra (pip install pytesseract + the tesseract binary)."""

    def __init__(self, resolution: int = 300) -> None:
        self.resolution = resolution

    def page_text(self, pdf: Path, page_no: int) -> tuple[str, float]:
        """Render the page and OCR it with Tesseract."""
        import pytesseract

        with pdfplumber.open(pdf) as doc:
            image = doc.pages[page_no - 1].to_image(resolution=self.resolution).original
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        confidences = [float(c) for word, c in zip(data["text"], data["conf"], strict=True) if str(word).strip()]
        confidences = [c for c in confidences if c >= 0]
        mean = sum(confidences) / len(confidences) if confidences else 0.0
        return str(pytesseract.image_to_string(image)), mean


@dataclass(frozen=True)
class OcrResult:
    """Pages with low-density pages replaced by OCR text, and whether the OCR is trustworthy enough."""

    pages: Pages
    confidence: float
    accepted: bool


def apply_ocr(pdf: Path, pages: Pages, engine: OcrEngine, min_chars: int, min_confidence: float) -> OcrResult:
    """OCR the low-density pages; reject the document when mean confidence is below min_confidence."""
    ocr = {number: engine.page_text(pdf, number) for number in low_density_pages(pages, min_chars)}
    confidence = sum(conf for _, conf in ocr.values()) / len(ocr) if ocr else 100.0
    merged = [(number, ocr[number][0] if number in ocr else text) for number, text in pages]
    return OcrResult(merged, confidence, confidence >= min_confidence)
