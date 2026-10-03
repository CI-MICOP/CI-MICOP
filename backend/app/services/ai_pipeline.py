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

Conclusion (see the docs for the full audit table): as of Step 5.8.11,
only 2 of 7 signal families were genuinely live-computable -
`claim_pattern_anomaly` (claim-filed-vs-policy-start timing) and
`repair_estimate_anomaly` (repair-estimate/claim-amount ratio only, NOT
the Excessive_Claim_Amount_Indicator flag, which is always a placeholder
for a live estimate). Step 5.8.12 adds a genuine, deterministic
`document_completeness` signal (see services/document_analysis.py) once a
claim has at least one uploaded document - a rule-based required-vs-present
Document_Type comparison, not machine learning - bringing the total to 3
of 7. Step 5.8.18 (roadmap item 8) feeds three more from the live checks
built since: `document_consistency_mismatch` (Steps 5.8.13-B/C, 5.8.16-17),
`evidence_duplication` (Step 5.8.14) and `information_quality` (Step
5.8.15, photo part) - up to 6 of 7, each reported unavailable whenever its
check could not run. `fraud_screening_rule_score` is still never computed
live (see its reason below), so status never reaches "completed". See
docs/project_documentation/LIVE_SIGNAL_INTEGRATION.md.

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
from app.db_models.document import Document
from app.schemas.ai_pipeline import EvidenceSummaryOut, LiveAiAnalysisRunOut, LiveSignalOut
from app.services import (
    accident_consistency,
    document_analysis,
    document_consistency,
    evidence_duplication,
    evidence_quality,
    semantic_consistency,
)

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

