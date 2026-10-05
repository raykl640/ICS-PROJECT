"""Tiny synthetic corpus shared by the index tests. All text is invented; none of it is statute text."""

from backend.app.models import LegalChunk, UnitType

EMPLOYMENT = "sample-employment-act"
TENANCY = "sample-tenancy-act"
CONSTITUTION = "sample-constitution"
_ACTS = {EMPLOYMENT: "Sample Employment Act", TENANCY: "Sample Tenancy Act", CONSTITUTION: "Sample Constitution"}

# Long section: filler about record keeping, with one distinctive passage near the end (lands only in the last window).
LONG_TAIL = "pension ledger audit by the zebra committee"
_FILLER = "The employer shall keep records of service for every employee and produce them on request. " * 25
LONG_TEXT = f"{_FILLER}Finally the {LONG_TAIL} shall happen yearly."


def make_chunk(
    act_slug: str,
    num: str,
    title: str,
    text: str,
    *,
    unit_type: UnitType = "section",
    repealed: bool = False,
) -> LegalChunk:
    """Build a valid LegalChunk with an id derived like the parser's."""
    suffix = num.lower().replace(" ", "-") if unit_type != "schedule" else "sch1"
    return LegalChunk(
        chunk_id=f"{act_slug}-{suffix}",
        act=_ACTS[act_slug],
        act_slug=act_slug,
        act_year=2000,
        unit_type=unit_type,
        section_num=num,
        section_title=title,
        text=text,
        page=1,
        repealed=repealed,
        source_sha256="0" * 64,
    )


def corpus() -> list[LegalChunk]:
    """Twenty-two chunks over three Acts: two repealed, one long (windowed), one schedule, section 41 in two Acts."""
    e, t, c = EMPLOYMENT, TENANCY, CONSTITUTION
    return [
        make_chunk(e, "1", "Interpretation", "In this Act words have the meanings assigned in this part."),
        make_chunk(e, "2", "Contracts of service", "A contract of service shall be in writing and signed by both."),
        make_chunk(
            e, "3", "Notice", "Either party may end a contract of service by giving one month notice in writing."
        ),
        make_chunk(
            e,
            "4",
            "Unfair termination",
            "A termination of employment by an employer is unfair where the employer fails to prove a valid reason "
            "and that a fair procedure was followed before the employee lost the job.",
        ),
        make_chunk(
            e, "5", "Annual leave", "An employee is entitled to twenty one days of paid annual leave each year."
        ),
        make_chunk(e, "6", "Payment of wages", "Wages shall be paid in legal tender at the end of each month."),
        make_chunk(e, "7", "Deleted provision", "[Repealed by Act No. 1 of 2001.]", repealed=True),
        make_chunk(
            e,
            "8",
            "Summary dismissal",
            (
                "Gross misconduct by an employee may justify summary dismissal, subject to the procedure in "
                "section 4 and Article 41 of the Sample Constitution."
            ),
        ),
        make_chunk(e, "9", "Sick leave", "An employee with a medical certificate is entitled to sick leave with pay."),
        make_chunk(e, "41", "Records of service", LONG_TEXT),
        make_chunk(
            t, "1", "Interpretation", "In this Act tenant means a person who occupies premises under a tenancy."
        ),
        make_chunk(t, "2", "Rent increases", "A landlord shall not increase rent without giving three months notice."),
        make_chunk(t, "3", "Eviction", "A landlord shall not evict a tenant from premises without an order of court."),
        make_chunk(t, "4", "Deposits", "A deposit paid by a tenant shall be refunded when the tenancy ends."),
        make_chunk(t, "5", "Repairs", "The landlord shall keep the premises in good and habitable repair."),
        make_chunk(t, "6", "Deleted provision", "[Repealed by Act No. 2 of 2002.]", repealed=True),
        make_chunk(
            t,
            "41",
            "Complaints",
            (
                "A tenant may lodge a complaint with the tribunal about any landlord, including a refusal under "
                "section 4 or an eviction contrary to section 6."
            ),
        ),
        make_chunk(
            c,
            "27",
            "Equality",
            "Every person is equal before the law and shall not suffer discrimination.",
            unit_type="article",
        ),
        make_chunk(
            c,
            "41",
            "Labour relations",
            "Every person has the right to fair labour practices and fair pay.",
            unit_type="article",
        ),
        make_chunk(
            c, "43", "Housing", "Every person has the right to accessible and adequate housing.", unit_type="article"
        ),
        make_chunk(
            c, "49", "Arrested persons", "An arrested person has the right to remain silent.", unit_type="article"
        ),
        make_chunk(
            c, "First Schedule", "Counties", "The counties are listed by name and number.", unit_type="schedule"
        ),
    ]
