"""Response schema for POST /officer/claims/{claim_id}/ai-analysis/run
(Step 5.8.11). Read-only/analyze-only: nothing here is ever accepted as
request input beyond the claim_id path parameter, and nothing in this
module writes to the database. See
docs/project_documentation/LIVE_AI_PIPELINE.md.
"""

from pydantic import BaseModel


class EvidenceSummaryOut(BaseModel):
    """Real, counted evidence available for this claim right now - never
    estimated or assumed."""

    documents: int
    vehicle_damage: int
    evidence: int
    repair_estimates: int
    inspections: int


class LiveSignalOut(BaseModel):
    """One live-computed (or explicitly unavailable) signal. Mirrors the
    shape of ai_ml/risk_fusion/signal_schema.py's Signal dataclass -
    same fields, same meaning - so this is recognizable as the same
    methodology, not a new one."""

    signal_name: str
    category: str
    signal_value: float | None = None
    availability: str
    confidence: float | None = None
    explanation: str


class LiveAiAnalysisRunOut(BaseModel):
    """Result of one on-demand live AI analysis run. Never persisted -
    see LIVE_AI_PIPELINE.md, Section 6."""

    claim_id: str
    # False only when the live pipeline could not produce a reliable
    # combined signal (fewer than 2 of the 7 defined signal families were
    # computable) - mirrors ai_ml/risk_fusion/uncertainty.py's own
    # MIN_SIGNALS_FOR_ANY_CONFIDENCE threshold, not a new invented rule.
    available: bool
    # "insufficient_evidence" | "partial" - "partial" is the ceiling this
    # live pipeline can reach today, since 5 of 7 signal families have no
    # live computation path yet (see Section 4 of the docs) - "completed"
    # is never returned.
    status: str
    evidence_summary: EvidenceSummaryOut
    overall_risk_score: float | None = None
    risk_band: str | None = None
    confidence_score: float | None = None
    confidence_band: str | None = None
    uncertainty_reasons: list[str] = []
    signals: list[LiveSignalOut]
    limitations: list[str]
    methodology_source: str
