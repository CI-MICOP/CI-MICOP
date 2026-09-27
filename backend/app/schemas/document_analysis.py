from __future__ import annotations

from pydantic import BaseModel

from app.schemas.document_consistency import DocumentConsistencyOut
from app.schemas.entity_extraction import EntityExtractionResultOut


class DocumentCompletenessOut(BaseModel):
    """Deterministic, rule-based - never machine-learned. See
    services/document_analysis.py::calculate_claim_document_completeness."""

    available: bool
    required_document_types: list[str]
    present_document_types: list[str]
    missing_document_types: list[str]
    completeness_ratio: float | None
    explanation: str


class DocumentAnalysisOut(BaseModel):
    """Response for POST /documents/{document_id}/analyze. Never exposes
    the physical storage path - only metadata and the genuinely
    extracted/derived values."""

    Document_ID: str
    Document_Type: str
    extraction_status: str
    extracted_text: str
    ocr_confidence: float
    mismatch_indicator: bool
    completeness: DocumentCompletenessOut
    entities: EntityExtractionResultOut
    consistency: DocumentConsistencyOut
    limitations: list[str]


class ClaimDocumentAnalysisOut(BaseModel):
    """Response for POST /officer/claims/{claim_id}/documents/analyze."""

    Claim_ID: str
    documents_analyzed: int
    documents: list[DocumentAnalysisOut]
    completeness: DocumentCompletenessOut
    consistency: DocumentConsistencyOut
