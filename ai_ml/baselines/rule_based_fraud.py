"""Transparent, non-AI, rule-based fraud-screening baseline.

This represents how a claim could be screened WITHOUT any ML model,
using only pre-decision signals already judged "safe" for the
`frd_Fraud_Label` target by
`ai_ml.common.feature_builder.safe_feature_columns`.

Design principles (per the Step 5.1 audit and Step 5.2 instructions):
  - No arbitrary invented thresholds. Every numeric threshold is a
    configurable, named constant computed from the TRAINING split only
    (via `fit`), never from the test labels.
  - Boolean signals that are already flags in the raw data (cross-document
    mismatch, duplicate evidence, excessive-claim-amount) need no
    threshold at all - they are used as-is.
  - Every rule carries a human-readable reason code (Section 15 of the
    Step 5.2 instructions) - never a claim of "confirmed fraud".
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ai_ml.explainability.reason_codes import REASON_CODES  # noqa: F401 - re-exported for callers


@dataclass
class RuleBasedFraudScreener:
    """Configurable rule-based screener. Boolean-flag rules have a fixed
    weight (they need no calibration); the two numeric rules calibrate
    their threshold from `fit(train_df)` and store it as a named
    attribute so the exact calibrated value is always inspectable and
    reproducible - not tuned against test labels.

    calibration_percentile: how "extreme" a numeric signal must be,
        relative to the *training* distribution, to fire. 0.90 means
        "in the worst 10% of the training claims for this signal".
    overall_threshold: the summed rule weight needed to flag a claim.
        Default 1.0 - one strong boolean flag, or two weaker numeric
        signals (each weighted 0.5), is enough to flag.
    """

    calibration_percentile: float = 0.90
    overall_threshold: float = 1.0
    weights: dict = field(
        default_factory=lambda: {
            "cross_document_mismatch": 1.0,
            "excessive_repair_estimate_flag": 1.0,
            "duplicate_evidence": 1.0,
            "high_repair_ratio": 0.5,
            "early_claim_after_policy": 0.5,
            "low_document_completeness": 0.5,
        }
    )

    def __post_init__(self) -> None:
        self._fitted = False
        self.repair_ratio_threshold_: float | None = None
        self.early_claim_days_threshold_: float | None = None
        self.completeness_threshold_: float | None = None

    @staticmethod
    def _derived_signals(df: pd.DataFrame) -> pd.DataFrame:
        """Computes the two numeric signals used by the calibrated rules.
        Returns a small DataFrame aligned to df.index - never mutates df."""
        out = pd.DataFrame(index=df.index)
        claim_amount = df["Claim_Amount"].replace(0, np.nan)
        out["repair_ratio"] = df["est_Repair_Estimate"] / claim_amount
        out["days_since_policy_start"] = (df["Claim_Date"] - df["pol_Policy_Start_Date"]).dt.days
        out["document_completeness_mean"] = df["document_completeness_mean"]
        return out

    def fit(self, train_df: pd.DataFrame) -> "RuleBasedFraudScreener":
        """Calibrates the numeric thresholds using ONLY the training
        claims passed in. Must never be called with test data."""
        signals = self._derived_signals(train_df)
        self.repair_ratio_threshold_ = float(signals["repair_ratio"].quantile(self.calibration_percentile))
        self.early_claim_days_threshold_ = float(
            signals["days_since_policy_start"].quantile(1 - self.calibration_percentile)
        )
        self.completeness_threshold_ = float(
            signals["document_completeness_mean"].quantile(1 - self.calibration_percentile)
        )
        self._fitted = True
        return self

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """Returns one row per claim: Claim_ID, Rule_Baseline_Prediction
        (0/1), Rule_Baseline_Score (sum of fired rule weights, normalized
        to [0, 1]), Rule_Reason_Codes (comma-joined reason codes)."""
        if not self._fitted:
            raise RuntimeError("RuleBasedFraudScreener.fit(train_df) must be called before predict().")

        signals = self._derived_signals(df)
        fired = pd.DataFrame(index=df.index)

        fired["cross_document_mismatch"] = (
            df["cdc_Document_Mismatch_Indicator"].fillna(False)
            | df["cdc_Accident_Details_Mismatch_Indicator"].fillna(False)
            | df["cdc_Vehicle_Damage_Mismatch_Indicator"].fillna(False)
        )
        fired["excessive_repair_estimate_flag"] = df["est_Excessive_Claim_Amount_Indicator"].fillna(False)
        fired["duplicate_evidence"] = df["evidence_any_duplicate_flag"].fillna(False).astype(bool)
        fired["high_repair_ratio"] = signals["repair_ratio"] >= self.repair_ratio_threshold_
        fired["early_claim_after_policy"] = signals["days_since_policy_start"] <= self.early_claim_days_threshold_
        fired["low_document_completeness"] = signals["document_completeness_mean"] <= self.completeness_threshold_
        fired = fired.fillna(False)

        max_score = sum(self.weights.values())
        raw_score = sum(fired[rule] * weight for rule, weight in self.weights.items())
        score = raw_score / max_score

        reason_map = {
            "cross_document_mismatch": "DOCUMENT_INCONSISTENCY",
            "excessive_repair_estimate_flag": "REPAIR_ESTIMATE_ANOMALY",
            "high_repair_ratio": "REPAIR_ESTIMATE_ANOMALY",
            "duplicate_evidence": "DUPLICATE_EVIDENCE",
            "early_claim_after_policy": "UNUSUAL_CLAIM_PATTERN",
            "low_document_completeness": "UNUSUAL_CLAIM_PATTERN",
        }

        def reasons_for_row(row) -> str:
            codes = []
            for rule, code in reason_map.items():
                if row[rule] and code not in codes:
                    codes.append(code)
            return ",".join(codes)

        reason_codes = fired.apply(reasons_for_row, axis=1)

        return pd.DataFrame(
            {
                "Claim_ID": df["Claim_ID"].values,
                "Rule_Baseline_Prediction": (raw_score >= self.overall_threshold).astype(int).values,
                "Rule_Baseline_Score": score.values,
                "Rule_Reason_Codes": reason_codes.values,
            }
        )

    def calibration_summary(self) -> dict:
        """The exact thresholds calibrated by fit(), for reporting."""
        return {
            "calibration_percentile": self.calibration_percentile,
            "overall_threshold": self.overall_threshold,
            "weights": dict(self.weights),
            "repair_ratio_threshold": self.repair_ratio_threshold_,
            "early_claim_days_threshold": self.early_claim_days_threshold_,
            "completeness_threshold": self.completeness_threshold_,
        }
