from __future__ import annotations

from pydantic import BaseModel


class EntityCandidateOut(BaseModel):
    """One best-effort candidate value - never a claimed certainty. See
    services/entity_extraction.py for the deterministic, regex-based
    method that produced it."""

    entity_type: str
    value: str
    normalized_value: str
    confidence: float
    source: str
    reason: str


class EntityExtractionResultOut(BaseModel):
    """Read-time only - never persisted. status is 'unavailable' for
    empty/missing text, 'no_candidates' when text exists but nothing
    matched, or 'extracted' when at least one candidate was found."""

    status: str
    entities: list[EntityCandidateOut]
    limitations: list[str]
