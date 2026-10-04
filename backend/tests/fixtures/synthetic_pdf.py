"""Write small synthetic statute PDFs with reportlab; the repo never holds real statute text."""

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

_LEFT = 40
_TOP_MARGIN = 40
_LINE_HEIGHT = 13


def write_pdf(path: Path, pages: list[list[str]]) -> Path:
    """One PDF page per inner list, one text line per string; byte-identical on every run."""
    pdf = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    _, height = A4
    for lines in pages:
        pdf.setFont("Helvetica", 9)
        for i, line in enumerate(lines):
            pdf.drawString(_LEFT, height - _TOP_MARGIN - i * _LINE_HEIGHT, line)
        pdf.showPage()
    pdf.save()
    return path


# A small Act exercising every hygiene rule: cover, TOC, running header, footer page numbers, wrapped Part title,
# editorial notes, a repealed section, subsections, a compound hyphen, a two-page section, a cross-heading, Schedules.
SAMPLE_ACT_PAGES: list[list[str]] = [
    ["LAWS OF KENYA", "THE SAMPLE ACT", "CAP. 999"],
    [
        "Sample Act (Cap. 999)",
        "Contents",
        "Part I – PRELIMINARY ........................................ 1",
        "1. Short title ........................................ 1",
        "2. Interpretation ........................................ 1",
        "3. [Repealed by Act No. 1 of 2015, s. 4.] ........................................ 1",
        "Part II – RIGHTS AND DUTIES OF EMPLOYERS ........................................ 1",
        "4. Rights of workers ........................................ 1",
        "5. Notice of termination ........................................ 2",
    ],
    [
        "Sample Act (Cap. 999) Kenya",
        "An Act of Parliament to provide for sample matters",
        "Part I – PRELIMINARY",
        "1. Short title",
        "This Act may be cited as the Sample Act.",
        "2. Interpretation",
        "In this Act, unless the context otherwise requires—",
        "“employer” means a person who employs another person under a contract",
        "of service;",
        "“worker” means a person employed for wages.",
        "[Act No. 5 of 2010, s. 2, Act No. 7 of",
        "2012, s. 3.]",
        "3. [Repealed by Act No. 1 of 2015, s. 4.]",
        "Part II – RIGHTS AND DUTIES OF",
        "EMPLOYERS",
        "4. Rights of workers",
        "(1) Every worker has the right to fair treatment and the co-",
        "operation of the employer in all matters.",
        "(2) An employer shall—",
        "(a) pay wages on time; and",
        "(b) keep records, including—",
        "(i) hours worked; and",
        "(ii) leave taken.",
        "1",
    ],
    [
        "Sample Act (Cap. 999) Kenya",
        "(3) The records shall be kept for five years.",
        "1. Introduction",
        "2. Background",
        "The list above is illustrative only.",
        "Termination Generally",
        "5. Notice of termination",
        "An employer shall give a worker at least twenty-eight days’ written notice of termination.",
        "2",
    ],
    [
        "Sample Act (Cap. 999) Kenya",
        "SCHEDULE [s. 4]",
        "FORMS OF NOTICE",
        "1. Form of notice to a worker",
        "2. Form of notice to the labour officer",
        "SECOND SCHEDULE [s. 5]",
        "REPEALED",
        "Repealed by Act No. 1 of 2015, s. 9.",
        "3",
    ],
]
