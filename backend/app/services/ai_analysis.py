"""Read-time aggregation of existing, already-computed AI/ML artifacts
for one claim (Step 5.8.10). This module computes nothing itself: it
only reads (a) the Step 5.4 risk-fusion research-prototype export
(services/risk_fusion_artifacts.py) and (b) the three dedicated
database tables the approved schema already provides for this purpose
(fraud_risk_analysis, cross_document_consistency, repair_estimates).

Human-in-the-loop: this module has no write path at all. It cannot
create, update, or delete a claim_decision_audit row, and it never
touches Claim.Final_Decision. See
docs/project_documentation/AI_BACKEND_INTEGRATION.md.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.crud import claim as crud_claim
from app.crud import cross_document_consistency as crud_consistency
from app.crud import fraud_risk_analysis as crud_fraud
from app.crud import repair_estimate as crud_repair_estimate
from app.db_models.cross_document_consistency import CrossDocumentConsistency
from app.db_models.fraud_risk_analysis import FraudRiskAnalysis
from app.db_models.repair_estimate import RepairEstimate
from app.schemas.ai_analysis import (
    AiClaimAnalysisOut,
    AiSignalOut,
    ConsistencyAnalysisOut,
    FraudAnalysisOut,
    RepairEstimateAnalysisOut,
)
from app.services import risk_fusion_artifacts

RISK_FUSION_DATA_SOURCE = (
    "Step 5.4 risk-fusion research prototype "
    "(ai_ml/experiments/run_risk_fusion_experiment.py) - a validation study on the "
    "current synthetic/de-identified dataset, not a measurement of real-world "
    "production accuracy."
)

# The FraudRiskAnalysis boolean columns, in the order they appear on the
# model - flagged (True) ones become this claim's fraud reason codes.
# Never a fabricated code: every entry here is a real column name from
# the approved schema.
_FRAUD_INDICATOR_FIELDS = [
    "Duplicate_Claim_Indicator",
    "Previous_Similar_Claim",
    "Suspicious_Garage_Indicator",
    "Claim_Immediately_After_Policy_Indicator",
    "Excessive_Claim_Amount_Indicator",
    "Document_Mismatch_Indicator",
    "Vehicle_Damage_Mismatch_Indicator",
    "Accident_Details_Mismatch_Indicator",
    "Evidence_Reuse_Indicator",
]

# The CrossDocumentConsistency per-field match columns - any value other
# than the real dataset's "Match" is surfaced as a contradiction, using
# the actual stored value, never an invented description.
_CONSISTENCY_MATCH_FIELDS = [
    "Customer_Statement_Match",
    "FIR_Match",
    "Surveyor_Report_Match",
    "Repair_Estimate_Match",
    "Accident_Date_Match",
    "Accident_Location_Match",
    "Vehicle_Details_Match",
    "Damage_Description_Match",
    "Claim_Amount_Match",
]


def _build_fraud_analysis(row: FraudRiskAnalysis | None) -> FraudAnalysisOut:
    if row is None:
        return FraudAnalysisOut(
            available=False,
            message="No fraud risk analysis has been generated for this claim.",
        )
    reason_codes = [field.upper() for field in _FRAUD_INDICATOR_FIELDS if getattr(row, field)]
    return FraudAnalysisOut(
        available=True,
        risk_category=row.Risk_Category,
        fraud_risk_score=row.Fraud_Risk_Score,
        anomaly_score=row.Anomaly_Score,
        overall_risk_score=row.Overall_Risk_Score,
        reason_codes=reason_codes,
    )


def _build_consistency_analysis(row: CrossDocumentConsistency | None) -> ConsistencyAnalysisOut:
    if row is None:
        return ConsistencyAnalysisOut(
            available=False,
            message="No cross-document consistency analysis has been generated for this claim.",
        )
    contradictions = [
        f"{field}: {getattr(row, field)}" for field in _CONSISTENCY_MATCH_FIELDS if getattr(row, field) != "Match"
    ]
    return ConsistencyAnalysisOut(
        available=True,
        overall_status=row.Overall_Consistency_Status,
        document_consistency_score=row.Document_Consistency_Score,
        contradictions=contradictions,
    )


def _is_unanalyzed_placeholder(row: RepairEstimate) -> bool:
    """True for the exact honest "not yet analyzed" placeholder
    services/repair_estimate_creation.py always writes (Step 5.8.7) -
    False/0.0000 there is a guaranteed non-prediction, not a genuine
    anomaly score of zero, so it must not be reported as available."""
    return row.Excessive_Claim_Amount_Indicator is False and row.Estimate_Anomaly_Score == 0


def _build_repair_estimate_analysis(rows: list[RepairEstimate]) -> RepairEstimateAnalysisOut:
    analyzed = [r for r in rows if not _is_unanalyzed_placeholder(r)]
    if not analyzed:
        message = (
            "No repair estimate has been submitted for this claim yet."
            if not rows
            else "A repair estimate exists but has not been analyzed yet "
            "(no leakage/anomaly-detection pipeline is connected - see "
            "SURVEYOR_REPAIR_ESTIMATE_WORKFLOW.md)."
        )
        return RepairEstimateAnalysisOut(available=False, message=message)

    row = analyzed[0]
    reason_codes = ["EXCESSIVE_CLAIM_AMOUNT_INDICATOR"] if row.Excessive_Claim_Amount_Indicator else []
    return RepairEstimateAnalysisOut(
        available=True,
        anomaly_detected=row.Excessive_Claim_Amount_Indicator,
        anomaly_score=row.Estimate_Anomaly_Score,
        reason_codes=reason_codes,
    )


def get_ai_analysis_for_claim(db: Session, claim_id: str) -> AiClaimAnalysisOut:
    claim = crud_claim.get(db, claim_id)
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")

    limitations = [
        "This is a research-prototype analysis validated only on a synthetic/de-identified "
        "dataset - see docs/project_documentation/AI_VS_NON_AI_RESULTS.md. It must not be "
        "treated as a measurement of real-world fraud-detection accuracy.",
    ]

    fusion = risk_fusion_artifacts.get_risk_fusion_result(claim_id)
    if fusion is None:
        overall_available = False
        overall_risk = None
        risk_score = None
        confidence_score = None
        confidence_band = None
        review_priority = None
        human_review_required = True
        contributing_signal_count = None
        unavailable_signal_count = None
        reason_codes: list[str] = []
        officer_explanations: list[dict] = []
        signals: list[AiSignalOut] = []
        explanation: list[str] = []
        limitations.append(
            "No AI risk-fusion result is available for this claim - it is outside the Step 5.4 "
            "research-prototype dataset (654 claims). This is expected for claims created "
            "through the live application, since the Step 5.4 export is a one-time static "
            "artifact, not a live-refreshing feed."
        )
    else:
        overall_available = True
        overall_risk = fusion["risk_band"]
        risk_score = fusion["overall_risk_score"]
        confidence_score = fusion["confidence_score"]
        confidence_band = fusion["confidence_band"]
        review_priority = fusion["review_priority"]
        human_review_required = fusion["human_review_required"]
        contributing_signal_count = fusion["contributing_signals"]
        unavailable_signal_count = fusion["unavailable_signals"]
        reason_codes = fusion["reason_codes"]
        officer_explanations = fusion["officer_explanations"]
        signals = [
            AiSignalOut(
                signal_name=s["signal_name"],
                category=s["category"],
                signal_value=s.get("signal_value"),
                availability=s["availability"],
                explanation=s["explanation"],
            )
            for s in fusion["signals"]
        ]
        explanation = list(fusion["explanation"])
        if not fusion["has_full_breakdown"]:
            limitations.append(
                "A full per-signal breakdown was only generated for 4 representative example "
                "claims in the Step 5.4 export - this claim has summary-level risk/confidence/"
                "reason-code data only."
            )

    fraud_rows = crud_fraud.list_by_claim(db, claim_id)
    consistency_rows = crud_consistency.list_by_claim(db, claim_id)
    repair_rows = crud_repair_estimate.list_by_claim(db, claim_id)

    return AiClaimAnalysisOut(
        claim_id=claim_id,
        available=overall_available,
        overall_risk=overall_risk,
        risk_score=risk_score,
        confidence_score=confidence_score,
        confidence_band=confidence_band,
        review_priority=review_priority,
        contributing_signal_count=contributing_signal_count,
        unavailable_signal_count=unavailable_signal_count,
        human_review_required=human_review_required,
        fraud_analysis=_build_fraud_analysis(fraud_rows[0] if fraud_rows else None),
        consistency_analysis=_build_consistency_analysis(consistency_rows[0] if consistency_rows else None),
        repair_estimate_analysis=_build_repair_estimate_analysis(repair_rows),
        reason_codes=reason_codes,
        officer_explanations=officer_explanations,
        signals=signals,
        explanation=explanation,
        limitations=limitations,
        data_source=RISK_FUSION_DATA_SOURCE,
    )
