"""Live claim AI analysis orchestration (Step 5.8.11).

This is the "NEW/LIVE CLAIM DATA -> AI processing -> AI result" pipeline
Step 5.8.10 did not provide (that step only read already-computed
artifacts/rows). Before writing this module, every AI/ML component in
`ai_ml/` was audited against the live PostgreSQL schema (see
docs/project_documentation/LIVE_AI_PIPELINE.md, Section 3) to determine
which of the 7 Step 5.4 risk-fusion signal families can be computed from
data that actually exists for a live claim, as opposed to data that only
ever existed in the offline synthetic research dataset or as Step
5.8.x's own honest "not yet analyzed" placeholders.

Conclusion (see the docs for the full audit table): only 2 of 7 signal
families are genuinely live-computable today -
`claim_pattern_anomaly` (claim-filed-vs-policy-start timing) and
`repair_estimate_anomaly` (repair-estimate/claim-amount ratio only, NOT
the Excessive_Claim_Amount_Indicator flag, which is always a placeholder
for a live estimate). The other 5 depend on document OCR, cross-document
consistency, or duplicate-evidence detection - none of which has a live
computation path anywhere in this codebase - and are always reported
explicitly unavailable, never fabricated from placeholder defaults.

The fusion/uncertainty math itself (`_fuse`, `_compute_uncertainty`) is
ported faithfully from `ai_ml/risk_fusion/fusion_engine.py` and
`ai_ml/risk_fusion/uncertainty.py` - same formulas, same thresholds,
using `statistics.pstdev` instead of `numpy` purely to avoid adding a
new backend dependency for a formula that does not need it. Nothing
about the methodology was altered. This is READ/ANALYZE-ONLY: it has no
write path, cannot touch Claim.Final_Decision/Approved_Amount, and does
not persist its result (see the docs, Section 6, for why).
"""

from __future__ import annotations

import statistics

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.crud import claim as crud_claim
from app.crud import document as crud_document
from app.crud import evidence as crud_evidence
from app.crud import policy as crud_policy
from app.crud import repair_estimate as crud_repair_estimate
from app.crud import surveyor_inspection as crud_inspection
from app.crud import vehicle_damage as crud_vehicle_damage
from app.db_models.claim import Claim
from app.schemas.ai_pipeline import EvidenceSummaryOut, LiveAiAnalysisRunOut, LiveSignalOut

METHODOLOGY_SOURCE = (
    "Signal/fusion/uncertainty formulas ported faithfully from the Step 5.4 risk-fusion "
    "research prototype (ai_ml/risk_fusion/signal_builder.py, fusion_engine.py, "
    "uncertainty.py) - same math, same thresholds, applied live to whichever signals this "
    "claim's actual data genuinely supports today. See "
    "docs/project_documentation/LIVE_AI_PIPELINE.md."
)

# Reference percentiles computed ONCE from the approved 654-claim training
# dataset (ai_ml/datasets/CI_MICOP_15_Tables_Complete/{05_claims,04_policies,
# 09_repair_estimates}.xlsx) using the exact same formula as
# ai_ml.risk_fusion.signal_builder.ReferenceStats.from_reference_population.
# Never recomputed from live data - that would leak the very claims being
# scored into their own normalization reference.
REPAIR_RATIO_P50 = 0.8360257578280614
REPAIR_RATIO_P90 = 2.974623089931217
EARLY_CLAIM_DAYS_P10 = 29.0
EARLY_CLAIM_DAYS_P50 = 157.5

# ai_ml.risk_fusion.uncertainty constants, ported unchanged.
TOTAL_DEFINED_SIGNALS = 7
MIN_SIGNALS_FOR_ANY_CONFIDENCE = 2
CONFIDENCE_BAND_THRESHOLDS = {"HIGH_CONFIDENCE": 0.70, "MEDIUM_CONFIDENCE": 0.45, "LOW_CONFIDENCE": 0.25}

