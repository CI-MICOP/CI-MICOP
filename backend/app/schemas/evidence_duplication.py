from __future__ import annotations

from pydantic import BaseModel


class EvidenceMatchOut(BaseModel):
    evidence_id: str
    claim_id: str
    same_claim: bool
    match_type: str  # "EXACT" | "NEAR"
    hash_distance: int | None


class EvidenceDuplicationOut(BaseModel):
    evidence_id: str
    evidence_type: str
    file_name: str
    status: str  # "EXACT_DUPLICATE" | "NEAR_DUPLICATE" | "NO_MATCH_FOUND" | "UNAVAILABLE"
    matches: list[EvidenceMatchOut]
    explanation: str


class ClaimEvidenceDuplicationOut(BaseModel):
    """Response for POST /officer/claims/{claim_id}/evidence/duplication-check
    (Step 5.8.14 - see services/evidence_duplication.py and
    docs/project_documentation/EVIDENCE_DUPLICATION.md).

    Deliberately has no score or confidence field: the check reports which
    stored photos match and how, never a probability of wrongdoing."""

    Claim_ID: str
    photos_checked: int
    photos_compared_against: int
    results: list[EvidenceDuplicationOut]
    limitations: list[str]
