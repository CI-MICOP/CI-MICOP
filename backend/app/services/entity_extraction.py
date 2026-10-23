"""Step 5.8.13-A: deterministic, regex-based entity-extraction foundation.

This is NOT an NLP model, NOT a general information-extraction system,
NOT a fraud detector, and NOT a consistency detector. It is a small,
explainable, rule-based utility that looks for two specific identifier
shapes inside already-extracted document text
(Document.Extracted_Text - see services/document_analysis.py, which this
module does not modify): vehicle registration numbers and policy numbers.

Every candidate's confidence comes from a fixed, documented rule tied to
*how* it was found (which regex matched, and whether the document's own
type is a strong context for that entity) - never a fabricated or
learned probability. See docs/project_documentation/ENTITY_EXTRACTION.md
for the full methodology and its limitations.

Read-time only: nothing here writes to the database. Cross-document
comparison (matching an extracted candidate against
vehicles.Registration_Number / policies.Policy_Number) is explicitly
Step 5.8.13-B's job, not this module's - see extract_entities' docstring.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Registration number
# ---------------------------------------------------------------------------

# The Indian motor-vehicle registration plate format actually used by this
# project's own live/dev-representative data (seed_dev_data.py:
# Registration_Number="TN01AB0001") - 2-letter state code, 1-2 digit RTO
# code, 1-3 letter series, 4-digit number, with or without a space/hyphen
# between each group. NOTE: the bulk offline synthetic dataset
# (03_vehicles.xlsx) does NOT follow this format - it contains
# unconstrained Faker-generated strings in many different shapes (e.g.
# "CV-8035", "MWP 189", "0AG J82") - that dataset is NOT used as the basis
# for this pattern; only the project's own real convention is targeted.
_REG_STRICT = re.compile(
    r"\b([A-Z]{2})[ -]?(\d{1,2})[ -]?([A-Z]{1,3})[ -]?(\d{4})\b",
    re.IGNORECASE,
)

# Weaker fallback: a value appearing right after a registration-related
# label, regardless of whether it matches the strict shape above. Requires
# at least one digit in the captured token (checked after matching) so
# plain words like "Registration Certificate" are never mistaken for a
# value. Deliberately excludes spaces from the captured token (unlike the
# strict pattern above) so it can never bleed into the next word of
# ordinary sentence text (e.g. "reg no TN-01-AB-0001 noted" must not
# capture "TN-01-AB-0001 n"). The compound "vehicle registration"/"vehicle
# reg" alternatives are listed BEFORE the bare "vehicle" one: without that
# ordering, "Vehicle Registration Number: X" would match "vehicle" alone at
# the first word and then wrongly capture the literal word "Registration"
# as if it were the value (regex alternation does not backtrack to find a
# "better" match elsewhere once one alternative lets the whole pattern
# succeed) - confirmed by a Step 5.8.13-B integration test that failed
# until this ordering was fixed.
#
# The digit requirement is also enforced inside the pattern, by the
# lookahead before the value: a match whose value has no digit (e.g. the
# second "Registration" in "Vehicle Registration\nRegistration No: X") would
# otherwise be consumed by finditer and then rejected, hiding the real
# "Registration No: X" label that it swallowed. The post-match digit check
# is kept as well.
_REG_KEYWORD = re.compile(
    r"(?:vehicle\s+registration|vehicle\s+reg\.?|registration|reg\.?|vehicle)\s*"
    r"(?:no\.?|number|#)?\s*[:\-]?\s*"
    r"(?=[A-Za-z0-9\-]{0,14}\d)([A-Za-z0-9][A-Za-z0-9\-]{3,13}[A-Za-z0-9])",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Policy number
# ---------------------------------------------------------------------------

# The one consistent policy-number convention actually present in this
# project's structured data (policies.Policy_Number, e.g. "POL-000001").
# This is a single observed convention, not a guaranteed universal format -
# see the docs for why this is treated as moderate, not high, confidence.
_POLICY_STRICT = re.compile(r"\bPOL[- ]?\d{6}\b", re.IGNORECASE)

# Weaker fallback: a value following a policy-related label. Requires at
# least one digit in the captured token so "Policy Type: Comprehensive" is
# never mistaken for a policy number. As with _REG_KEYWORD, the digit is
# required inside the pattern (lookahead) so that a title line such as
# "Insurance Policy" directly above "Policy No: X" cannot swallow the second
# "Policy" as a digit-less value and hide the real number.
_POLICY_KEYWORD = re.compile(
    r"policy\s*(?:no\.?|number|#)?\s*[:\-]?\s*(?=[A-Za-z0-9\-]{0,20}\d)([A-Za-z0-9][A-Za-z0-9\-]{3,19}[A-Za-z0-9])",
    re.IGNORECASE,
)

REGISTRATION_NUMBER = "registration_number"
POLICY_NUMBER = "policy_number"

# Document types where each entity is expected to genuinely appear - see
# services/document_upload.py::ALLOWED_DOCUMENT_TYPES for the exact live
# vocabulary. A document of any other type is still scanned (Section 7 of
# the Step 5.8.13 audit: "do not reject an otherwise plausible candidate
# solely because the document type is not ideal") - only the confidence
# boost below depends on this.
_STRONG_CONTEXT_DOCUMENT_TYPE = {
    REGISTRATION_NUMBER: "RC",
    POLICY_NUMBER: "Insurance Policy",
}
_CONTEXT_CONFIDENCE_BOOST = 0.05
_MAX_CONFIDENCE = 0.99

# Deterministic OCR-confidence rule (Step 5.8.13 instructions explicitly
# forbid converting OCR confidence into entity confidence without a
# documented rule): below this threshold, OCR text is likely to contain
# enough character-level errors to corrupt an identifier match, so every
# candidate's confidence is halved rather than trusted at face value.
_LOW_OCR_CONFIDENCE_THRESHOLD = 0.3
_LOW_OCR_CONFIDENCE_MULTIPLIER = 0.5

_STANDARD_LIMITATION = (
    "This is a deterministic, regex/rule-based extractor - not an NLP model, "
    "not a general information-extraction system, and not a fraud or "
    "consistency detector. It has not been validated for accuracy against a "
    "representative corpus of real uploaded insurance documents."
)


@dataclass
class EntityCandidate:
    entity_type: str
    value: str  # exactly as found in the text (before normalization)
    normalized_value: str
    confidence: float
    source: str  # "regex_strict_format" | "regex_keyword_context"
    reason: str
    # Set only when an OCR character correction was applied to reach
    # normalized_value (see correct_registration_ocr); explains it in words.
    correction: str | None = None


@dataclass
class EntityExtractionResult:
    status: str  # "unavailable" | "no_candidates" | "extracted"
    entities: list[EntityCandidate]
    limitations: list[str]


def normalize_registration(raw: str) -> str:
    """Uppercase, and collapse internal spaces/hyphens - the identifier
    itself is never altered beyond whitespace/case, per the no-aggressive-
    mutation rule; the original `value` is always preserved alongside this.

    Public (not module-private) so Step 5.8.13-B's document_consistency.py
    can normalize the structured vehicles.Registration_Number the exact
    same way before comparing it to an extracted candidate - see that
    module's docstring for why a second, possibly-diverging normalization
    implementation must not exist."""
    return re.sub(r"[ \-]+", "", raw).upper()


# --- OCR character correction for registration numbers ---------------------
#
# OCR often confuses the letter O with the digit 0 and the letter I with the
# digit 1 (e.g. "MHO2EM6629" for MH02EM6629). correct_registration_ocr()
# repairs this ONLY for a value already being read as a registration (a
# labelled keyword candidate) and only where the plate structure says which
# kind of character belongs in that position:
#   state code (2 letters) | RTO code (1-2 digits) | series (1-3 letters) | number (4 digits)
# It refuses whenever the evidence is not structural:
#   - the series must start and end with a letter that is not O/I/0/1, so a
#     confusable character can never decide where a part begins or ends;
#   - a 0/1 inside the series is never turned into O/I: Indian series letters
#     do not use I or O, so that would only invent an impossible series.
#     Digit-to-letter repair is therefore limited to the state code;
#   - exactly one reading may produce a valid plate;
#   - at most _MAX_OCR_CORRECTIONS characters may change;
#   - the corrected state code must be a real state/UT code.
# The trusted vehicle record is never passed through this function.

# State / union-territory codes used on Indian plates, including older codes
# still seen on existing vehicles (OR, UA, DD/DN before their mergers).
_STATE_CODES = frozenset({
    "AN", "AP", "AR", "AS", "BR", "CG", "CH", "DD", "DL", "DN", "GA", "GJ", "HP", "HR", "JH", "JK", "KA",
    "KL", "LA", "LD", "MH", "ML", "MN", "MP", "MZ", "NL", "OD", "OR", "PB", "PY", "RJ", "SK", "TN", "TR",
    "TS", "UA", "UK", "UP", "WB",
})
_AS_DIGIT = {"O": "0", "I": "1"}
_AS_LETTER = {"0": "O", "1": "I"}
_CONFUSABLE = frozenset("OI01")
_MAX_OCR_CORRECTIONS = 2


@dataclass
class RegistrationCorrection:
    corrected: str
    changes: list[str]  # human-readable, one per changed character


def correct_registration_ocr(normalized: str) -> RegistrationCorrection | None:
    """Position-aware O/0 and I/1 repair of an already-normalized value
    (see normalize_registration). Returns None when the value already has
    the plate structure, or when no single, structurally supported
    correction exists - the caller then keeps the value as read."""
    if _REG_STRICT.fullmatch(normalized):
        return None
    readings: dict[str, list[str]] = {}
    for rto_len in (1, 2):
        for series_len in (1, 2, 3):
            if 2 + rto_len + series_len + 4 != len(normalized):
                continue
            series = normalized[2 + rto_len: 2 + rto_len + series_len]
            if series[0] in _CONFUSABLE or series[-1] in _CONFUSABLE:
                continue
            # S = state code letter, D = digit, L = series letter (never repaired).
            layout = "S" * 2 + "D" * rto_len + "L" * series_len + "D" * 4
            chars, changes = [], []
            for position, (char, kind) in enumerate(zip(normalized, layout), start=1):
                if (kind == "D" and char.isdigit()) or (kind in "SL" and char.isalpha()):
                    chars.append(char)
                    continue
                swap = _AS_DIGIT.get(char) if kind == "D" else _AS_LETTER.get(char) if kind == "S" else None
                if swap is None:
                    break
                chars.append(swap)
                changes.append(
                    f"character {position} '{char}' read as the {'digit' if kind == 'D' else 'letter'} '{swap}'"
                )
            else:
                corrected = "".join(chars)
                if (changes and len(changes) <= _MAX_OCR_CORRECTIONS and corrected[:2] in _STATE_CODES
                        and _REG_STRICT.fullmatch(corrected)):
                    readings[corrected] = changes
    if len(readings) != 1:
        return None
    corrected, changes = next(iter(readings.items()))
    return RegistrationCorrection(corrected=corrected, changes=changes)


def normalize_policy(raw: str) -> str:
    """Uppercase and collapse whitespace only - hyphens are preserved
    since they are part of this project's own POL-XXXXXX convention.
    Public for the same reason as normalize_registration above."""
    collapsed = re.sub(r"\s+", " ", raw).strip()
    return collapsed.upper()


def _apply_context_boost(entity_type: str, confidence: float, document_type: str | None) -> float:
    if document_type and document_type == _STRONG_CONTEXT_DOCUMENT_TYPE.get(entity_type):
        return min(_MAX_CONFIDENCE, round(confidence + _CONTEXT_CONFIDENCE_BOOST, 4))
    return confidence


def _extract_registration_candidates(text: str, document_type: str | None) -> list[EntityCandidate]:
    candidates: list[EntityCandidate] = []
    seen_normalized: set[str] = set()

    for match in _REG_STRICT.finditer(text):
        raw = match.group(0)
        normalized = normalize_registration(raw)
        if normalized in seen_normalized:
            continue
        seen_normalized.add(normalized)
        confidence = _apply_context_boost(REGISTRATION_NUMBER, 0.90, document_type)
        candidates.append(
            EntityCandidate(
                entity_type=REGISTRATION_NUMBER,
                value=raw,
                normalized_value=normalized,
                confidence=confidence,
                source="regex_strict_format",
                reason=(
                    "Matches the Indian motor-vehicle registration format "
                    "(2 letters, 1-2 digit RTO code, 1-3 letter series, 4-digit number)."
                ),
            )
        )

    for match in _REG_KEYWORD.finditer(text):
        raw = match.group(1).strip()
        if not any(ch.isdigit() for ch in raw):
            continue
        normalized = normalize_registration(raw)
        # The label says this value is a registration, so a structurally
        # supported O/0, I/1 OCR repair may be applied; `raw` keeps the text
        # exactly as read, and the candidate stays a weak keyword candidate.
        correction = correct_registration_ocr(normalized)
        if correction:
            normalized = correction.corrected
        if normalized in seen_normalized:
            continue
        seen_normalized.add(normalized)
        confidence = _apply_context_boost(REGISTRATION_NUMBER, 0.40, document_type)
        note = (
            f"The document reads '{raw}'; read as a registration number, "
            f"{'; '.join(correction.changes)}, giving {correction.corrected}."
            if correction else None
        )
        candidates.append(
            EntityCandidate(
                entity_type=REGISTRATION_NUMBER,
                value=raw,
                normalized_value=normalized,
                confidence=confidence,
                source="regex_keyword_context",
                reason=(
                    "Found immediately after a registration/vehicle-number label. " + note
                    if note
                    else "Found immediately after a registration/vehicle-number label, but does not match the expected format."
                ),
                correction=note,
            )
        )

    return candidates


def _extract_policy_candidates(text: str, document_type: str | None) -> list[EntityCandidate]:
    candidates: list[EntityCandidate] = []
    seen_normalized: set[str] = set()

    for match in _POLICY_STRICT.finditer(text):
        raw = match.group(0)
        normalized = normalize_policy(raw)
        if normalized in seen_normalized:
            continue
        seen_normalized.add(normalized)
        confidence = _apply_context_boost(POLICY_NUMBER, 0.70, document_type)
        candidates.append(
            EntityCandidate(
                entity_type=POLICY_NUMBER,
                value=raw,
                normalized_value=normalized,
                confidence=confidence,
                source="regex_strict_format",
                reason="Matches this project's POL-XXXXXX policy-number convention.",
            )
        )

    for match in _POLICY_KEYWORD.finditer(text):
        raw = match.group(1).strip()
        if not any(ch.isdigit() for ch in raw):
            continue
        normalized = normalize_policy(raw)
        if normalized in seen_normalized:
            continue
        seen_normalized.add(normalized)
        confidence = _apply_context_boost(POLICY_NUMBER, 0.50, document_type)
        candidates.append(
            EntityCandidate(
                entity_type=POLICY_NUMBER,
                value=raw,
                normalized_value=normalized,
                confidence=confidence,
                source="regex_keyword_context",
                reason="Found immediately after a policy-number label, but does not match the project's known convention.",
            )
        )

    return candidates


def extract_entities(
    text: str | None,
    *,
    document_type: str | None = None,
    ocr_confidence: float | None = None,
) -> EntityExtractionResult:
    """Best-effort, deterministic extraction of a vehicle registration
    number and/or policy number from already-extracted document text.

    Does NOT compare results against any structured claim/vehicle/policy
    value - that is Step 5.8.13-B's job. This function only answers "what
    entities can be found in this text," never "does this match the claim."
    """
    if not text or not text.strip():
        return EntityExtractionResult(status="unavailable", entities=[], limitations=[_STANDARD_LIMITATION])

    entities = _extract_registration_candidates(text, document_type) + _extract_policy_candidates(text, document_type)

    limitations = [_STANDARD_LIMITATION]
    if ocr_confidence is not None and ocr_confidence < _LOW_OCR_CONFIDENCE_THRESHOLD:
        for entity in entities:
            entity.confidence = round(entity.confidence * _LOW_OCR_CONFIDENCE_MULTIPLIER, 4)
        limitations.append(
            f"OCR confidence for this document was below {_LOW_OCR_CONFIDENCE_THRESHOLD:.2f} - "
            "every candidate's confidence has been halved, since low-confidence OCR text is likely "
            "to contain character-level errors that corrupt an identifier match."
        )

    status = "extracted" if entities else "no_candidates"
    return EntityExtractionResult(status=status, entities=entities, limitations=limitations)
