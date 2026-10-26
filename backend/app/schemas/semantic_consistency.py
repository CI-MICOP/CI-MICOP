from __future__ import annotations

from pydantic import BaseModel

from app.schemas.document_consistency import DocumentConsistencyOut, EntityConsistencyOut


class DocumentRefOut(BaseModel):
    document_id: str
    document_type: str


class SemanticConsistencyOut(BaseModel):
    """Response shape for the Step 5.8.13-C narrative-consistency RESEARCH
    PROTOTYPE - see services/semantic_consistency.py and
    docs/project_documentation/SEMANTIC_DOCUMENT_CONSISTENCY.md.

    confidence is always null in this prototype - no calibrated
    probability exists here, and a raw similarity score is never exposed
    labelled as one."""

    document_a: DocumentRefOut | None
    document_b: DocumentRefOut | None
    relationship: str  # "CONSISTENT" | "CONTRADICTION" | "INCONCLUSIVE"
    confidence: float | None
    explanation: str
    limitations: list[str]


class AccidentDetailsConsistencyOut(BaseModel):
    """Step 5.8.16 deterministic accident-detail checks - see
    services/accident_consistency.py. Same MATCH/MISMATCH/UNAVAILABLE shape
    as the registration/policy checks."""

    accident_date: EntityConsistencyOut
    fir_number: EntityConsistencyOut
    accident_time: EntityConsistencyOut  # Step 5.8.17


class ClaimSemanticConsistencyOut(BaseModel):
    """Response for POST /officer/claims/{claim_id}/documents/semantic-consistency.

    `narrative` (this step) and `deterministic` (Step 5.8.13-B, returned
    completely unmodified) are two SEPARATE dimensions and are never
    merged - a CONTRADICTION on one must never override or hide a MATCH on
    the other, or vice versa (Step 5.8.13-C brief, Section 9)."""

    Claim_ID: str
    narrative: SemanticConsistencyOut
    deterministic: DocumentConsistencyOut
    accident_details: AccidentDetailsConsistencyOut
    # RC / licence validity and policy cover on the accident date
    # (services/document_validity.py). Optional so older clients still parse.
    validity: "DocumentValidityOut | None" = None


class ValidityCheckOut(BaseModel):
    outcome: str  # services/verification_outcome.py
    explanation: str
    evidence: dict[str, str | None]
    limitations: list[str]


class DocumentValidityOut(BaseModel):
    rc_validity: ValidityCheckOut
    licence_number: ValidityCheckOut
    licence_validity: ValidityCheckOut
    licence_class: ValidityCheckOut
    policy_cover: ValidityCheckOut


ClaimSemanticConsistencyOut.model_rebuild()
