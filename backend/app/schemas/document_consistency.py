from __future__ import annotations

from pydantic import BaseModel


class EntityConsistencyOut(BaseModel):
    """One deterministic MATCH/MISMATCH/UNAVAILABLE verdict for a single
    entity type. See services/document_consistency.py for the exact,
    documented candidate-resolution rule that produced it - never a
    probability, never a fraud verdict."""

    status: str  # "MATCH" | "MISMATCH" | "UNAVAILABLE"
    structured_value: str | None
    extracted_value: str | None
    matched_document_type: str | None
    matched_document_id: str | None
    explanation: str


class DocumentConsistencyOut(BaseModel):
    registration: EntityConsistencyOut
    policy: EntityConsistencyOut
