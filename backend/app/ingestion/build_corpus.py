"""Build data/processed/chunks.json and parse_report.md from the PDFs in data/raw_pdfs (indexes are built in M2)."""

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from backend.app.config import ActSpec, Settings, get_settings
from backend.app.ingestion.download import ManifestEntry, MissingPDFError, ensure_pdfs, sha256_file, update_manifest
from backend.app.ingestion.extract import (
    OcrEngine,
    TesseractEngine,
    apply_ocr,
    extract_pages,
    low_density_pages,
    needs_ocr,
)
from backend.app.ingestion.parse import parse_act
from backend.app.ingestion.report import ActReport, act_report, render_report
from backend.app.models import LegalChunk
from backend.app.retrieval.store import ChunkStore


@dataclass
class ActBuild:
    """Chunks, manifest fields and report notes produced for one Act."""

    chunks: list[LegalChunk] = field(default_factory=list)
    manifest: ManifestEntry = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def build_act(spec: ActSpec, pdf: Path, settings: Settings, ocr_engine: OcrEngine | None) -> ActBuild:
    """Extract, density-check, optionally OCR, then parse one Act."""
    pages = extract_pages(pdf)
    flagged = needs_ocr(pages, settings.ocr_min_page_chars, settings.ocr_max_low_page_ratio)
    low = low_density_pages(pages, settings.ocr_min_page_chars)
    build = ActBuild(
        manifest={"pages": len(pages), "low_density_pages": low, "needs_ocr": flagged, "ocr": "not_needed"}
    )
    if flagged and ocr_engine is None:
        build.manifest["ocr"] = "disabled"
        build.notes.append("needs_ocr: too little text; rerun with --ocr (optional extra, see docs/PARSING_NOTES.md)")
    elif flagged and ocr_engine is not None:
        result = apply_ocr(pdf, pages, ocr_engine, settings.ocr_min_page_chars, settings.ocr_min_confidence)
        build.manifest["ocr_confidence"] = round(result.confidence, 1)
        if not result.accepted:
            build.manifest["ocr"] = "excluded_low_confidence"
            build.notes.append(f"excluded: OCR confidence {result.confidence:.1f} < {settings.ocr_min_confidence}")
            return build
        build.manifest["ocr"] = "applied"
        build.notes.append(f"OCR applied to {len(low)} pages (confidence {result.confidence:.1f})")
        pages = result.pages
    build.chunks = parse_act(pages, spec, sha256_file(pdf))
    return build


def build_corpus(settings: Settings, ocr_engine: OcrEngine | None = None) -> list[ActReport]:
    """Parse every Act, write chunks.json, parse_report.md and the manifest; return the per-Act reports."""
    pdfs = ensure_pdfs(settings.acts, settings, offline=True)
    chunks: list[LegalChunk] = []
    reports: list[ActReport] = []
    manifest: dict[str, ManifestEntry] = {}
    for spec, pdf in zip(settings.acts, pdfs, strict=True):
        build = build_act(spec, pdf, settings, ocr_engine)
        chunks += build.chunks
        manifest[spec.slug] = build.manifest
        reports.append(act_report(spec, build.chunks, settings, build.notes))
    update_manifest(settings.manifest_path, manifest)
    ChunkStore(chunks).save(settings.chunks_path)
    settings.parse_report_path.parent.mkdir(parents=True, exist_ok=True)
    settings.parse_report_path.write_text(render_report(reports), encoding="utf-8")
    return reports


def main(
    argv: Sequence[str] | None = None, settings: Settings | None = None, ocr_engine: OcrEngine | None = None
) -> int:
    """CLI. Exit 0 on success, 1 when any Act parsed empty, 2 when PDFs are missing."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ocr", action="store_true", help="OCR low-text PDFs with Tesseract (optional extra)")
    args = parser.parse_args(argv)
    settings = settings or get_settings()
    if ocr_engine is None and (args.ocr or settings.ocr_enabled):
        ocr_engine = TesseractEngine()
    try:
        reports = build_corpus(settings, ocr_engine)
    except MissingPDFError as err:
        print(f"{err}. Put them in {settings.raw_pdf_dir} (names in data/sources.yaml).", file=sys.stderr)
        return 2
    failed = [r.name for r in reports if r.failed]
    total = sum(r.total for r in reports)
    print(f"{total} chunks from {len(reports)} Acts -> {settings.chunks_path}; report -> {settings.parse_report_path}")
    if failed:
        print(f"empty parse: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
