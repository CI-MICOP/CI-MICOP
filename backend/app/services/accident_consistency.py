"""Step 5.8.16: deterministic accident-detail consistency (roadmap item 6).

Compares two accident facts stated in a claim's documents with the claim's
own accident record (accidents table):
  - FIR number:    "FIR No: ..." in the FIR document vs Accident.FIR_Number
  - accident date: a LABELLED accident date ("Date of accident: ...",
                   "the accident occurred on ...") in the FIR and Survey
                   Report vs Accident.Accident_Date

Same spirit as Step 5.8.13-B (services/document_consistency.py): a
deterministic MATCH / MISMATCH / UNAVAILABLE verdict from explicit,
keyword-anchored text patterns - NOT fraud detection, NOT NLI, NOT a
confidence score. Kept in its own module so the shipped registration/policy
checks are untouched. See
docs/project_documentation/ACCIDENT_DETAIL_CONSISTENCY.md.

Read-time only: never writes to the database, never runs OCR (it only reads
Document.Extracted_Text already persisted by Step 5.8.12's analyze
endpoints), never touches Final_Decision, Approved_Amount or
claim_decision_audit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.crud import document as crud_document
from app.db_models.accident import Accident
from app.db_models.claim import Claim
from app.db_models.document import Document
from app.services.document_consistency import (
    STATUS_MATCH,
    STATUS_MISMATCH,
    STATUS_UNAVAILABLE,
    ConsistencyResult,
)

FIR_DOCUMENT_TYPES = ("FIR",)
DATE_DOCUMENT_TYPES = ("FIR", "Survey Report")

# ---------------------------------------------------------------------------
# FIR number
# ---------------------------------------------------------------------------

# A value right after an explicit FIR-number label. Requires a "No/Number/#"
# word so that the bare document title "FIR" or a sentence such as "FIR was
# lodged" is never read as a number, and at least one digit in the value
# (checked after matching). "/" is allowed because Indian FIR numbers are
# commonly written as serial/year, e.g. "123/2026".
_FIR_NUMBER = re.compile(
    r"(?:\bF\.?\s?I\.?\s?R\.?|first\s+information\s+report)\s*(?:no\.?|number|#)\s*[:\-]?\s*"
    r"([A-Za-z0-9][A-Za-z0-9/\-]{0,28}[A-Za-z0-9])",
    re.IGNORECASE,
)


def normalize_fir_number(raw: str) -> str:
    """Uppercase and drop spaces only - hyphens and slashes are part of the
    number itself and are kept."""
    return re.sub(r"\s+", "", raw).upper()


def extract_fir_numbers(text: str | None) -> list[str]:
    """Distinct FIR-number values (as written) found after an explicit label."""
    if not text:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for match in _FIR_NUMBER.finditer(text):
        raw = match.group(1)
        if not any(ch.isdigit() for ch in raw):
            continue
        normalized = normalize_fir_number(raw)
        if normalized not in seen:
            seen.add(normalized)
            found.append(raw)
    return found


# ---------------------------------------------------------------------------
# Accident date
# ---------------------------------------------------------------------------

_MONTHS = {
    name: index
    for index, names in enumerate(
        [
            ("jan", "january"), ("feb", "february"), ("mar", "march"), ("apr", "april"),
            ("may",), ("jun", "june"), ("jul", "july"), ("aug", "august"),
            ("sep", "sept", "september"), ("oct", "october"), ("nov", "november"), ("dec", "december"),
        ],
        start=1,
    )
    for name in names
}
_MONTH_WORD = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"

# Supported date shapes. Numeric day/month dates are read DAY-FIRST
# (dd/mm/yyyy), the Indian convention - never month-first.
_DATE = (
    r"(?:\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4}"  # 20/08/2026, 20-08-2026, 20.08.2026
    r"|\d{4}-\d{1,2}-\d{1,2}"  # 2026-08-20
    rf"|\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTH_WORD}\.?,?\s+\d{{4}}"  # 20 August 2026, 20th Aug 2026
    rf"|{_MONTH_WORD}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}})"  # August 20, 2026
)

# Only a date that is explicitly labelled as the accident/incident date is
# used. Unlabelled dates (report date, policy dates, inspection date) are
# deliberately ignored, so they can never be mistaken for the accident date.
_LABELLED_DATE = re.compile(
    r"(?:date\s+of\s+(?:the\s+)?(?:accident|incident|occurrence|collision)"
    r"|(?:accident|incident|collision)\s+date"
    r"|(?:accident|incident|collision)\s+(?:occurred|happened|took\s+place)\s+on)"
    rf"\s*[:\-]?\s*(?:on\s+)?({_DATE})",
    re.IGNORECASE,
)


def parse_date(raw: str) -> date | None:
    """Parse one of the supported shapes; None for anything impossible
    (e.g. 31/02/2026) rather than guessing."""
    text = raw.strip().lower().replace(",", " ")
    try:
        m = re.fullmatch(r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})", text)
        if m:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
        if m:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        m = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)\.?\s+(\d{4})", text)
        if m and m.group(2) in _MONTHS:
            return date(int(m.group(3)), _MONTHS[m.group(2)], int(m.group(1)))
        m = re.fullmatch(r"([a-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?\s+(\d{4})", text)
        if m and m.group(1) in _MONTHS:
            return date(int(m.group(3)), _MONTHS[m.group(1)], int(m.group(2)))
    except ValueError:
        return None
    return None


def extract_accident_dates(text: str | None) -> list[tuple[str, date]]:
    """(as written, parsed) for every distinct labelled accident date."""
    if not text:
        return []
    found: list[tuple[str, date]] = []
    seen: set[date] = set()
    for match in _LABELLED_DATE.finditer(text):
        parsed = parse_date(match.group(1))
        if parsed is not None and parsed not in seen:
            seen.add(parsed)
            found.append((match.group(1), parsed))
    return found


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

@dataclass
class AccidentConsistencyResult:
    accident_date: ConsistencyResult
    fir_number: ConsistencyResult


def _unavailable(structured_value: str | None, explanation: str) -> ConsistencyResult:
    return ConsistencyResult(
        status=STATUS_UNAVAILABLE,
        structured_value=structured_value,
        extracted_value=None,
        matched_document_type=None,
        matched_document_id=None,
        explanation=explanation,
    )


def _result(status, structured_value, extracted_value, document, explanation) -> ConsistencyResult:
    return ConsistencyResult(
        status=status,
        structured_value=structured_value,
        extracted_value=extracted_value,
        matched_document_type=document.Document_Type,
        matched_document_id=document.Document_ID,
        explanation=explanation,
    )


def compare_fir_number(reference: str | None, documents: list[Document]) -> ConsistencyResult:
    firs = [d for d in documents if d.Document_Type in FIR_DOCUMENT_TYPES]
    if not firs:
        return _unavailable(reference, "FIR number could not be compared because no FIR document exists for this claim.")

    pairs = [(value, d) for d in firs for value in extract_fir_numbers(d.Extracted_Text)]
    if not pairs:
        return _unavailable(
            reference,
            "FIR number could not be compared because no labelled FIR number (e.g. 'FIR No: ...') "
            "was found in this claim's FIR document text.",
        )
    if not reference:
        return _unavailable(None, "FIR number could not be compared because this claim has no FIR number on record.")

    normalized_reference = normalize_fir_number(reference)
    distinct = {normalize_fir_number(value) for value, _ in pairs}
    matching = next(((v, d) for v, d in pairs if normalize_fir_number(v) == normalized_reference), None)

    if matching and len(distinct) == 1:
        value, document = matching
        return _result(STATUS_MATCH, reference, value, document, "FIR number in the FIR document matches the accident record.")
    if matching:
        value, document = matching
        return _result(
            STATUS_MATCH, reference, value, document,
            "FIR number in the FIR document matches the accident record (other, different FIR numbers "
            "were also found in this claim's FIR document text).",
        )
    if len(distinct) == 1:
        value, document = pairs[0]
        return _result(STATUS_MISMATCH, reference, value, document, "FIR number in the FIR document does not match the accident record.")
    return _unavailable(
        reference,
        "FIR number could not be reliably compared - several different FIR numbers were found in this "
        "claim's FIR document text and none matches the accident record.",
    )


def compare_accident_date(reference: date | None, documents: list[Document]) -> ConsistencyResult:
    reference_text = reference.isoformat() if reference else None
    sources = [d for d in documents if d.Document_Type in DATE_DOCUMENT_TYPES]
    if not sources:
        return _unavailable(
            reference_text, "Accident date could not be compared because no FIR or Survey Report document exists for this claim."
        )

    stated = [(raw, parsed, d) for d in sources for raw, parsed in extract_accident_dates(d.Extracted_Text)]
    if not stated:
        return _unavailable(
            reference_text,
            "Accident date could not be compared because no labelled accident date (e.g. 'Date of accident: ...') "
            "was found in this claim's FIR or Survey Report text.",
        )
    if reference is None:
        return _unavailable(None, "Accident date could not be compared because this claim has no accident date on record.")

    differing = [(raw, parsed, d) for raw, parsed, d in stated if parsed != reference]
    if not differing:
        raw, _, document = stated[0]
        named = sorted({d.Document_Type for _, _, d in stated})
        return _result(
            STATUS_MATCH, reference_text, raw, document,
            f"Accident date stated in the {' and '.join(named)} matches the accident record.",
        )

    raw, parsed, document = differing[0]
    detail = "; ".join(f"{d.Document_Type} {d.Document_ID} states {p.isoformat()}" for _, p, d in differing)
    return _result(
        STATUS_MISMATCH, reference_text, raw, document,
        f"Accident date stated in this claim's documents does not match the accident record ({reference_text}): {detail}.",
    )


def compare_claim_accident_details(db: Session, claim: Claim) -> AccidentConsistencyResult:
    """Entry point routers should call. Read-only."""
    accident = db.query(Accident).filter(Accident.Claim_ID == claim.Claim_ID).order_by(Accident.Accident_ID).first()
    documents = crud_document.list_by_claim(db, claim.Claim_ID)
    if accident is None:
        missing = "this claim has no accident record on file"
        return AccidentConsistencyResult(
            accident_date=_unavailable(None, f"Accident date could not be compared because {missing}."),
            fir_number=_unavailable(None, f"FIR number could not be compared because {missing}."),
        )
    return AccidentConsistencyResult(
        accident_date=compare_accident_date(accident.Accident_Date, documents),
        fir_number=compare_fir_number(accident.FIR_Number, documents),
    )
