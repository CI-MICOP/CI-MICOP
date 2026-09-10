"""Non-AI rule baselines for the Step 5.3 secondary targets (Section 7),
plus the improved "Rule Baseline v2" for fraud (Section 12).

For `est_Excessive_Claim_Amount_Indicator` a single transparent signal -
the repair-estimate-to-claim-amount ratio - is a legitimate pre-decision
input (verified NOT to be target-derived; see
`ai_ml.secondary_targets.target_audit.SAFE_RESTORATIONS`), so a rule
baseline is implemented and evaluated honestly, even though the earlier
correlation check found it near-independent of the target.

For `frd_Risk_Category` and `cdc_Overall_Consistency_Status`, no field
outside the target's own source table showed any usable relationship
(see the crosstabs run during the target audit), and every field inside
that source table is POTENTIAL_LEAKAGE (same generation process). Inventing
a rule from unrelated customer/vehicle/policy fields would be exactly the
"arbitrary invented threshold" the Step 5.2/5.3 instructions forbid.
`ai_ml.secondary_targets.target_audit.NO_BASELINE_STATEMENT` is used
verbatim for both in the report.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from sklearn.metrics import f1_score
from sklearn.model_selection import GroupShuffleSplit

from ai_ml.baselines.rule_based_fraud import RuleBasedFraudScreener

RANDOM_SEED = 42


@dataclass
class ExcessiveAmountRuleScreener:
    """Flags a claim when its repair-estimate/claim-amount ratio is in
    the extreme tail of the TRAINING distribution. `calibration_percentile`
    is the only free parameter and is never chosen using test/validation
    labels - only the ratio distribution itself."""

    calibration_percentile: float = 0.90

    def __post_init__(self) -> None:
        self._fitted = False
        self.ratio_threshold_: float | None = None

    @staticmethod
    def _ratio(df: pd.DataFrame) -> pd.Series:
        claim_amount = df["Claim_Amount"].replace(0, np.nan)
        return df["est_Repair_Estimate"] / claim_amount

    def fit(self, train_df: pd.DataFrame) -> "ExcessiveAmountRuleScreener":
        ratio = self._ratio(train_df)
        self.ratio_threshold_ = float(ratio.quantile(self.calibration_percentile))
        self._fitted = True
        return self

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self._fitted:
            raise RuntimeError("ExcessiveAmountRuleScreener.fit(train_df) must be called before predict().")
        ratio = self._ratio(df)
        flagged = (ratio >= self.ratio_threshold_).fillna(False)
        return pd.DataFrame({
            "Claim_ID": df["Claim_ID"].values,
            "Rule_Baseline_Prediction": flagged.astype(int).values,
            "Rule_Baseline_Score": ratio.fillna(0).clip(upper=ratio.quantile(0.99) if ratio.notna().any() else 1).values,
            "Rule_Reason_Codes": np.where(flagged, "REPAIR_ESTIMATE_ANOMALY", ""),
        })

    def calibration_summary(self) -> dict:
        return {"calibration_percentile": self.calibration_percentile, "ratio_threshold": self.ratio_threshold_}


def calibrate_rule_baseline_v2(train_df: pd.DataFrame, candidate_thresholds=tuple(np.arange(0.5, 3.51, 0.5)), random_state: int = RANDOM_SEED) -> tuple[RuleBasedFraudScreener, dict]:
    """Section 12: a scored (not OR-combined) fraud rule baseline. Reuses
    the existing `RuleBasedFraudScreener` (it already sums weighted rule
    hits into a score) and calibrates ONLY `overall_threshold` - raising
    it above the default 1.0 requires multiple weaker signals or two
    strong ones to fire together, which is expected to trade some recall
    for meaningfully higher precision.

    Calibration procedure (training data only, mirrors Step 5.2's ML
    threshold calibration): split TRAIN further into an inner-train/
    inner-validation grouped split, fit the rule's numeric-signal
    thresholds on inner-train, then pick the `overall_threshold` that
    maximizes F1 on inner-validation. The final screener returned is
    re-fit on the FULL training set with that chosen threshold, ready to
    be evaluated once on the untouched test set."""
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=random_state)
    inner_train_idx, inner_val_idx = next(splitter.split(train_df, groups=train_df["Customer_ID"]))
    inner_train_df = train_df.iloc[inner_train_idx]
    inner_val_df = train_df.iloc[inner_val_idx]

    scored_candidates = []
    for threshold in candidate_thresholds:
        screener = RuleBasedFraudScreener(overall_threshold=float(threshold))
        screener.fit(inner_train_df)
        predictions = screener.predict(inner_val_df)
        actual = inner_val_df["frd_Fraud_Label"].astype(int).values
        f1 = f1_score(actual, predictions["Rule_Baseline_Prediction"], zero_division=0)
        scored_candidates.append((float(threshold), float(f1)))

    best_threshold, best_f1 = max(scored_candidates, key=lambda item: item[1])

    final_screener = RuleBasedFraudScreener(overall_threshold=best_threshold)
    final_screener.fit(train_df)

    calibration_info = {
        "procedure": "inner grouped train/validation split (25% of TRAIN only); test set never touched",
        "inner_train_claims": len(inner_train_idx),
        "inner_val_claims": len(inner_val_idx),
        "candidates_tried": scored_candidates,
        "chosen_overall_threshold": best_threshold,
        "inner_validation_f1_at_chosen_threshold": best_f1,
    }
    return final_screener, calibration_info
