"""Which customer-submitted claim documents are kept, and what is kept of
the ones that are not.

The customer submits a copy of the RC, the driving licence and the
insurance policy with every claim. The insurer holds its own reference
records for these (the vehicles / policies tables), so the copy is needed
only to check the details printed on it - it is not kept as another
stored copy of a sensitive document:

  - services/document_upload.py reads the uploaded bytes into memory,
    extracts the text through a private temporary directory that is
    removed before the request returns (document_analysis.
    extract_document_bytes), and never writes the file to
    DOCUMENT_STORAGE_ROOT;
  - Document.Extracted_Text then holds only `verification_record(text)` -
    the label-and-value spans that the checks read: entity_extraction's
    registration and policy-number patterns, and document_fields' labelled
    RC validity date, licence number, licence validity date and licence
    classes (needed for the validity checks in document_validity). Names,
    addresses, dates of birth, issue dates and the rest of the document are
    dropped.

The Document row itself is still created, because claim completeness
(document_analysis.calculate_claim_document_completeness) counts it.
FIR, repair estimates, accident photos and survey reports are claim
evidence and are stored as before.
"""

from __future__ import annotations

from app.services import document_fields, entity_extraction

NOT_RETAINED_DOCUMENT_TYPES = frozenset({"Driving Licence", "RC", "Insurance Policy"})

# The exact patterns entity_extraction uses, so the kept spans re-extract to
# the same candidates (value, source and OCR-correction note) as the full text.
_VERIFICATION_PATTERNS = (
    entity_extraction._REG_STRICT,
    entity_extraction._REG_KEYWORD,
    entity_extraction._POLICY_STRICT,
    entity_extraction._POLICY_KEYWORD,
    *document_fields.RETAINED_FIELD_PATTERNS,
)


def is_copy_retained(document_type: str) -> bool:
    return document_type not in NOT_RETAINED_DOCUMENT_TYPES


def verification_record(text: str | None) -> str:
    """The parts of `text` the registration / policy-number checks read -
    every pattern match, overlapping matches merged, one per line, in
    document order. Empty when nothing matched."""
    if not text:
        return ""
    spans = sorted(match.span() for pattern in _VERIFICATION_PATTERNS for match in pattern.finditer(text))
    merged: list[list[int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return "\n".join(text[start:end].strip() for start, end in merged)
