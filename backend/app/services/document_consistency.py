"""Step 5.8.13-B: deterministic cross-document consistency checking.

This compares an already-extracted entity candidate (Step 5.8.13-A,
services/entity_extraction.py) against the claim's own structured
reference value (vehicles.Registration_Number / policies.Policy_Number).
It is explicitly NOT fraud detection, NOT NLI, NOT semantic similarity,
and NOT a confidence score - it is a deterministic MATCH/MISMATCH/
UNAVAILABLE verdict with a fixed, documented resolution rule (see
docs/project_documentation/DETERMINISTIC_DOCUMENT_CONSISTENCY.md).

Deliberately reuses entity_extraction.normalize_registration/
normalize_policy rather than re-implementing normalization - a second,
possibly-diverging normalization implementation would risk two identical
identifiers being judged unequal (or vice versa) depending on which code
path produced them.

Read-time only: this module never writes to the database, never touches
cross_document_consistency (that table cannot represent this result
without losing provenance - see the docs, Section 7 - so it is left
untouched), and never runs OCR itself - it only reads whatever
Document.Extracted_Text/OCR_Confidence_Score has already been persisted by
Step 5.8.12's analyze endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.crud import document as crud_document
from app.crud import policy as crud_policy
from app.crud import vehicle as crud_vehicle
from app.db_models.claim import Claim
from app.db_models.document import Document
from app.services import entity_extraction

STATUS_MATCH = "MATCH"
STATUS_MISMATCH = "MISMATCH"
STATUS_UNAVAILABLE = "UNAVAILABLE"

# The one document type treated as a reliable source for each entity -
# deliberately narrow (Step 5.8.13-B brief, Section 4): "only use other
# document types if the existing extraction/audit clearly supports them."
# No such evidence exists for any other type, so comparison is restricted
# to exactly these two - unlike entity_extraction.py itself, which still
# scans every document type (just without a confidence boost).
_RELEVANT_DOCUMENT_TYPE = {
    entity_extraction.REGISTRATION_NUMBER: "RC",
    entity_extraction.POLICY_NUMBER: "Insurance Policy",
}
_ENTITY_LABEL = {
    entity_extraction.REGISTRATION_NUMBER: "Registration number",
    entity_extraction.POLICY_NUMBER: "Policy number",
}
_NORMALIZE = {
    entity_extraction.REGISTRATION_NUMBER: entity_extraction.normalize_registration,
    entity_extraction.POLICY_NUMBER: entity_extraction.normalize_policy,
}


@dataclass
class ConsistencyResult:
    status: str
    structured_value: str | None
    extracted_value: str | None
    matched_document_type: str | None
    matched_document_id: str | None
    explanation: str


@dataclass
class ClaimConsistencyResult:
    registration: ConsistencyResult
    policy: ConsistencyResult


def _unavailable(structured_value: str | None, matched_document_type: str | None, explanation: str) -> ConsistencyResult:
    return ConsistencyResult(
        status=STATUS_UNAVAILABLE,
        structured_value=structured_value,
        extracted_value=None,
        matched_document_type=matched_document_type,
        matched_document_id=None,
        explanation=explanation,
    )


def _candidate_document_pairs(documents: list[Document], entity_type: str) -> list[tuple]:
    """(candidate, document) pairs across every relevant document's
    ALREADY-PERSISTED Extracted_Text - this never re-runs OCR/extraction,
    it only re-reads what Step 5.8.12 already wrote to the Document row."""
    pairs = []
    for document in documents:
        ocr_confidence = float(document.OCR_Confidence_Score) if document.OCR_Confidence_Score is not None else None
        result = entity_extraction.extract_entities(
            document.Extracted_Text, document_type=document.Document_Type, ocr_confidence=ocr_confidence
        )
        for candidate in result.entities:
            if candidate.entity_type == entity_type:
                pairs.append((candidate, document))
    return pairs


def _compare_entity(entity_type: str, structured_reference: str | None, documents: list[Document]) -> ConsistencyResult:
    label = _ENTITY_LABEL[entity_type]
    target_type = _RELEVANT_DOCUMENT_TYPE[entity_type]
    normalize = _NORMALIZE[entity_type]

    relevant_documents = [d for d in documents if d.Document_Type == target_type]
    if not relevant_documents:
        return _unavailable(
            structured_reference, None,
            f"{label} could not be compared because no {target_type} document exists for this claim.",
        )

    pairs = _candidate_document_pairs(relevant_documents, entity_type)
    if not pairs:
        return _unavailable(
            structured_reference, target_type,
            f"{label} could not be compared because no usable entity was extracted from this claim's {target_type} document(s).",
        )

    if not structured_reference:
        return _unavailable(
            None, target_type,
            f"{label} could not be compared because this claim has no structured reference value on file.",
        )

    normalized_reference = normalize(structured_reference)
    distinct_values = {candidate.normalized_value for candidate, _ in pairs}

    def _pair_for(value: str):
        return next((candidate, document) for candidate, document in pairs if candidate.normalized_value == value)

    # Rule 1: every candidate across every relevant document agrees on one
    # value (the common case: exactly one candidate, or several documents/
    # candidates all producing the same normalized value) - compare it
    # directly against the structured reference.
    if len(distinct_values) == 1:
        candidate, document = _pair_for(next(iter(distinct_values)))
        if candidate.normalized_value == normalized_reference:
            return ConsistencyResult(
                status=STATUS_MATCH,
                structured_value=structured_reference,
                extracted_value=candidate.value,
                matched_document_type=document.Document_Type,
                matched_document_id=document.Document_ID,
                explanation=f"{label} extracted from {document.Document_Type} matches the insured record.",
            )
        return ConsistencyResult(
            status=STATUS_MISMATCH,
            structured_value=structured_reference,
            extracted_value=candidate.value,
            matched_document_type=document.Document_Type,
            matched_document_id=document.Document_ID,
            explanation=f"{label} extracted from {document.Document_Type} does not match the insured record.",
        )

    # Rule 2: candidates disagree with each other (multiple distinct
    # values, from one document with multiple candidates or several
    # documents). If exactly one of those distinct values equals the
    # structured reference, that is a genuine, explainable MATCH - the
    # correct value was found among the noise.
    if normalized_reference in distinct_values:
        candidate, document = _pair_for(normalized_reference)
        return ConsistencyResult(
            status=STATUS_MATCH,
            structured_value=structured_reference,
            extracted_value=candidate.value,
            matched_document_type=document.Document_Type,
            matched_document_id=document.Document_ID,
            explanation=(
                f"{label} extracted from {document.Document_Type} matches the insured record "
                "(other, non-matching candidates were also found in this claim's documents)."
            ),
        )

    # Rule 3: none of the disagreeing candidates match. This is only
    # reported as a MISMATCH (not UNAVAILABLE) when every candidate is
    # independently format-verified (source == "regex_strict_format") -
    # i.e. the evidence is "sufficiently explicit": several well-formed
    # values were found and none of them is the insured record. If even
    # one candidate came only from the weaker keyword-context fallback
    # (unverified shape), the disagreement is not explicit enough to call
    # a mismatch, so this is UNAVAILABLE instead - never fabricated
    # certainty out of ambiguous evidence.
    if all(candidate.source == "regex_strict_format" for candidate, _ in pairs):
        candidate, document = pairs[0]
        return ConsistencyResult(
            status=STATUS_MISMATCH,
            structured_value=structured_reference,
            extracted_value=candidate.value,
            matched_document_type=document.Document_Type,
            matched_document_id=document.Document_ID,
            explanation=(
                f"Multiple well-formed {label.lower()} values were extracted from this claim's "
                f"{target_type} document(s), and none matches the insured record."
            ),
        )

    return _unavailable(
        structured_reference, target_type,
        f"{label} could not be reliably compared - multiple disagreeing candidates were found in this "
        "claim's documents and at least one is a low-confidence, unverified-format candidate.",
    )


def compare_registration_number(db: Session, claim: Claim) -> ConsistencyResult:
    vehicle = crud_vehicle.get(db, claim.Vehicle_ID)
    structured_reference = vehicle.Registration_Number if vehicle else None
    documents = crud_document.list_by_claim(db, claim.Claim_ID)
    return _compare_entity(entity_extraction.REGISTRATION_NUMBER, structured_reference, documents)


def compare_policy_number(db: Session, claim: Claim) -> ConsistencyResult:
    policy = crud_policy.get(db, claim.Policy_ID)
    structured_reference = policy.Policy_Number if policy else None
    documents = crud_document.list_by_claim(db, claim.Claim_ID)
    return _compare_entity(entity_extraction.POLICY_NUMBER, structured_reference, documents)


def compare_claim_documents(db: Session, claim: Claim) -> ClaimConsistencyResult:
    """Bundles both comparisons - the single entry point routers should
    call. Analysis/comparison-only: has no access to, and never touches,
    Claim.Final_Decision, Claim.Approved_Amount, or claim_decision_audit."""
    return ClaimConsistencyResult(
        registration=compare_registration_number(db, claim),
        policy=compare_policy_number(db, claim),
    )
