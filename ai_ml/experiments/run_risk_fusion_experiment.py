"""Step 5.4 experiment: multi-signal risk fusion, uncertainty, and review
prioritization, compared against the individual fraud-screening signal
alone. Builds on Step 5.2/5.3 (`RuleBasedFraudScreener`,
`create_grouped_split`, the `StratifiedGroupKFold` repeated-CV protocol)
without modifying any of it.

Run from the repo root:
    python -m ai_ml.experiments.run_risk_fusion_experiment

This is a research-prototype architecture demonstration on CI-MICOP's
synthetic/de-identified dataset (see AI_ML_DATASET_AUDIT.md,
AI_VS_NON_AI_RESULTS.md, SECONDARY_TARGET_RESULTS.md). Fusion scores are
NOT calibrated probabilities and must not be read as production
fraud-detection accuracy.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    f1_score,
    precision_recall_fscore_support,
    roc_auc_score,
)

from ai_ml.baselines.rule_based_fraud import RuleBasedFraudScreener
from ai_ml.common.feature_builder import build_claim_level_dataset
from ai_ml.experiments.run_fraud_experiment import TARGET as FRAUD_TARGET
from ai_ml.models.train_fraud_models import add_engineered_features
from ai_ml.risk_fusion.fusion_engine import (
    CONFIGURABLE_FUSION_WEIGHTS,
    configurable_weighted_fusion,
    equal_weight_fusion,
    risk_band_from_score,
)
from ai_ml.risk_fusion.reason_codes import reason_codes_for_claim
from ai_ml.risk_fusion.review_priority import recommend_review_priority
from ai_ml.risk_fusion.signal_builder import build_signals
from ai_ml.risk_fusion.signal_schema import Signal, SignalAvailability
from ai_ml.risk_fusion.uncertainty import calibrate_confidence_band_thresholds, compute_uncertainty
from ai_ml.risk_fusion.validation import assert_full_claim_coverage, assert_no_invalid_scores
from ai_ml.secondary_targets.validation import RANDOM_SEEDS, make_folds, summarize_stability

ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "model_artifacts" / "risk_fusion"
N_SPLITS = 5

SIGNAL_CATEGORY_TO_NAME = {
    "document_consistency": "document_consistency_mismatch",
    "repair_estimate": "repair_estimate_anomaly",
    "evidence": "evidence_duplication",
    "fraud_screening": "fraud_screening_rule_score",
}
ALL_SIGNAL_NAMES = [
    "document_consistency_mismatch", "repair_estimate_anomaly", "evidence_duplication",
    "fraud_screening_rule_score", "claim_pattern_anomaly", "document_completeness", "information_quality",
]


def _filter_signals(signals: list[Signal], keep_names: set[str]) -> list[Signal]:
    return [s for s in signals if s.signal_name in keep_names]


def _binary_metrics(y_true, scores, threshold: float = 0.5) -> dict:
    y_true = np.asarray(y_true)
    scores = np.asarray(scores, dtype=float)
    y_pred = (scores >= threshold).astype(int)
    single_class = len(np.unique(y_true)) < 2
    precision, recall, f1, _ = precision_recall_fscore_support(y_true, y_pred, average="binary", zero_division=0)
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "roc_auc": None if single_class else float(roc_auc_score(y_true, scores)),
        "pr_auc": None if single_class else float(average_precision_score(y_true, scores)),
        "n": int(len(y_true)),
    }


def _score_claims_with_strategy(train_df: pd.DataFrame, val_df: pd.DataFrame, strategy: str, keep_names: set[str] | None = None) -> dict[str, float | None]:
    """Fits the rule screener + reference stats on TRAIN, builds signals
    for VAL, and returns {claim_id: overall_risk_score}. `strategy` in
    {"individual_fraud_signal", "equal_weight_fusion", "configurable_weighted_fusion"}."""
    screener = RuleBasedFraudScreener()
    screener.fit(train_df)
    signals_by_claim = build_signals(val_df, train_df, screener)

    scores: dict[str, float | None] = {}
    for claim_id, signals in signals_by_claim.items():
        if keep_names is not None:
            signals = _filter_signals(signals, keep_names)
        if strategy == "individual_fraud_signal":
            fraud_signal = next((s for s in signals if s.signal_name == "fraud_screening_rule_score"), None)
            scores[claim_id] = fraud_signal.signal_value if fraud_signal and fraud_signal.availability == SignalAvailability.AVAILABLE else None
        elif strategy == "equal_weight_fusion":
            scores[claim_id] = equal_weight_fusion(claim_id, signals).overall_risk_score
        elif strategy == "configurable_weighted_fusion":
            scores[claim_id] = configurable_weighted_fusion(claim_id, signals).overall_risk_score
        else:
            raise ValueError(strategy)
    return scores


def section_comparison_cv(df: pd.DataFrame) -> dict:
    print("=" * 100)
    print("PART G: INDIVIDUAL SIGNAL vs EQUAL-WEIGHT vs CONFIGURABLE-WEIGHTED FUSION (repeated grouped CV)")
    print("=" * 100)
    strategies = ["individual_fraud_signal", "equal_weight_fusion", "configurable_weighted_fusion"]
    rows = []
    for seed in RANDOM_SEEDS:
        folds = make_folds(df, FRAUD_TARGET, N_SPLITS, seed)
        for fold_i, (train_idx, val_idx) in enumerate(folds):
            train_df, val_df = df.iloc[train_idx], df.iloc[val_idx]
            y_val = val_df[FRAUD_TARGET].astype(int)
            for strategy in strategies:
                scores_by_claim = _score_claims_with_strategy(train_df, val_df, strategy)
                claim_order = val_df["Claim_ID"].astype(str).tolist()
                scores = [scores_by_claim[c] if scores_by_claim[c] is not None else 0.0 for c in claim_order]
                coverage = sum(1 for c in claim_order if scores_by_claim[c] is not None) / len(claim_order)
                metrics = _binary_metrics(y_val, scores)
                metrics.update({"strategy": strategy, "seed": seed, "fold": fold_i, "coverage": coverage})
                rows.append(metrics)

    cv_df = pd.DataFrame(rows)
    stability = {}
    for strategy, group in cv_df.groupby("strategy"):
        stability[strategy] = {m: summarize_stability(group[m].tolist()) for m in ("precision", "recall", "f1", "roc_auc", "pr_auc", "coverage")}
        s = stability[strategy]
        print(f"  {strategy}: PR-AUC={s['pr_auc']['mean']:.3f}(std={s['pr_auc']['std']:.3f})  "
              f"F1={s['f1']['mean']:.3f}  Recall={s['recall']['mean']:.3f}  coverage={s['coverage']['mean']:.3f}")

    pr_auc_means = {k: v["pr_auc"]["mean"] for k, v in stability.items()}
    best = max(pr_auc_means, key=lambda k: pr_auc_means[k] if pr_auc_means[k] is not None else -1)
    improved = pr_auc_means.get("configurable_weighted_fusion", 0) is not None and pr_auc_means.get("individual_fraud_signal") is not None and pr_auc_means["configurable_weighted_fusion"] > pr_auc_means["individual_fraud_signal"]
    print(f"\n  Highest mean PR-AUC: {best} ({pr_auc_means[best]:.3f})")
    print(f"  Configurable fusion improves PR-AUC over the individual fraud signal alone: {improved}")

    return {"cv_rows": cv_df.to_dict(orient="records"), "stability": stability, "best_strategy_by_pr_auc": best, "fusion_improves_over_individual_signal": improved}


def section_ablation_study(df: pd.DataFrame) -> dict:
    print()
    print("=" * 100)
    print("PART H: ABLATION STUDY (configurable weighted fusion, repeated grouped CV)")
    print("=" * 100)
    configs = {
        "all_signals": set(ALL_SIGNAL_NAMES),
        "without_document_consistency": set(ALL_SIGNAL_NAMES) - {"document_consistency_mismatch"},
        "without_repair_estimate": set(ALL_SIGNAL_NAMES) - {"repair_estimate_anomaly"},
        "without_evidence": set(ALL_SIGNAL_NAMES) - {"evidence_duplication"},
        "without_fraud_screening": set(ALL_SIGNAL_NAMES) - {"fraud_screening_rule_score"},
        "only_fraud_screening": {"fraud_screening_rule_score"},
        "only_document_consistency": {"document_consistency_mismatch"},
        "only_repair_estimate": {"repair_estimate_anomaly"},
    }

    rows = []
    for seed in RANDOM_SEEDS:
        folds = make_folds(df, FRAUD_TARGET, N_SPLITS, seed)
        for fold_i, (train_idx, val_idx) in enumerate(folds):
            train_df, val_df = df.iloc[train_idx], df.iloc[val_idx]
            y_val = val_df[FRAUD_TARGET].astype(int)
            for config_name, keep_names in configs.items():
                scores_by_claim = _score_claims_with_strategy(train_df, val_df, "configurable_weighted_fusion", keep_names=keep_names)
                claim_order = val_df["Claim_ID"].astype(str).tolist()
                scores = [scores_by_claim[c] if scores_by_claim[c] is not None else 0.0 for c in claim_order]
                metrics = _binary_metrics(y_val, scores)
                metrics.update({"config": config_name, "seed": seed, "fold": fold_i})
                rows.append(metrics)

    ablation_df = pd.DataFrame(rows)
    stability = {}
    for config_name, group in ablation_df.groupby("config"):
        stability[config_name] = {m: summarize_stability(group[m].tolist()) for m in ("precision", "recall", "f1", "pr_auc")}
        s = stability[config_name]
        print(f"  {config_name:32s}: PR-AUC={s['pr_auc']['mean']:.3f}(std={s['pr_auc']['std']:.3f})  F1={s['f1']['mean']:.3f}")

    full_pr_auc = stability["all_signals"]["pr_auc"]["mean"]
    print(f"\n  Reference (all signals) PR-AUC: {full_pr_auc:.3f}")
    for config_name, s in stability.items():
        if config_name == "all_signals":
            continue
        delta = (s["pr_auc"]["mean"] - full_pr_auc) if s["pr_auc"]["mean"] is not None else None
        if delta is not None:
            print(f"    {config_name}: delta vs all_signals = {delta:+.3f}")

    return {"ablation_rows": ablation_df.to_dict(orient="records"), "stability": stability}


def section_full_dataset_scoring(df: pd.DataFrame) -> tuple[pd.DataFrame, dict, dict]:
    """Scores every claim once (train reference = full dataset, since this
    section is about coverage/review-priority distribution, not a
    held-out predictive-performance claim) for Parts C/D/F reporting and
    Part I example generation."""
    print()
    print("=" * 100)
    print("PARTS C/D/F: FULL-DATASET RISK BANDS, UNCERTAINTY, REVIEW PRIORITY (reference = full dataset)")
    print("=" * 100)
    screener = RuleBasedFraudScreener()
    screener.fit(df)
    signals_by_claim = build_signals(df, df, screener)

    # Two-pass: (1) compute raw confidence scores with the fixed default
    # bands, purely to calibrate readable band boundaries from THIS
    # dataset's own distribution (unsupervised - no label read); (2)
    # recompute uncertainty using those calibrated bands. See
    # ai_ml.risk_fusion.uncertainty.calibrate_confidence_band_thresholds.
    raw_confidence_scores = [compute_uncertainty(cid, s).confidence_score for cid, s in signals_by_claim.items()]
    band_thresholds = calibrate_confidence_band_thresholds(raw_confidence_scores)
    print(f"Calibrated confidence band thresholds (percentiles of this dataset's own confidence-score distribution): {band_thresholds}")

    records = []
    all_signals_map = {}
    for claim_id, signals in signals_by_claim.items():
        all_signals_map[claim_id] = signals
        fusion = configurable_weighted_fusion(claim_id, signals)
        uncertainty = compute_uncertainty(claim_id, signals, band_thresholds=band_thresholds)
        disagreement = any("disagree" in r for r in uncertainty.uncertainty_reasons)
        priority = recommend_review_priority(fusion.risk_band, uncertainty.confidence_band, fusion.evidence_count, disagreement)
        codes = reason_codes_for_claim(signals, uncertainty.confidence_band, uncertainty.uncertainty_reasons)
        records.append({
            "claim_id": claim_id, "overall_risk_score": fusion.overall_risk_score, "risk_band": fusion.risk_band,
            "evidence_count": fusion.evidence_count, "contributing_signals": len(fusion.contributing_signals),
            "unavailable_signals": len(fusion.unavailable_signals), "confidence_score": uncertainty.confidence_score,
            "confidence_band": uncertainty.confidence_band, "review_priority": priority, "reason_codes": ",".join(codes),
        })

    result_df = pd.DataFrame(records)
    assert_no_invalid_scores([configurable_weighted_fusion(cid, s) for cid, s in signals_by_claim.items()])
    assert_full_claim_coverage([configurable_weighted_fusion(cid, s) for cid, s in signals_by_claim.items()], set(df["Claim_ID"].astype(str)))

    print("Risk band distribution:")
    print(result_df["risk_band"].value_counts())
    print("\nConfidence band distribution:")
    print(result_df["confidence_band"].value_counts())
    print("\nReview priority distribution:")
    print(result_df["review_priority"].value_counts())
    coverage_pct = (result_df["contributing_signals"] / 7 * 100).mean()
    print(f"\nMean signal coverage: {coverage_pct:.1f}% of the 7 defined signals available per claim")

    return result_df, all_signals_map, band_thresholds


def section_representative_examples(result_df: pd.DataFrame, all_signals_map: dict, band_thresholds: dict) -> list[dict]:
    print()
    print("=" * 100)
    print("PART I: REPRESENTATIVE EXPLAINABILITY EXAMPLES")
    print("=" * 100)
    EXAMPLE_DIR = ARTIFACT_DIR.parent / "risk_fusion_explanations"
    EXAMPLE_DIR.mkdir(parents=True, exist_ok=True)

    def pick(mask, label):
        subset = result_df[mask]
        return subset.iloc[0]["claim_id"] if len(subset) else None

    examples_wanted = {
        "low_risk_high_confidence": (result_df["risk_band"] == "LOW") & (result_df["confidence_band"] == "HIGH_CONFIDENCE"),
        "high_risk_high_confidence": result_df["risk_band"].isin(["HIGH", "CRITICAL"]) & (result_df["confidence_band"] == "HIGH_CONFIDENCE"),
        "high_risk_low_confidence": result_df["risk_band"].isin(["HIGH", "CRITICAL"]) & result_df["confidence_band"].isin(["LOW_CONFIDENCE", "INSUFFICIENT_EVIDENCE"]),
        "signal_disagreement": result_df["reason_codes"].str.contains("MULTI_SIGNAL_DISAGREEMENT", na=False),
        "insufficient_evidence": result_df["confidence_band"] == "INSUFFICIENT_EVIDENCE",
    }

    saved = []
    for label, mask in examples_wanted.items():
        claim_id = pick(mask, label)
        if claim_id is None:
            print(f"  {label}: no matching claim found in this dataset (reported honestly, not fabricated).")
            continue
        signals = all_signals_map[claim_id]
        fusion = configurable_weighted_fusion(claim_id, signals)
        uncertainty = compute_uncertainty(claim_id, signals, band_thresholds=band_thresholds)
        codes = reason_codes_for_claim(signals, uncertainty.confidence_band, uncertainty.uncertainty_reasons)
        disagreement = any("disagree" in r for r in uncertainty.uncertainty_reasons)
        priority = recommend_review_priority(fusion.risk_band, uncertainty.confidence_band, fusion.evidence_count, disagreement)
        from ai_ml.risk_fusion.reason_codes import build_officer_explanation

        explanation = {
            "claim_id": claim_id,
            "example_type": label,
            "overall_risk_score": fusion.overall_risk_score,
            "risk_band": fusion.risk_band,
            "risk_band_label": "Prototype research risk band - workflow prioritization only, not a validated insurance risk threshold.",
            "confidence_score": uncertainty.confidence_score,
            "confidence_band": uncertainty.confidence_band,
            "uncertainty_reasons": uncertainty.uncertainty_reasons,
            "signals": [s.to_dict() for s in signals],
            "contributing_signals": fusion.contributing_signals,
            "unavailable_signals": fusion.unavailable_signals,
            "reason_codes": codes,
            "officer_explanations": build_officer_explanation(codes),
            "review_priority": priority,
            "human_review_required": True,
            "explanation": "These are AI risk signals for review prioritization, not a fraud determination. The Claims Officer makes the final decision.",
        }
        path = EXAMPLE_DIR / f"{label}.json"
        with open(path, "w") as f:
            json.dump(explanation, f, indent=2, default=str)
        saved.append(str(path))
        print(f"  {label}: claim {claim_id} -> {path}")

    return saved


def main() -> None:
    df = add_engineered_features(build_claim_level_dataset())
    if df["Claim_ID"].duplicated().any():
        raise AssertionError("Claim_ID duplicated - refusing to proceed.")
    print(f"Claim-level dataset: {len(df)} rows, Claim_ID unique: {df['Claim_ID'].is_unique}")

    comparison = section_comparison_cv(df)
    ablation = section_ablation_study(df)
    result_df, all_signals_map, band_thresholds = section_full_dataset_scoring(df)
    example_paths = section_representative_examples(result_df, all_signals_map, band_thresholds)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(ARTIFACT_DIR / "full_dataset_risk_fusion_scores.csv", index=False)
    summary = {
        "comparison_cv": comparison,
        "ablation_study": ablation,
        "risk_band_distribution": result_df["risk_band"].value_counts().to_dict(),
        "confidence_band_distribution": result_df["confidence_band"].value_counts().to_dict(),
        "review_priority_distribution": result_df["review_priority"].value_counts().to_dict(),
        "calibrated_confidence_band_thresholds": band_thresholds,
        "example_paths": example_paths,
        "configurable_fusion_weights": CONFIGURABLE_FUSION_WEIGHTS,
    }
    with open(ARTIFACT_DIR / "risk_fusion_summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print()
    print("=" * 100)
    print("DATA INTEGRITY CHECK")
    print("=" * 100)
    print(f"claims in dataset: {len(df)} (expected 654)")
    print(f"claims scored: {len(result_df)}")
    print(f"Full summary saved to {ARTIFACT_DIR / 'risk_fusion_summary.json'}")


if __name__ == "__main__":
    main()