# ai_ml.risk_fusion.fusion_engine.RISK_BAND_THRESHOLDS, ported unchanged.
RISK_BAND_THRESHOLDS = {"CRITICAL": 0.75, "HIGH": 0.50, "MEDIUM": 0.25}

# The 5 signal families this live pipeline cannot compute today, and
# exactly why - see this module's docstring and LIVE_AI_PIPELINE.md.
_UNAVAILABLE_SIGNAL_REASONS: dict[str, tuple[str, str]] = {
    "document_consistency_mismatch": (
        "DOCUMENT_CONSISTENCY",
        "No cross-document consistency analysis pipeline is connected to live claims yet - "
        "the cross_document_consistency table has no live-writing code path in this "
        "application (its only populated row today is a hand-seeded development example).",
    ),
    "evidence_duplication": (
        "EVIDENCE_DUPLICATION",
        "Duplicate-evidence detection is not connected to the live evidence upload pipeline - "
        "Evidence.Duplicate_Evidence_Indicator is always an honest 'not yet analyzed' "
        "placeholder for evidence uploaded through the live application.",
    ),
    "fraud_screening_rule_score": (
        "FRAUD_SCREENING",
        "The trained fraud model and the full rule-based screener both require inputs "
        "(document consistency, evidence duplication, document completeness) that have no "
        "live computation path yet. Running them on placeholder 'nothing detected' values "
        "would misrepresent every live claim as low-risk regardless of its true risk, so "
        "this signal is not computed live.",
    ),
    "document_completeness": (
        "DOCUMENT_COMPLETENESS",
        "OCR/document-completeness inference is not connected to the live document upload "
        "pipeline - Document.Document_Completeness is always an honest 'not yet analyzed' "
        "placeholder (0.0000) for documents uploaded through the live application.",
    ),
    "information_quality": (
        "INFORMATION_QUALITY",
        "OCR inference remains a research/prototype component and is not yet part of the "
        "live claim pipeline - Document.OCR_Confidence_Score, Evidence.Image_Quality, and "
        "Evidence.Evidence_Confidence_Score are always honest 'not yet analyzed' "
        "placeholders (0.0000) for live uploads.",
    ),
}


def _scale_between(value: float, low: float, high: float) -> float:
    """Identical to ai_ml.risk_fusion.signal_builder._scale_between."""
    if high <= low:
        return 0.0
    return float(min(max((value - low) / (high - low), 0.0), 1.0))


def _claim_timing_signal(claim: Claim, policy) -> LiveSignalOut:
    if policy is None or policy.Policy_Start_Date is None:
        return LiveSignalOut(
            signal_name="claim_pattern_anomaly",
            category="CLAIM_PATTERN_ANOMALY",
            availability="unavailable",
            explanation="Policy start date is unavailable for this claim - claim timing cannot be assessed.",
        )
    days = (claim.Claim_Date - policy.Policy_Start_Date).days
    value = 1.0 - _scale_between(days, EARLY_CLAIM_DAYS_P10, EARLY_CLAIM_DAYS_P50)
    return LiveSignalOut(
        signal_name="claim_pattern_anomaly",
        category="CLAIM_PATTERN_ANOMALY",
        signal_value=value,
        availability="available",
        confidence=1.0,
        explanation=(
            f"Claim filed {days} day(s) after policy start (reference 10th percentile "
            f"{EARLY_CLAIM_DAYS_P10:.0f}, median {EARLY_CLAIM_DAYS_P50:.0f})."
        ),
    )


