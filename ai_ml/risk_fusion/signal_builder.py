"""Builds the 7 claim-level `Signal` objects (Part A) from the EXISTING
Step 5.1/5.2 leakage-safe claim-level dataset and the EXISTING
`RuleBasedFraudScreener`. No new raw data, no new database columns, no
new preprocessing logic - this module only re-packages already-computed,
already-verified-safe columns into the common `Signal` representation.

Continuous signals (repair-estimate ratio, days-since-policy-start) are
normalized against a REFERENCE population's own empirical distribution
(`ReferenceStats`, computed once from a TRAINING split - never from the
claims being scored) rather than an arbitrary fixed cutoff. This is
normalization, not label-based tuning: no target column is read anywhere
in this module.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ai_ml.baselines.rule_based_fraud import RuleBasedFraudScreener
from ai_ml.risk_fusion.signal_schema import Signal, SignalAvailability, SignalCategory, SignalDirection

SOURCE_MODULE = "ai_ml.risk_fusion.signal_builder"

# The fraud-screening rule score is the one signal in this layer that is
# downstream of an evaluated model/rule (`RuleBasedFraudScreener`). Step
# 5.2 (single split) and Step 5.3 (5-fold x 3-seed grouped CV) both found
# it performs only marginally above chance (repeated-CV PR-AUC ~0.156 vs
# a ~15.1% base rate). Its per-signal confidence is fixed at this
# documented, literature-of-its-own-experiment-derived discount rather
# than left at 1.0 like the other, purely-descriptive boolean/ratio
# signals - it is NOT a per-claim computed confidence.
FRAUD_SCREENING_CONFIDENCE = 0.40


@dataclass(frozen=True)
class ReferenceStats:
    """Empirical percentile anchors computed once from a reference
    (training) population - used only to normalize continuous raw
    values into [0, 1] risk contributions. Contains no target/label
    information."""

    repair_ratio_p50: float
    repair_ratio_p90: float
    early_claim_days_p10: float
    early_claim_days_p50: float

    @classmethod
    def from_reference_population(cls, reference_df: pd.DataFrame) -> "ReferenceStats":
        claim_amount = reference_df["Claim_Amount"].replace(0, np.nan)
        ratio = reference_df["est_Repair_Estimate"] / claim_amount
        days = (reference_df["Claim_Date"] - reference_df["pol_Policy_Start_Date"]).dt.days
        return cls(
            repair_ratio_p50=float(ratio.quantile(0.50)),
            repair_ratio_p90=float(ratio.quantile(0.90)),
            early_claim_days_p10=float(days.quantile(0.10)),
            early_claim_days_p50=float(days.quantile(0.50)),
        )


def _scale_between(value: float, low: float, high: float) -> float:
    """Linearly maps value into [0, 1], clipped, treating `low` as the
    "no risk contribution" anchor and `high` as the "maximum risk
    contribution" anchor. Handles low == high (degenerate reference
    distribution) by returning 0.0 rather than dividing by zero."""
    if high <= low:
        return 0.0
    return float(np.clip((value - low) / (high - low), 0.0, 1.0))


def _row_signals(row: pd.Series, ref: ReferenceStats, rule_predictions_by_claim: dict) -> list[Signal]:
    claim_id = str(row["Claim_ID"])
    signals: list[Signal] = []

    # 1. DOCUMENT_CONSISTENCY - three independent cross-document mismatch
    # flags from cross_document_consistency (already used as safe
    # Fraud_Label features in ai_ml.baselines.rule_based_fraud).
    mismatch_cols = ["cdc_Document_Mismatch_Indicator", "cdc_Accident_Details_Mismatch_Indicator", "cdc_Vehicle_Damage_Mismatch_Indicator"]
    mismatch_vals = [bool(row[c]) for c in mismatch_cols if pd.notna(row[c])]
    if mismatch_vals:
        value = float(np.mean(mismatch_vals))
        signals.append(Signal(
            claim_id=claim_id, signal_name="document_consistency_mismatch", category=SignalCategory.DOCUMENT_CONSISTENCY,
            signal_value=value, raw_value=value, signal_direction=SignalDirection.HIGHER_IS_RISKIER,
            confidence=1.0, availability=SignalAvailability.AVAILABLE, evidence_available=True,
            explanation=f"{sum(mismatch_vals)}/{len(mismatch_vals)} cross-document consistency checks (accident details, vehicle damage, overall document match) flagged a mismatch.",
            source_module="ai_ml.common.feature_builder (cross_document_consistency)",
        ))
    else:
        signals.append(Signal(
            claim_id=claim_id, signal_name="document_consistency_mismatch", category=SignalCategory.DOCUMENT_CONSISTENCY,
            signal_value=None, raw_value=None, signal_direction=SignalDirection.HIGHER_IS_RISKIER,
            confidence=None, availability=SignalAvailability.UNAVAILABLE, evidence_available=False,
            explanation="No cross-document consistency record available for this claim.",
            source_module="ai_ml.common.feature_builder (cross_document_consistency)",
        ))

    # 2. REPAIR_ESTIMATE_ANOMALY - the existing excessive-amount flag,
    # blended with a reference-normalized repair/claim-amount ratio.
    claim_amount = row["Claim_Amount"] if pd.notna(row["Claim_Amount"]) and row["Claim_Amount"] != 0 else np.nan
    ratio = row["est_Repair_Estimate"] / claim_amount if pd.notna(claim_amount) and pd.notna(row["est_Repair_Estimate"]) else np.nan
    excessive_flag = row.get("est_Excessive_Claim_Amount_Indicator")
    if not np.isnan(ratio) or pd.notna(excessive_flag):
        ratio_component = _scale_between(ratio, ref.repair_ratio_p50, ref.repair_ratio_p90) if not np.isnan(ratio) else 0.0
        flag_component = float(bool(excessive_flag)) if pd.notna(excessive_flag) else 0.0
        value = 0.5 * flag_component + 0.5 * ratio_component
        signals.append(Signal(
            claim_id=claim_id, signal_name="repair_estimate_anomaly", category=SignalCategory.REPAIR_ESTIMATE_ANOMALY,
            signal_value=value, raw_value=float(ratio) if not np.isnan(ratio) else None,
            signal_direction=SignalDirection.HIGHER_IS_RISKIER, confidence=1.0,
            availability=SignalAvailability.AVAILABLE, evidence_available=True,
            explanation=(
                f"Repair-estimate/claim-amount ratio {'%.2f' % ratio if not np.isnan(ratio) else 'n/a'} "
                f"(reference median {ref.repair_ratio_p50:.2f}, 90th percentile {ref.repair_ratio_p90:.2f}); "
                f"excessive-amount flag={'set' if flag_component else 'not set'}."
            ),
            source_module="ai_ml.common.feature_builder (repair_estimates) + ai_ml.risk_fusion.signal_builder",
        ))
    else:
        signals.append(Signal(
            claim_id=claim_id, signal_name="repair_estimate_anomaly", category=SignalCategory.REPAIR_ESTIMATE_ANOMALY,
            signal_value=None, raw_value=None, signal_direction=SignalDirection.HIGHER_IS_RISKIER,
            confidence=None, availability=SignalAvailability.UNAVAILABLE, evidence_available=False,
            explanation="No repair estimate or claim amount available for this claim.",
            source_module="ai_ml.common.feature_builder (repair_estimates)",
        ))

    # 3. EVIDENCE_DUPLICATION
    evidence_count = row.get("evidence_count", 0) or 0
    if evidence_count > 0:
        value = float(bool(row["evidence_any_duplicate_flag"]))
        signals.append(Signal(
            claim_id=claim_id, signal_name="evidence_duplication", category=SignalCategory.EVIDENCE_DUPLICATION,
            signal_value=value, raw_value=value, signal_direction=SignalDirection.HIGHER_IS_RISKIER,
            confidence=1.0, availability=SignalAvailability.AVAILABLE, evidence_available=True,
            explanation=f"{'Duplicate' if value else 'No duplicate'} evidence detected across {int(evidence_count)} submitted evidence item(s).",
            source_module="ai_ml.common.preprocessing (evidence aggregation)",
        ))
    else:
        signals.append(Signal(
            claim_id=claim_id, signal_name="evidence_duplication", category=SignalCategory.EVIDENCE_DUPLICATION,
            signal_value=None, raw_value=None, signal_direction=SignalDirection.HIGHER_IS_RISKIER,
            confidence=None, availability=SignalAvailability.INSUFFICIENT_EVIDENCE, evidence_available=False,
            explanation="No evidence items submitted for this claim - duplication cannot be assessed.",
            source_module="ai_ml.common.preprocessing (evidence aggregation)",
        ))

    # 4. FRAUD_SCREENING - Step 5.2's transparent rule-based screener
    # (reused as-is, already fit on a reference training split).
    rule_pred = rule_predictions_by_claim.get(claim_id)
    if rule_pred is not None:
        signals.append(Signal(
            claim_id=claim_id, signal_name="fraud_screening_rule_score", category=SignalCategory.FRAUD_SCREENING,
            signal_value=float(rule_pred["Rule_Baseline_Score"]), raw_value=float(rule_pred["Rule_Baseline_Score"]),
            signal_direction=SignalDirection.HIGHER_IS_RISKIER, confidence=FRAUD_SCREENING_CONFIDENCE,
            availability=SignalAvailability.AVAILABLE, evidence_available=True,
            explanation=(
                "Transparent rule-based fraud screening score (ai_ml.baselines.rule_based_fraud), reason codes: "
                f"{rule_pred['Rule_Reason_Codes'] or 'none'}. Confidence fixed at {FRAUD_SCREENING_CONFIDENCE} "
                "to reflect Step 5.2/5.3's finding that this signal performs only marginally above chance under "
                "repeated grouped cross-validation - it is treated as one weak, honestly-labeled input, not a verdict."
            ),
            source_module="ai_ml.baselines.rule_based_fraud.RuleBasedFraudScreener",
        ))
    else:
        signals.append(Signal(
            claim_id=claim_id, signal_name="fraud_screening_rule_score", category=SignalCategory.FRAUD_SCREENING,
            signal_value=None, raw_value=None, signal_direction=SignalDirection.HIGHER_IS_RISKIER,
            confidence=None, availability=SignalAvailability.NOT_EVALUATED, evidence_available=False,
            explanation="Fraud screening rule was not evaluated for this claim.",
            source_module="ai_ml.baselines.rule_based_fraud.RuleBasedFraudScreener",
        ))

    # 5. CLAIM_PATTERN_ANOMALY - early-claim-after-policy-start timing.
    policy_start = row.get("pol_Policy_Start_Date")
    claim_date = row.get("Claim_Date")
    if pd.notna(policy_start) and pd.notna(claim_date):
        days = (claim_date - policy_start).days
        # Fewer days since policy start -> more anomalous -> invert scale.
        value = 1.0 - _scale_between(days, ref.early_claim_days_p10, ref.early_claim_days_p50)
        signals.append(Signal(
            claim_id=claim_id, signal_name="claim_pattern_anomaly", category=SignalCategory.CLAIM_PATTERN_ANOMALY,
            signal_value=value, raw_value=float(days), signal_direction=SignalDirection.LOWER_IS_RISKIER,
            confidence=1.0, availability=SignalAvailability.AVAILABLE, evidence_available=True,
            explanation=f"Claim filed {int(days)} day(s) after policy start (reference 10th percentile {ref.early_claim_days_p10:.0f}, median {ref.early_claim_days_p50:.0f}).",
            source_module="ai_ml.common.feature_builder (claims + policies)",
        ))
    else:
        signals.append(Signal(
            claim_id=claim_id, signal_name="claim_pattern_anomaly", category=SignalCategory.CLAIM_PATTERN_ANOMALY,
            signal_value=None, raw_value=None, signal_direction=SignalDirection.LOWER_IS_RISKIER,
            confidence=None, availability=SignalAvailability.UNAVAILABLE, evidence_available=False,
            explanation="Policy start date or claim date missing - claim timing cannot be assessed.",
            source_module="ai_ml.common.feature_builder (claims + policies)",
        ))

    # 6. DOCUMENT_COMPLETENESS
    document_count = row.get("document_count", 0) or 0
    completeness = row.get("document_completeness_mean")
    if document_count > 0 and pd.notna(completeness):
        value = float(np.clip(1.0 - completeness, 0.0, 1.0))
        signals.append(Signal(
            claim_id=claim_id, signal_name="document_completeness", category=SignalCategory.DOCUMENT_COMPLETENESS,
            signal_value=value, raw_value=float(completeness), signal_direction=SignalDirection.LOWER_IS_RISKIER,
            confidence=1.0, availability=SignalAvailability.AVAILABLE, evidence_available=True,
            explanation=f"Mean document completeness {completeness:.2f} across {int(document_count)} submitted document(s).",
            source_module="ai_ml.common.preprocessing (document aggregation)",
        ))
    else:
        signals.append(Signal(
            claim_id=claim_id, signal_name="document_completeness", category=SignalCategory.DOCUMENT_COMPLETENESS,
            signal_value=None, raw_value=None, signal_direction=SignalDirection.LOWER_IS_RISKIER,
            confidence=None, availability=SignalAvailability.INSUFFICIENT_EVIDENCE, evidence_available=False,
            explanation="No documents submitted for this claim - completeness cannot be assessed.",
            source_module="ai_ml.common.preprocessing (document aggregation)",
        ))

    # 7. INFORMATION_QUALITY - OCR/image/evidence confidence, discounted
    # further (in explanation only, not value) when no surveyor
    # inspection exists to corroborate the submitted evidence.
    quality_components = [row.get(c) for c in ["document_ocr_confidence_mean", "evidence_confidence_mean", "evidence_image_quality_mean"]]
    quality_components = [float(c) for c in quality_components if pd.notna(c)]
    has_inspection = pd.notna(row.get("insp_Surveyor_ID"))
    if quality_components:
        mean_quality = float(np.mean(quality_components))
        value = float(np.clip(1.0 - mean_quality, 0.0, 1.0))
        confidence = 1.0 if has_inspection else 0.85
        inspection_note = "A surveyor inspection is on record." if has_inspection else "No surveyor inspection is on record for this claim, reducing corroborating evidence."
        signals.append(Signal(
            claim_id=claim_id, signal_name="information_quality", category=SignalCategory.INFORMATION_QUALITY,
            signal_value=value, raw_value=mean_quality, signal_direction=SignalDirection.LOWER_IS_RISKIER,
            confidence=confidence, availability=SignalAvailability.AVAILABLE, evidence_available=True,
            explanation=f"Mean document/evidence quality score {mean_quality:.2f}. {inspection_note}",
            source_module="ai_ml.common.preprocessing (document + evidence aggregation)",
        ))
    else:
        signals.append(Signal(
            claim_id=claim_id, signal_name="information_quality", category=SignalCategory.INFORMATION_QUALITY,
            signal_value=None, raw_value=None, signal_direction=SignalDirection.LOWER_IS_RISKIER,
            confidence=None, availability=SignalAvailability.INSUFFICIENT_EVIDENCE, evidence_available=False,
            explanation="No document/evidence quality measurements available for this claim.",
            source_module="ai_ml.common.preprocessing (document + evidence aggregation)",
        ))

    return signals


def build_signals(df: pd.DataFrame, reference_df: pd.DataFrame, fraud_screener: RuleBasedFraudScreener) -> dict[str, list[Signal]]:
    """Builds all 7 signals for every claim in `df`.

    `reference_df` supplies the (training-only) empirical distribution
    used to normalize continuous signals - pass the SAME training split
    used to fit `fraud_screener` to keep every part of this layer
    leakage-safe. `fraud_screener` must already be `.fit()`-ed.

    Returns {claim_id: [Signal, ...]} - always exactly 7 signals per
    claim (some may be UNAVAILABLE/INSUFFICIENT_EVIDENCE, never silently
    dropped), so no claim is ever missing from the result.
    """
    ref = ReferenceStats.from_reference_population(reference_df)
    rule_predictions = fraud_screener.predict(df).set_index("Claim_ID").to_dict(orient="index")
    rule_predictions = {str(k): v for k, v in rule_predictions.items()}

    result: dict[str, list[Signal]] = {}
    for _, row in df.iterrows():
        claim_id = str(row["Claim_ID"])
        result[claim_id] = _row_signals(row, ref, rule_predictions)
    return result