# Signal families this live pipeline cannot compute today, and exactly
# why - see this module's docstring and LIVE_AI_PIPELINE.md.
# "document_completeness" is a special case as of Step 5.8.12: it has a
# genuine live computation (document_analysis.calculate_claim_document_
# completeness) and is normally computed by _document_completeness_signal
# below - this entry is only used as its fallback for the one case that
# function itself reports unavailable (a claim with zero documents, where
# there is no analyzable document set at all - see Phase 10 of Step 5.8.12).
_UNAVAILABLE_SIGNAL_REASONS: dict[str, tuple[str, str]] = {
    # Step 5.8.18: the three entries below are now only fallbacks - each
    # signal is normally computed by its own function further down and
    # passes a more specific reason when it cannot be.
    "document_consistency_mismatch": (
        "DOCUMENT_CONSISTENCY",
        "No document consistency check could compare anything for this claim yet.",
    ),
    "evidence_duplication": (
        "EVIDENCE_DUPLICATION",
        "No readable evidence photos exist for this claim, so duplication cannot be assessed.",
    ),
    "fraud_screening_rule_score": (
        "FRAUD_SCREENING",
        "The trained fraud model and the full rule-based screener were built on the synthetic "
        "dataset's own indicator columns (e.g. Duplicate_Evidence_Indicator, cross-document "
        "mismatch flags), which live uploads still store as 'not yet analyzed' placeholders. "
        "Running them on those placeholders would misrepresent every live claim as low-risk, "
        "and their live inputs have not been validated (roadmap item 9), so this signal is not "
        "computed live.",
    ),
    "document_completeness": (
        "DOCUMENT_COMPLETENESS",
        "No documents have been uploaded for this claim yet, so there is no document set to "
        "compare against the required document types for its claim type - this is not the "
        "same as 0% complete (see docs/project_documentation/DOCUMENT_COMPLETENESS_AND_OCR.md).",
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


def _document_completeness_signal(claim: Claim, documents: list[Document]) -> LiveSignalOut:
    """Step 5.8.12: a genuine, deterministic (not machine-learned) signal -
    see document_analysis.calculate_claim_document_completeness. Reports
    unavailable, via the same _unavailable_signal fallback as every other
    unsupported signal, only when the claim has zero documents (no
    analyzable document set at all - not the same as "0% complete")."""
    result = document_analysis.calculate_claim_document_completeness(claim.Claim_Type, documents)
    if not result.available:
        return _unavailable_signal("document_completeness")

    # Higher signal_value = more anomalous/concerning, matching the other
    # two live signals' convention - so incompleteness (not completeness)
    # is what raises this signal's contribution to the fused risk score.
    incompleteness = round(1.0 - result.ratio, 4)
    explanation = result.explanation
    if result.missing:
        explanation += f" Missing: {', '.join(result.missing)}."
    else:
        explanation += " All required document types are present."

    return LiveSignalOut(
        signal_name="document_completeness",
        category="DOCUMENT_COMPLETENESS",
        signal_value=incompleteness,
        availability="available",
        confidence=1.0,
        explanation=explanation,
    )


def _unavailable_signal(signal_name: str, reason: str | None = None) -> LiveSignalOut:
    category, default_reason = _UNAVAILABLE_SIGNAL_REASONS[signal_name]
    return LiveSignalOut(
        signal_name=signal_name, category=category, availability="unavailable", explanation=reason or default_reason
    )


# ---------------------------------------------------------------------------
# Step 5.8.18: signals fed by the live analysis checks built in Steps
# 5.8.13-B to 5.8.17 (roadmap item 8). Each reuses the existing check's own
# result unchanged and turns it into a 0-1 value with the same "higher =
# more concerning" convention as the research signal_builder. A check that
# could not run (UNAVAILABLE / INCONCLUSIVE) never contributes a number.
# ---------------------------------------------------------------------------

_CONSISTENCY_DISAGREE = {document_consistency.STATUS_MISMATCH, semantic_consistency.STATUS_CONTRADICTION}
_CONSISTENCY_AGREE = {document_consistency.STATUS_MATCH, semantic_consistency.STATUS_CONSISTENT}


def _document_consistency_signal(db: Session, claim: Claim) -> LiveSignalOut:
    """Share of the claim's document consistency checks that found a
    disagreement, out of those that could actually compare something -
    the live counterpart of signal_builder's mean of three mismatch flags."""
    identifiers = document_consistency.compare_claim_documents(db, claim)
    accident = accident_consistency.compare_claim_accident_details(db, claim)
    narrative = semantic_consistency.compare_claim_narrative(db, claim)
    checks = {
        "registration number": identifiers.registration.status,
        "policy number": identifiers.policy.status,
        "accident date": accident.accident_date.status,
        "accident time": accident.accident_time.status,
        "FIR number": accident.fir_number.status,
        "FIR vs Survey Report location": narrative.relationship,
    }
    compared = {name: s for name, s in checks.items() if s in _CONSISTENCY_AGREE | _CONSISTENCY_DISAGREE}
    if not compared:
        return _unavailable_signal(
            "document_consistency_mismatch",
            "None of this claim's document consistency checks (registration, policy, accident date/time, FIR "
            "number, FIR vs Survey Report location) could compare anything yet. Upload the relevant documents "
            "and run 'Analyze Documents' so their text is extracted.",
        )
    disagreeing = [name for name, s in compared.items() if s in _CONSISTENCY_DISAGREE]
    value = round(len(disagreeing) / len(compared), 4)
    explanation = (
        f"{len(disagreeing)}/{len(compared)} document consistency check(s) that could run found a disagreement"
        + (f" ({', '.join(disagreeing)})." if disagreeing else ".")
        + f" Not comparable yet: {', '.join(n for n in checks if n not in compared) or 'none'}."
        " Deterministic text checks validated only on controlled test documents - a disagreement is for "
        "officer review, not an accusation."
    )
    return LiveSignalOut(
        signal_name="document_consistency_mismatch",
        category="DOCUMENT_CONSISTENCY",
        signal_value=value,
        availability="available",
        confidence=1.0,
        explanation=explanation,
    )


def _evidence_duplication_signal(db: Session, claim: Claim) -> LiveSignalOut:
    """1 if any readable photo on the claim is an exact or near copy of
    another stored photo, else 0 - binary, like signal_builder's
    evidence_any_duplicate_flag."""
    result = evidence_duplication.check_claim_evidence(db, claim)
    if result.photos_checked == 0:
        return _unavailable_signal(
            "evidence_duplication", "No evidence photos have been uploaded for this claim, so duplication cannot be assessed."
        )
    copied = [
        r.evidence_id
        for r in result.results
        if r.status in (evidence_duplication.STATUS_EXACT_DUPLICATE, evidence_duplication.STATUS_NEAR_DUPLICATE)
    ]
    checked = [r for r in result.results if r.status != evidence_duplication.STATUS_UNAVAILABLE]
    if not copied and not checked:
        return _unavailable_signal(
            "evidence_duplication",
            "None of this claim's evidence photos could be read, so duplication cannot be assessed.",
        )
    value = 1.0 if copied else 0.0
    explanation = (
        f"Copy found for {len(copied)} of {result.photos_checked} evidence photo(s) ({', '.join(copied)})."
        if copied
        else f"No exact or near copy found for {len(checked)} readable evidence photo(s) among "
        f"{result.photos_compared_against} stored photo(s)."
    ) + " Image-fingerprint check (SHA-256 + 64-bit difference hash), not an image-recognition model."
    return LiveSignalOut(
        signal_name="evidence_duplication",
        category="EVIDENCE_DUPLICATION",
        signal_value=value,
        availability="available",
        confidence=1.0,
        explanation=explanation,
    )


def _information_quality_signal(db: Session, claim: Claim, inspections: list) -> LiveSignalOut:
    """Share of the claim's readable evidence photos with at least one
    quality flag. The research signal also averaged document OCR confidence;
    that part stays out because native PDF text has no OCR confidence and
    Tesseract is not installed in this environment. Confidence 1.0 with a
    surveyor inspection on record, else 0.85 - ported from signal_builder."""
    result = evidence_quality.check_claim_photo_quality(db, claim)
    measured = [r for r in result.results if r.status != evidence_quality.STATUS_UNAVAILABLE]
    if not measured:
        return _unavailable_signal(
            "information_quality",
            "No readable evidence photos exist for this claim, so photo quality cannot be assessed. Document "
            "OCR confidence is not used: OCR remains a research/prototype component in this environment.",
        )
    with_issues = [r for r in measured if r.status == evidence_quality.STATUS_ISSUES_FOUND]
    value = round(len(with_issues) / len(measured), 4)
    has_inspection = bool(inspections)
    explanation = (
        f"{len(with_issues)}/{len(measured)} readable evidence photo(s) have a quality issue (low resolution, "
        "too dark/bright, low contrast or blurry). "
        + ("A surveyor inspection is on record." if has_inspection else "No surveyor inspection is on record for this claim, reducing corroborating evidence.")
        + " Document OCR confidence is not included (OCR remains a research/prototype component here)."
    )
    return LiveSignalOut(
        signal_name="information_quality",
        category="INFORMATION_QUALITY",
        signal_value=value,
        availability="available",
        confidence=1.0 if has_inspection else 0.85,
        explanation=explanation,
    )


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
        _document_completeness_signal(claim, documents),
        _document_consistency_signal(db, claim),
        _evidence_duplication_signal(db, claim),
        _unavailable_signal("fraud_screening_rule_score"),
        _information_quality_signal(db, claim, inspections),
    ]
    available_count = sum(1 for s in signals if s.availability == "available")
    unavailable_names = [s.signal_name for s in signals if s.availability != "available"]

    confidence_score, confidence_band, uncertainty_reasons = _compute_uncertainty(signals)

    limitations = [
        "This is a research-prototype live pipeline validated only on a synthetic/de-identified "
        "dataset - see docs/project_documentation/AI_VS_NON_AI_RESULTS.md.",
        f"Only {available_count}/{TOTAL_DEFINED_SIGNALS} signal families defined by the Step 5.4 "
        "research prototype could be computed live for this claim"
        + (f" (unavailable: {', '.join(unavailable_names)})." if unavailable_names else ".")
        + " Fraud screening is never computed live: the trained model and full rule screener are not "
        "validated for live inputs. Document consistency, evidence duplication and information quality "
        "(Step 5.8.18) come from deterministic rule/fingerprint checks validated only on controlled test "
        "documents and generated images - see docs/project_documentation/LIVE_SIGNAL_INTEGRATION.md.",
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