def _repair_estimate_ratio_signal(claim: Claim, repair_estimates: list) -> LiveSignalOut:
    if not repair_estimates:
        return LiveSignalOut(
            signal_name="repair_estimate_anomaly",
            category="REPAIR_ESTIMATE_ANOMALY",
            availability="unavailable",
            explanation="No repair estimate has been submitted for this claim yet.",
        )
    estimate = repair_estimates[0]
    claim_amount = float(claim.Claim_Amount) if claim.Claim_Amount else None
    if not claim_amount:
        return LiveSignalOut(
            signal_name="repair_estimate_anomaly",
            category="REPAIR_ESTIMATE_ANOMALY",
            availability="unavailable",
            explanation="Claim amount is unavailable for this claim - the repair-estimate ratio cannot be computed.",
        )
    ratio = float(estimate.Repair_Estimate) / claim_amount
    value = _scale_between(ratio, REPAIR_RATIO_P50, REPAIR_RATIO_P90)
    return LiveSignalOut(
        signal_name="repair_estimate_anomaly",
        category="REPAIR_ESTIMATE_ANOMALY",
        signal_value=value,
        availability="available",
        confidence=1.0,
        explanation=(
            f"Repair-estimate/claim-amount ratio {ratio:.2f} (reference median {REPAIR_RATIO_P50:.2f}, "
            f"90th percentile {REPAIR_RATIO_P90:.2f}). The excessive-claim-amount flag on this repair "
            "estimate is not included: no leakage-detection pipeline is connected yet, so that flag is "
            "always an honest 'not yet analyzed' placeholder rather than a genuine prediction (see "
            "SURVEYOR_REPAIR_ESTIMATE_WORKFLOW.md)."
        ),
    )


def _unavailable_signal(signal_name: str) -> LiveSignalOut:
    category, reason = _UNAVAILABLE_SIGNAL_REASONS[signal_name]
    return LiveSignalOut(signal_name=signal_name, category=category, availability="unavailable", explanation=reason)


def _fuse(signals: list[LiveSignalOut]) -> tuple[float | None, str | None]:
    """Ports ai_ml.risk_fusion.fusion_engine.equal_weight_fusion exactly:
    equal weight per available signal, renormalized (with only one
    weight value, that renormalization is just an arithmetic mean)."""
    available = [s for s in signals if s.availability == "available" and s.signal_value is not None]
    if not available:
        return None, "UNSCORED"
    score = sum(s.signal_value for s in available) / len(available)
    score = min(max(score, 0.0), 1.0)
    if score >= RISK_BAND_THRESHOLDS["CRITICAL"]:
        band = "CRITICAL"
    elif score >= RISK_BAND_THRESHOLDS["HIGH"]:
        band = "HIGH"
    elif score >= RISK_BAND_THRESHOLDS["MEDIUM"]:
        band = "MEDIUM"
    else:
        band = "LOW"
    return score, band


def _compute_uncertainty(signals: list[LiveSignalOut]) -> tuple[float, str, list[str]]:
    """Ports ai_ml.risk_fusion.uncertainty.compute_uncertainty exactly
    (statistics.pstdev instead of numpy for the agreement term - no
    other behavioral change)."""
    available = [s for s in signals if s.availability == "available" and s.signal_value is not None]
    reasons: list[str] = []

    if len(available) < MIN_SIGNALS_FOR_ANY_CONFIDENCE:
        reasons.append(
            f"Only {len(available)}/{TOTAL_DEFINED_SIGNALS} signals available - fewer than the 2 "
            "required for any reliable confidence estimate."
        )
        return 0.0, "INSUFFICIENT_EVIDENCE", reasons

    if len(available) < TOTAL_DEFINED_SIGNALS:
        missing = [s.signal_name for s in signals if s not in available]
        reasons.append(
            f"Only {len(available)}/{TOTAL_DEFINED_SIGNALS} signals available (missing: {', '.join(missing)})."
        )

    values = [s.signal_value for s in available]
    agreement = 1.0 - (statistics.pstdev(values) if len(values) > 1 else 0.0)
    agreement = max(0.0, min(1.0, agreement))
    if agreement < 0.6:
        reasons.append(f"Available signals disagree with each other (agreement={agreement:.2f}).")

    signal_trust = sum(s.confidence for s in available) / len(available)
    confidence = (len(available) / TOTAL_DEFINED_SIGNALS) * agreement * signal_trust
    confidence = float(max(0.0, min(1.0, confidence)))

    if confidence >= CONFIDENCE_BAND_THRESHOLDS["HIGH_CONFIDENCE"]:
        band = "HIGH_CONFIDENCE"
    elif confidence >= CONFIDENCE_BAND_THRESHOLDS["MEDIUM_CONFIDENCE"]:
        band = "MEDIUM_CONFIDENCE"
    elif confidence >= CONFIDENCE_BAND_THRESHOLDS["LOW_CONFIDENCE"]:
        band = "LOW_CONFIDENCE"
    elif len(available) < TOTAL_DEFINED_SIGNALS:
        band = "INSUFFICIENT_EVIDENCE"
    else:
        band = "LOW_CONFIDENCE"

    if not reasons:
        reasons.append("All available signals agree; no specific uncertainty driver identified.")
    return confidence, band, reasons


