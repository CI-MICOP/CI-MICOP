"""Response schema for GET /officer/claims/{claim_id}/ai-analysis
(Step 5.8.10). Read-only: nothing here is ever accepted as request input,
and nothing in this module writes to the database. See
docs/project_documentation/AI_BACKEND_INTEGRATION.md.
"""

from decimal import Decimal

from pydantic import BaseModel


class FraudAnalysisOut(BaseModel):
    """Sourced from the existing fraud_risk_analysis table - no model is
    executed here. `available=False` means no row exists for this claim,
    never a fabricated zero score."""

    available: bool
    risk_category: str | None = None
    fraud_risk_score: Decimal | None = None
    anomaly_score: Decimal | None = None
    overall_risk_score: Decimal | None = None
    reason_codes: list[str] = []
    message: str | None = None


class ConsistencyAnalysisOut(BaseModel):
    """Sourced from the existing cross_document_consistency table."""

    available: bool
    overall_status: str | None = None
    document_consistency_score: Decimal | None = None
    contradictions: list[str] = []
    message: str | None = None


class RepairEstimateAnalysisOut(BaseModel):
    """Sourced from the existing repair_estimates table's AI-adjacent
    columns (Excessive_Claim_Amount_Indicator, Estimate_Anomaly_Score).
    `available=False` also covers the case where the only stored value is
    the Step 5.8.7 "not yet analyzed" placeholder (False/0.0000) - that
    placeholder must never be presented as a genuine anomaly score of
    zero."""

    available: bool
    anomaly_detected: bool | None = None
    anomaly_score: Decimal | None = None
    reason_codes: list[str] = []
    message: str | None = None


class AiSignalOut(BaseModel):
    """One entry from the Step 5.4 risk-fusion per-signal breakdown -
    only ever populated for the 4 representative example claims that
    breakdown was generated for (see ai_ml/model_artifacts/
    risk_fusion_explanations/)."""

    signal_name: str
    category: str
    signal_value: float | None = None
    availability: str
    explanation: str


class AiClaimAnalysisOut(BaseModel):
    """Aggregates read-only, already-computed AI/ML artifacts for one
    claim: Step 5.4's risk-fusion research prototype (overall_risk /
    risk_score / confidence_score / signals / explanation) plus the three
    dedicated per-domain database tables (fraud_analysis /
    consistency_analysis / repair_estimate_analysis). Nothing here is
    computed live, retrained, or invented - see
    docs/project_documentation/AI_BACKEND_INTEGRATION.md."""

    claim_id: str
    # True only if the Step 5.4 risk-fusion export has a result for this
    # exact Claim_ID - see the module docstring on why this is False for
    # nearly every claim in the live database today.
    available: bool
    overall_risk: str | None = None
    risk_score: float | None = None
    confidence_score: float | None = None
    confidence_band: str | None = None
    review_priority: str | None = None
    contributing_signal_count: int | None = None
    unavailable_signal_count: int | None = None
    # Always populated (defaults True when no AI signal exists at all) -
    # mirrors the same human-in-the-loop-safe default already used by
    # services/claim_decision.py for a fresh claim_decision_audit row.
    human_review_required: bool
    fraud_analysis: FraudAnalysisOut
    consistency_analysis: ConsistencyAnalysisOut
    repair_estimate_analysis: RepairEstimateAnalysisOut
    # The risk-fusion layer's own reason codes (ai_ml/risk_fusion/reason_codes.py) -
    # populated whenever a risk-fusion result exists, regardless of
    # whether a full per-signal breakdown was also generated.
    reason_codes: list[str] = []
    # Officer-facing wording for each reason code (title/detail/severity) -
    # only populated for the 4 representative example claims that have a
    # full breakdown; otherwise the frontend falls back to the bare codes.
    officer_explanations: list[dict] = []
    signals: list[AiSignalOut] = []
    explanation: list[str] = []
    limitations: list[str] = []
    data_source: str
