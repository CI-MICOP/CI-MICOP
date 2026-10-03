"""Step 5.8.13-C: semantic cross-document narrative-consistency RESEARCH
PROTOTYPE.

This is NOT fraud detection, NOT a fraud score, NOT a risk score, NOT an
automatic claim decision, and NOT a production-grade NLI system. It is a
narrow, deliberately small research prototype whose only job is to answer
one question: do this claim's FIR and Survey Report narrative texts state
the SAME accident location, a DIFFERENT one, or is there not enough usable
text to tell?

Why no NLI/embedding model is used here (see
docs/project_documentation/SEMANTIC_DOCUMENT_CONSISTENCY.md, Section
"Semantic Method" for the full reasoning): this repository has no
torch/transformers/sentence-transformers dependency anywhere (confirmed by
a repository-wide search before writing this module), and introducing one
for a single narrow comparison, with no real multi-document labelled
corpus to validate it against, would risk presenting an unvalidated
capability as if it worked. Cosine similarity between two sentences also
cannot, by itself, tell agreement from contradiction ("Gandhipuram" and
"Peelamedu" can be highly *similar* sentences about a highly *different*
fact) - so even if an embedding model were added, similarity alone would
not satisfy this step's actual requirement. Instead, this module reuses
the same style of narrow, deterministic, explainable extraction already
established by Step 5.8.13-A/B (services/entity_extraction.py,
services/document_consistency.py): it extracts an explicit, keyword-
anchored location mention from each document's already-extracted text and
compares the two extracted mentions directly. This IS a genuine
contradiction-capable method (an explicit disagreement between two
extracted values), not a similarity score mislabelled as one.

Read-time only: this module never writes to the database, never touches
cross_document_consistency (left untouched, same as Step 5.8.13-B), and
never runs OCR itself - it only reads whatever Document.Extracted_Text has
already been persisted by Step 5.8.12's analyze endpoints.

Kept entirely separate from services/document_consistency.py's
deterministic registration/policy MATCH/MISMATCH/UNAVAILABLE result - a
narrative CONTRADICTION here must never override, hide, or be merged with
a deterministic MATCH (or vice versa). Callers expose both, unmerged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.crud import document as crud_document
from app.db_models.claim import Claim
from app.db_models.document import Document

STATUS_CONSISTENT = "CONSISTENT"
STATUS_CONTRADICTION = "CONTRADICTION"
STATUS_INCONCLUSIVE = "INCONCLUSIVE"

# The one document-type pair this prototype supports (Step 5.8.13-C brief,
# Section 3: "keep the scope small... use two document types that actually
# exist in the project"). Both are genuine entries in this project's own
# live upload vocabulary (services/document_upload.py::ALLOWED_DOCUMENT_TYPES).
DOCUMENT_TYPE_A = "FIR"
DOCUMENT_TYPE_B = "Survey Report"

# Safety bound against pathological OCR output making the regex scan
# unboundedly slow - not a business rule, just a conservative cap. Well
# above any realistic single-page narrative section.
_MAX_COMPARISON_TEXT_CHARS = 5000

# Deliberately narrow and keyword-anchored (mirrors entity_extraction.py's
# own style): a capitalized token (or short capitalized phrase) following
# an explicit locative preposition. Requires the captured phrase to look
# like a proper noun (starts with an uppercase letter) specifically so
# this never fires on ordinary lowercase prepositional phrases such as
# "in an accident" or "at the scene".
#
# Step 5.8.17: the keyword itself may start with a capital letter, so a
# sentence that begins "At Anna Salai, ..." is recognised (validation case
# V12). Only the first letter of the keyword is case-insensitive - the place
# must still start with a capital letter.
_LOCATION_KEYWORD = re.compile(r"\b(?:[Nn]ear|[Aa]t|[Ii]n|[Cc]lose to)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})")

# Step 5.8.17: day and month names are capitalised like place names, so they
# were captured as places ("in March" -> a second location, case V15) or
# stuck to the end of one ("near Anna Salai Monday", case V17). They are
# removed from the end of a captured phrase, and a phrase made only of them
# is ignored.
_CALENDAR_WORDS = frozenset(
    "monday tuesday wednesday thursday friday saturday sunday "
    "january february march april may june july august september october november december".split()
)

_STANDARD_LIMITATIONS = [
    "This is a narrow, deterministic RESEARCH PROTOTYPE, not a general-purpose "
    "NLI/semantic-entailment model - no embedding, transformer, or sentence-similarity "
    "model is used anywhere in this module.",
    "The only contradiction-capable signal implemented is an explicit stated-location "
    "comparison - it cannot detect disagreement in dates, fault, sequence of events, "
    "injuries, or any other narrative fact.",
    "It has not been validated against a representative corpus of real accident "
    "narratives - only against controlled test text and the limited genuine documents "
    "available in this development environment.",
]


@dataclass
class DocumentRef:
    document_id: str
    document_type: str


@dataclass
class LocationCandidate:
    raw: str
    normalized: str


@dataclass
class SemanticConsistencyResult:
    document_a: DocumentRef | None
    document_b: DocumentRef | None
    relationship: str  # "CONSISTENT" | "CONTRADICTION" | "INCONCLUSIVE"
    confidence: float | None  # always None - no calibrated probability exists in this prototype
    explanation: str
    limitations: list[str]


def normalize_location(raw: str) -> str:
    """Uppercase, strip punctuation, collapse whitespace. Deliberately
    conservative (Step 5.8.13-C brief, Section 8): the place name itself
    is never altered beyond case/punctuation/whitespace - mirrors
    entity_extraction.py's own normalize_registration/normalize_policy
    convention, applied here to locations instead of identifiers."""
    cleaned = re.sub(r"[^\w\s]", "", raw)
    collapsed = re.sub(r"\s+", " ", cleaned).strip()
    return collapsed.upper()


def _extract_location_candidates(text: str | None) -> list[LocationCandidate]:
    if not text:
        return []
    bounded = text[:_MAX_COMPARISON_TEXT_CHARS]
    candidates: list[LocationCandidate] = []
    seen: set[str] = set()
    for match in _LOCATION_KEYWORD.finditer(bounded):
        words = match.group(1).split()
        while words and words[-1].lower() in _CALENDAR_WORDS:
            words.pop()
        raw = " ".join(words)
        normalized = normalize_location(raw)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        candidates.append(LocationCandidate(raw=raw, normalized=normalized))
    return candidates


def _resolve_single_location(text: str | None) -> LocationCandidate | None:
    """Returns the one distinct location mention found in this text, or
    None if zero or more than one distinct location is mentioned.
    Ambiguity (more than one candidate) is reported as INCONCLUSIVE, never
    guessed at - the same no-fabricated-certainty rule
    document_consistency.py already applies to disagreeing entity
    candidates."""
    candidates = _extract_location_candidates(text)
    if len(candidates) == 1:
        return candidates[0]
    return None


def _has_usable_text(document: Document | None) -> bool:
    return document is not None and bool(document.Extracted_Text) and bool(document.Extracted_Text.strip())


def _select_document_pair(documents: list) -> tuple:
    """Deterministic pairing rule (Step 5.8.13-C brief, Section 7): the
    MOST RECENTLY SUBMITTED FIR and the most recently submitted Survey
    Report on the claim (Document_Submitted_Date descending, ties broken
    by Document_ID descending) - deliberately NOT "the first one found".

    An ascending-ID rule was tried first and rejected after manual
    validation against the real development claim DEV-CLM-001 concretely
    demonstrated why it fails: that claim carries a hand-seeded placeholder
    FIR row (Document_ID="DEV-DOC-001", generic filler text, no physical
    file behind it) whose ID sorts alphabetically before every genuinely
    uploaded document's generated ID ("DEV-..." < "DOC-..."). Under an
    ascending rule, this placeholder would be selected forever, no matter
    how many real FIR documents were uploaded afterward - silently making
    every comparison meaningless. Preferring the most recently submitted
    document instead avoids that failure mode and matches how a Claims
    Officer would expect a resubmitted/corrected document to take
    precedence over an older one. If multiple documents of either type
    exist, every one except the most recent is deliberately ignored rather
    than arbitrarily comparing every possible pair."""

    def _sort_key(d):
        return (d.Document_Submitted_Date, d.Document_ID)

    firs = sorted((d for d in documents if d.Document_Type == DOCUMENT_TYPE_A), key=_sort_key, reverse=True)
    surveys = sorted((d for d in documents if d.Document_Type == DOCUMENT_TYPE_B), key=_sort_key, reverse=True)
    return (firs[0] if firs else None, surveys[0] if surveys else None)


def _document_ref(document) -> DocumentRef | None:
    if document is None:
        return None
    return DocumentRef(document_id=document.Document_ID, document_type=document.Document_Type)


def compare_narrative(document_a, document_b) -> SemanticConsistencyResult:
    """Core comparison. document_a/document_b are expected to be a FIR and
    a Survey Report (in that order) - this function itself does not
    enforce document type, only presence/usability of text; callers
    (compare_claim_narrative) are responsible for selecting the right
    pair via _select_document_pair. Only ever compares two documents
    already known to belong to the same claim - never fetches or accepts
    a document from another claim."""
    ref_a = _document_ref(document_a)
    ref_b = _document_ref(document_b)

    if document_a is None or document_b is None:
        missing = DOCUMENT_TYPE_A if document_a is None else DOCUMENT_TYPE_B
        return SemanticConsistencyResult(
            document_a=ref_a,
            document_b=ref_b,
            relationship=STATUS_INCONCLUSIVE,
            confidence=None,
            explanation=f"This claim has no {missing} document available for narrative comparison.",
            limitations=list(_STANDARD_LIMITATIONS),
        )

    if not _has_usable_text(document_a) or not _has_usable_text(document_b):
        empty_side = document_a.Document_Type if not _has_usable_text(document_a) else document_b.Document_Type
        return SemanticConsistencyResult(
            document_a=ref_a,
            document_b=ref_b,
            relationship=STATUS_INCONCLUSIVE,
            confidence=None,
            explanation=(
                "The available document text is insufficient for a reliable semantic comparison "
                f"({empty_side} has no extracted text yet)."
            ),
            limitations=list(_STANDARD_LIMITATIONS),
        )

    location_a = _resolve_single_location(document_a.Extracted_Text)
    location_b = _resolve_single_location(document_b.Extracted_Text)

    if location_a is None or location_b is None:
        return SemanticConsistencyResult(
            document_a=ref_a,
            document_b=ref_b,
            relationship=STATUS_INCONCLUSIVE,
            confidence=None,
            explanation=(
                "The available document text is insufficient for a reliable semantic comparison - "
                "no single, unambiguous accident-location mention could be found in one or both documents."
            ),
            limitations=list(_STANDARD_LIMITATIONS),
        )

    if location_a.normalized == location_b.normalized:
        return SemanticConsistencyResult(
            document_a=ref_a,
            document_b=ref_b,
            relationship=STATUS_CONSISTENT,
            confidence=None,
            explanation=(
                f"The {document_a.Document_Type} and {document_b.Document_Type} describe the accident as "
                f"occurring at the same stated location ({location_a.raw})."
            ),
            limitations=list(_STANDARD_LIMITATIONS),
        )

    return SemanticConsistencyResult(
        document_a=ref_a,
        document_b=ref_b,
        relationship=STATUS_CONTRADICTION,
        confidence=None,
        explanation=(
            f"The {document_a.Document_Type} states {location_a.raw} as the accident location, while the "
            f"{document_b.Document_Type} states {location_b.raw}. Document inconsistency identified for "
            "officer review."
        ),
        limitations=list(_STANDARD_LIMITATIONS),
    )


def compare_claim_narrative(db: Session, claim: Claim) -> SemanticConsistencyResult:
    """Entry point routers should call. Only compares documents belonging
    to THIS claim (loaded via crud_document.list_by_claim, the same
    claim-scoped query every other analysis service in this codebase
    uses) - never across claims. Read-only and comparison-only: has no
    access to, and never touches, Claim.Final_Decision,
    Claim.Approved_Amount, or claim_decision_audit."""
    documents = crud_document.list_by_claim(db, claim.Claim_ID)
    document_a, document_b = _select_document_pair(documents)
    return compare_narrative(document_a, document_b)
