"""Labelled validity fields read from RC and driving-licence text.

Deterministic regular expressions over already-extracted text - not an NLP
model. Only a value that follows an explicit label is read ("Regn. Validity:
...", "Valid Till: ...", "Class of Vehicle: ..."); an unlabelled date is
never taken as a validity date, and nothing is inferred from a licence
number. Dates are read day-first, with the same parser as the accident-date
check (accident_consistency.parse_date).

These patterns also decide what claim_copy_retention keeps of a submitted
copy, so they are deliberately narrow.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from app.services.accident_consistency import _DATE, parse_date

# RC: "Regn. Validity: 19/07/2026", "Registration Valid Upto: ...", "Valid Upto: ...".
RC_VALIDITY = re.compile(
    rf"(?:(?:regn\.?|registration)\s*(?:validity|valid\s*(?:up\s*to|upto|till))|valid\s*up\s*to|validity\s*up\s*to)"
    rf"\s*[:\-]?\s*({_DATE})",
    re.IGNORECASE,
)
# Licence number in the Indian format SS RR YYYY NNNNNNN (spaces / hyphens optional).
LICENCE_NUMBER = re.compile(
    r"(?:licen[cs]e|\bD\.?L\.?)\s*(?:no\.?|number)\s*[:\-]?\s*([A-Z]{2}[ \-]?\d{2}[ \-]?\d{4}[ \-]?\d{7})\b",
    re.IGNORECASE,
)
# "Valid Till (Non-Transport): 09/03/2032", "Valid Upto (NT): ...", "Validity (NT): ...".
LICENCE_VALIDITY = re.compile(
    rf"(?:valid\s*(?:till|up\s*to|upto)|validity)\s*(?:\((?:non[\s\-]?transport|nt)\))?\s*[:\-]?\s*({_DATE})",
    re.IGNORECASE,
)
# "Class of Vehicle: LMV, MCWG" / "COV: LMV-NT" - the rest of that line only.
LICENCE_CLASS = re.compile(r"(?:class(?:es)?\s+of\s+vehicles?|\bCOV\b)\s*[:\-]?[ \t]*([^\n]+)", re.IGNORECASE)

RETAINED_FIELD_PATTERNS = (RC_VALIDITY, LICENCE_NUMBER, LICENCE_VALIDITY, LICENCE_CLASS)

_CLASS_TOKEN = re.compile(r"[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*")
_KNOWN_CLASSES = {
    "LMV", "LMV-NT", "LMV-TR", "MCWG", "MCWOG", "MC", "MCEX50CC", "MGV", "HMV", "HGMV", "HPMV", "HTV", "TRANS",
    "INVCRG", "TRCTOR", "E-RIKSHAW", "E-CART", "LMV-TRANS",
}


@dataclass
class RcFields:
    validity_dates: list[tuple[str, date]] = field(default_factory=list)  # (as written, parsed)


@dataclass
class LicenceFields:
    numbers: list[str] = field(default_factory=list)
    validity_dates: list[tuple[str, date]] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)  # normalised class codes, in order
    unparsed_dates: list[str] = field(default_factory=list)


def _dates(pattern: re.Pattern, text: str) -> tuple[list[tuple[str, date]], list[str]]:
    found, bad = [], []
    for match in pattern.finditer(text or ""):
        raw = match.group(1)
        parsed = parse_date(raw)
        if parsed is None:
            bad.append(raw)
        elif (raw, parsed) not in found:
            found.append((raw, parsed))
    return found, bad


def normalize_licence_number(raw: str) -> str:
    return re.sub(r"[ \-]+", "", raw).upper()


def extract_rc_fields(text: str | None) -> RcFields:
    dates, _ = _dates(RC_VALIDITY, text or "")
    return RcFields(validity_dates=dates)


def extract_licence_fields(text: str | None) -> LicenceFields:
    text = text or ""
    numbers = []
    for match in LICENCE_NUMBER.finditer(text):
        if match.group(1) not in numbers:
            numbers.append(match.group(1))
    dates, bad = _dates(LICENCE_VALIDITY, text)
    classes: list[str] = []
    for match in LICENCE_CLASS.finditer(text):
        for token in _CLASS_TOKEN.findall(match.group(1).upper()):
            if token in _KNOWN_CLASSES and token not in classes:
                classes.append(token)
    return LicenceFields(numbers=numbers, validity_dates=dates, classes=classes, unparsed_dates=bad)