def run_claim_ai_analysis(db: Session, claim_id: str) -> LiveAiAnalysisRunOut:
    claim = crud_claim.get(db, claim_id)
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")

    policy = crud_policy.get(db, claim.Policy_ID)
    documents = crud_document.list_by_claim(db, claim_id)
    damage = crud_vehicle_damage.list_by_claim(db, claim_id)
    evidence = crud_evidence.list_by_claim(db, claim_id)
    repair_estimates = crud_repair_estimate.list_by_claim(db, claim_id)
    inspections = crud_inspection.list_by_claim(db, claim_id)

    evidence_summary = EvidenceSummaryOut(
        documents=len(documents),
        vehicle_damage=len(damage),
        evidence=len(evidence),
        repair_estimates=len(repair_estimates),
        inspections=len(inspections),
    )

    signals = [
        _claim_timing_signal(claim, policy),
        _repair_estimate_ratio_signal(claim, repair_estimates),
        _unavailable_signal("document_consistency_mismatch"),
        _unavailable_signal("evidence_duplication"),
        _unavailable_signal("fraud_screening_rule_score"),
        _unavailable_signal("document_completeness"),
        _unavailable_signal("information_quality"),
    ]
    available_count = sum(1 for s in signals if s.availability == "available")

    confidence_score, confidence_band, uncertainty_reasons = _compute_uncertainty(signals)

    limitations = [
        "This is a research-prototype live pipeline validated only on a synthetic/de-identified "
        "dataset - see docs/project_documentation/AI_VS_NON_AI_RESULTS.md.",
        f"Only {available_count}/{TOTAL_DEFINED_SIGNALS} signal families defined by the Step 5.4 "
        "research prototype could be computed live for this claim. Document consistency, evidence "
        "duplication, document completeness, information quality/OCR, and fraud screening all "
        "require analysis pipelines that do not exist in this application yet - see "
        "docs/project_documentation/LIVE_AI_PIPELINE.md for exactly why.",
    ]

    if confidence_band == "INSUFFICIENT_EVIDENCE":
        overall_risk_score, risk_band = None, None
        available = False
        status_value = "insufficient_evidence"
        limitations.append(
            "Fewer than 2 signal families were computable for this claim, so no overall risk score is "
            "shown - a score built from a single weak signal would overstate what was actually analyzed."
        )
    else:
        overall_risk_score, risk_band = _fuse(signals)
        available = True
        status_value = "partial"

    return LiveAiAnalysisRunOut(
        claim_id=claim_id,
        available=available,
        status=status_value,
        evidence_summary=evidence_summary,
        overall_risk_score=overall_risk_score,
        risk_band=risk_band,
        confidence_score=confidence_score if status_value != "insufficient_evidence" else None,
        confidence_band=confidence_band,
        uncertainty_reasons=uncertainty_reasons,
        signals=signals,
        limitations=limitations,
        methodology_source=METHODOLOGY_SOURCE,
    )
