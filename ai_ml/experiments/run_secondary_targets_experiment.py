"""Step 5.3 experiment: secondary-target validation (frd_Risk_Category,
cdc_Overall_Consistency_Status, est_Excessive_Claim_Amount_Indicator),
Rule Baseline v2 for fraud, and repeated-grouped-CV robustness checks.

Builds on Step 5.2 (`ai_ml.experiments.run_fraud_experiment`,
`ai_ml.models.train_fraud_models`, `ai_ml.baselines.rule_based_fraud`)
without modifying any of it. Run from the repo root:

    python -m ai_ml.experiments.run_secondary_targets_experiment

This is a validation study on CI-MICOP's current synthetic/de-identified
dataset - see docs/project_documentation/AI_ML_DATASET_AUDIT.md and
AI_VS_NON_AI_RESULTS.md. Nothing here should be read as production
fraud-detection or claims-triage accuracy.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ai_ml.baselines.rule_based_fraud import RuleBasedFraudScreener
from ai_ml.common.feature_builder import build_claim_level_dataset
from ai_ml.experiments.run_fraud_experiment import TARGET as FRAUD_TARGET
from ai_ml.experiments.run_fraud_experiment import create_grouped_split
from ai_ml.explainability.reason_codes import build_claim_explanation
from ai_ml.explainability.shap_explainer import explain_claims, risk_level_from_probability, to_reason_codes
from ai_ml.models.evaluation import evaluate_binary
from ai_ml.models.train_fraud_models import (
    add_engineered_features,
    build_preprocessor,
    classify_feature_columns,
    train_logistic_regression,
    train_random_forest,
)
from ai_ml.secondary_targets.cv_runner import run_binary_cv, run_multiclass_cv, run_rule_baseline_cv
from ai_ml.secondary_targets.rule_baselines import ExcessiveAmountRuleScreener, calibrate_rule_baseline_v2
from ai_ml.secondary_targets.target_audit import (
    NO_BASELINE_STATEMENT,
    SECONDARY_TARGETS,
    audit_target,
    leakage_report,
    secondary_safe_feature_columns,
)
from ai_ml.secondary_targets.validation import RANDOM_SEEDS, summarize_stability

ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "model_artifacts" / "secondary_targets"
FIGURE_DIR = Path(__file__).resolve().parents[2] / "docs" / "project_documentation" / "figures"

MULTICLASS_TARGETS = {"frd_Risk_Category", "cdc_Overall_Consistency_Status"}
BINARY_SECONDARY_TARGETS = {"est_Excessive_Claim_Amount_Indicator"}


def section_target_audits(df: pd.DataFrame) -> dict:
    print("=" * 100)
    print("SECTION 1: TARGET AUDIT")
    print("=" * 100)
    audits = {}
    for target in SECONDARY_TARGETS:
        audit = audit_target(target, df)
        audits[target] = audit
        print(f"\n-- {target} --")
        print(f"  exists={audit['exists']}  dtype={audit['dtype']}  missing={audit['missing_values']}  "
              f"n_classes={audit['n_classes']}  min_class_size={audit['min_class_size']}")
        for cls, count in audit["class_counts"].items():
            pct = audit["class_percentages"][cls]
            print(f"    class {cls!r}: {count} ({pct}%)")
        if not audit["claim_id_unique"]:
            raise AssertionError(f"Claim_ID not unique while auditing {target}")
    return audits


def section_leakage_reports(df: pd.DataFrame) -> dict:
    print()
    print("=" * 100)
    print("SECTION 2: TARGET-SPECIFIC LEAKAGE CLASSIFICATION")
    print("=" * 100)
    reports = {}
    for target in SECONDARY_TARGETS:
        report = leakage_report(target, df)
        reports[target] = report
        print(f"\n-- {target} --")
        print(f"  SAFE: {report['n_safe']}  POTENTIAL_LEAKAGE: {report['n_potential_leakage']}  DEFINITE_LEAKAGE: {report['n_definite_leakage']}")
        print(f"  DEFINITE_LEAKAGE columns: {report['definite_leakage']}")
        if report["restorations_applied"]:
            print(f"  restored to SAFE (verified non-target-derived): {report['restorations_applied']}")
    return reports


def section_relationship_analysis(df: pd.DataFrame) -> dict:
    print()
    print("=" * 100)
    print("SECTION 11: TARGET RELATIONSHIP ANALYSIS (descriptive only - not used as predictive features)")
    print("=" * 100)
    pairs = [
        ("frd_Risk_Category", "frd_Fraud_Label"),
        ("frd_Risk_Category", "est_Excessive_Claim_Amount_Indicator"),
        ("frd_Risk_Category", "cdc_Overall_Consistency_Status"),
        ("cdc_Overall_Consistency_Status", "est_Excessive_Claim_Amount_Indicator"),
        ("cdc_Overall_Consistency_Status", "frd_Fraud_Label"),
        ("est_Excessive_Claim_Amount_Indicator", "frd_Fraud_Label"),
    ]
    crosstabs = {}
    for a, b in pairs:
        ct = pd.crosstab(df[a], df[b])
        crosstabs[f"{a}__vs__{b}"] = ct.to_dict()
        print(f"\n-- {a} vs {b} --")
        print(ct)

    low_medium_fraud_rate = df.loc[df["frd_Risk_Category"].isin(["Low", "Medium"]), "frd_Fraud_Label"].mean()
    high_critical_fraud_rate = df.loc[df["frd_Risk_Category"].isin(["High", "Critical"]), "frd_Fraud_Label"].mean()
    print(f"\nFraud rate when Risk_Category in {{Low, Medium}}: {low_medium_fraud_rate:.4f}")
    print(f"Fraud rate when Risk_Category in {{High, Critical}}: {high_critical_fraud_rate:.4f}")

    return {
        "crosstabs": crosstabs,
        "fraud_rate_low_medium_risk": float(low_medium_fraud_rate),
        "fraud_rate_high_critical_risk": float(high_critical_fraud_rate),
    }


def section_secondary_target_cv(df: pd.DataFrame) -> dict:
    print()
    print("=" * 100)
    print("SECTIONS 3-9: MODELING DATASETS + GROUPED REPEATED CROSS-VALIDATION")
    print("=" * 100)
    results = {}
    for target in SECONDARY_TARGETS:
        safe_cols = secondary_safe_feature_columns(target, df)
        print(f"\n-- {target} -- ({len(safe_cols)} safe features)")

        if target in MULTICLASS_TARGETS:
            cv_df, meta = run_multiclass_cv(df, target, safe_cols)
        else:
            cv_df, meta = run_binary_cv(df, target, safe_cols)

        if meta.get("skipped"):
            print(f"  SKIPPED: {meta['reason']}")
            results[target] = {"meta": meta, "cv_rows": [], "stability": {}}
            continue

        print(f"  folds={meta['n_splits']}  repeats={meta['n_repeats']}  min_class_size={meta['min_class_size']}")
        metric_cols = [c for c in cv_df.columns if c not in ("target", "model", "seed", "fold", "n_train", "n_val")]
        stability = {}
        for model_name, group in cv_df.groupby("model"):
            stability[model_name] = {}
            for metric in metric_cols:
                stability[model_name][metric] = summarize_stability(group[metric].tolist())
            m = stability[model_name]
            print(f"    {model_name}: " + "  ".join(
                f"{metric}={m[metric]['mean']:.3f}(+/-{(m[metric]['ci95'][1]-m[metric]['mean']):.3f})" if m[metric]["mean"] is not None else f"{metric}=N/A"
                for metric in metric_cols if metric in ("accuracy", "macro_f1", "weighted_f1", "f1", "pr_auc", "roc_auc", "roc_auc_ovr_macro")
            ))
        results[target] = {"meta": meta, "cv_rows": cv_df.to_dict(orient="records"), "stability": stability}

    return results


def section_rule_baselines(df: pd.DataFrame) -> dict:
    print()
    print("=" * 100)
    print("SECTION 7: RULE BASELINES FOR SECONDARY TARGETS")
    print("=" * 100)
    results = {}

    print("\n-- frd_Risk_Category --")
    print(f"  {NO_BASELINE_STATEMENT}")
    results["frd_Risk_Category"] = {"implemented": False, "statement": NO_BASELINE_STATEMENT}

    print("\n-- cdc_Overall_Consistency_Status --")
    print(f"  {NO_BASELINE_STATEMENT}")
    results["cdc_Overall_Consistency_Status"] = {"implemented": False, "statement": NO_BASELINE_STATEMENT}

    print("\n-- est_Excessive_Claim_Amount_Indicator --")
    cv_df, meta = run_rule_baseline_cv(df, "est_Excessive_Claim_Amount_Indicator", lambda: ExcessiveAmountRuleScreener(), "rule_baseline")
    metric_cols = [c for c in cv_df.columns if c not in ("target", "model", "seed", "fold", "n_train", "n_val")]
    stability = {m: summarize_stability(cv_df[m].tolist()) for m in metric_cols}
    print(f"  folds={meta['n_splits']}  repeats={meta['n_repeats']}")
    print("  " + "  ".join(f"{m}={stability[m]['mean']:.3f}" for m in ("accuracy", "precision", "recall", "f1", "pr_auc") if stability[m]["mean"] is not None))
    results["est_Excessive_Claim_Amount_Indicator"] = {
        "implemented": True, "meta": meta, "cv_rows": cv_df.to_dict(orient="records"), "stability": stability,
    }
    return results


def section_rule_baseline_v2_and_fraud_robustness(df: pd.DataFrame) -> dict:
    print()
    print("=" * 100)
    print("SECTION 12: RULE BASELINE V2 (fraud) - evaluated on the SAME Step 5.2 test set")
    print("=" * 100)
    train_idx, test_idx = create_grouped_split(df)
    train_df, test_df = df.iloc[train_idx], df.iloc[test_idx]
    y_test = test_df[FRAUD_TARGET].astype(int)

    v1 = RuleBasedFraudScreener()
    v1.fit(train_df)
    v1_predictions = v1.predict(test_df)
    v1_metrics = evaluate_binary(y_test, v1_predictions["Rule_Baseline_Prediction"], v1_predictions["Rule_Baseline_Score"])

    v2, v2_calibration = calibrate_rule_baseline_v2(train_df)
    v2_predictions = v2.predict(test_df)
    v2_metrics = evaluate_binary(y_test, v2_predictions["Rule_Baseline_Prediction"], v2_predictions["Rule_Baseline_Score"])

    print(f"Rule Baseline v1 (default OR-like, overall_threshold=1.0): "
          f"Precision={v1_metrics['precision']:.3f} Recall={v1_metrics['recall']:.3f} F1={v1_metrics['f1']:.3f} "
          f"PR-AUC={v1_metrics['pr_auc']:.3f} predicted_positive={v1_metrics['n_positive_predicted']}/{v1_metrics['n_test']}")
    print(f"Rule Baseline v2 (scored, overall_threshold={v2_calibration['chosen_overall_threshold']}, "
          f"calibrated on TRAIN only via inner split): "
          f"Precision={v2_metrics['precision']:.3f} Recall={v2_metrics['recall']:.3f} F1={v2_metrics['f1']:.3f} "
          f"PR-AUC={v2_metrics['pr_auc']:.3f} predicted_positive={v2_metrics['n_positive_predicted']}/{v2_metrics['n_test']}")

    print()
    print("=" * 100)
    print("SECTION 13: FRAUD REPEATED-GROUPED-CV ROBUSTNESS (LR vs RF vs Rule v1 vs Rule v2)")
    print("=" * 100)
    from ai_ml.common.feature_builder import safe_feature_columns
    fraud_safe_cols = safe_feature_columns(FRAUD_TARGET, df)
    ml_cv_df, ml_meta = run_binary_cv(df, FRAUD_TARGET, fraud_safe_cols)
    rule_v1_cv_df, rule_meta = run_rule_baseline_cv(df, FRAUD_TARGET, lambda: RuleBasedFraudScreener(), "rule_baseline_v1")
    rule_v2_cv_df, _ = run_rule_baseline_cv(
        df, FRAUD_TARGET,
        lambda: RuleBasedFraudScreener(overall_threshold=v2_calibration["chosen_overall_threshold"]),
        "rule_baseline_v2",
    )
    combined_cv_df = pd.concat([ml_cv_df, rule_v1_cv_df, rule_v2_cv_df], ignore_index=True)

    stability_by_model = {}
    for model_name, group in combined_cv_df.groupby("model"):
        stability_by_model[model_name] = {m: summarize_stability(group[m].tolist()) for m in ("precision", "recall", "f1", "pr_auc", "roc_auc")}
        s = stability_by_model[model_name]
        print(f"  {model_name}: PR-AUC={s['pr_auc']['mean']:.3f} (std={s['pr_auc']['std']:.3f})  "
              f"F1={s['f1']['mean']:.3f} (std={s['f1']['std']:.3f})  Recall={s['recall']['mean']:.3f}")

    pr_auc_means = {m: s["pr_auc"]["mean"] for m, s in stability_by_model.items() if s["pr_auc"]["mean"] is not None}
    pr_auc_stds = {m: s["pr_auc"]["std"] or 0.0 for m in pr_auc_means}
    rf_mean, lr_mean = pr_auc_means.get("random_forest"), pr_auc_means.get("logistic_regression")
    stable_rf_advantage = None
    if rf_mean is not None and lr_mean is not None:
        gap = rf_mean - lr_mean
        combined_std = np.sqrt(pr_auc_stds.get("random_forest", 0) ** 2 + pr_auc_stds.get("logistic_regression", 0) ** 2)
        stable_rf_advantage = bool(abs(gap) > combined_std) if combined_std > 0 else None
        print(f"\n  Random Forest vs Logistic Regression PR-AUC gap under CV: {gap:+.3f} "
              f"(combined std {combined_std:.3f}) -> {'stable' if stable_rf_advantage else 'NOT stable / within noise'}")

    return {
        "test_set_single_split": {
            "rule_baseline_v1": v1_metrics,
            "rule_baseline_v2": v2_metrics,
            "v2_calibration": v2_calibration,
        },
        "repeated_cv": {
            "meta": {"ml": ml_meta, "rule": rule_meta},
            "stability_by_model": stability_by_model,
            "rf_vs_lr_pr_auc_gap_stable": stable_rf_advantage,
            "cv_rows": combined_cv_df.to_dict(orient="records"),
        },
    }


def section_explainability(df: pd.DataFrame) -> dict:
    print()
    print("=" * 100)
    print("SECTION 14: EXPLAINABILITY FOR THE STRONGEST SECONDARY TARGET")
    print("=" * 100)
    target = "est_Excessive_Claim_Amount_Indicator"
    safe_cols = secondary_safe_feature_columns(target, df)
    report = classify_feature_columns(df, safe_cols)
    feature_cols = report["numeric"] + report["categorical"]

    train_idx, test_idx = create_grouped_split(df)
    X_train = df.iloc[train_idx][feature_cols]
    y_train = df.iloc[train_idx][target].astype(int)
    X_test = df.iloc[test_idx][feature_cols]

    preprocessor = build_preprocessor(report["numeric"], report["categorical"])
    rf_pipeline = train_random_forest(X_train, y_train, preprocessor, class_weight="balanced")
    rf_proba = rf_pipeline.predict_proba(X_test)[:, 1]

    top5_idx = np.argsort(-rf_proba)[:5]
    X_explain = X_test.iloc[top5_idx]
    claim_ids = df.iloc[test_idx]["Claim_ID"].values[top5_idx]

    _, _, top_factors_per_row = explain_claims(rf_pipeline, "random_forest", X_train, X_explain, top_n=3)
    explanations = []
    for row_i, claim_id in enumerate(claim_ids):
        reason_codes = to_reason_codes(top_factors_per_row[row_i])
        probability = float(rf_proba[top5_idx[row_i]])
        explanation = build_claim_explanation(str(claim_id), risk_level_from_probability(probability), reason_codes)
        explanation["model"] = "random_forest"
        explanation["target"] = target
        explanation["probability"] = probability
        explanation["top_shap_features"] = top_factors_per_row[row_i]
        explanation["label_type"] = "Model contribution / screening signal - NOT a confirmed cause"
        explanations.append(explanation)
        print(f"  Claim {claim_id} (p={probability:.3f}): {explanation['fraud_screening_risk']} - {reason_codes}")

    print("  NOTE: this target showed weak/near-chance CV performance (see Section 6/9 results) - "
          "these explanations are included to demonstrate the explainability pipeline generalizes beyond "
          "fraud, NOT as evidence the model is production-ready.")
    return {"target": target, "explanations": explanations}


def section_figures(secondary_cv_results: dict, fraud_robustness: dict, target_audits: dict) -> list[str]:
    print()
    print("=" * 100)
    print("SECTION 15: FIGURES")
    print("=" * 100)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    saved = []

    # 1. Target class distributions
    fig, axes = plt.subplots(1, len(SECONDARY_TARGETS), figsize=(5 * len(SECONDARY_TARGETS), 4))
    for ax, target in zip(axes, SECONDARY_TARGETS):
        counts = target_audits[target]["class_counts"]
        ax.bar([str(k) for k in counts.keys()], list(counts.values()), color="steelblue")
        ax.set_title(target, fontsize=9)
        ax.tick_params(axis="x", rotation=30, labelsize=8)
    fig.suptitle("Secondary target class distributions")
    fig.tight_layout()
    path = FIGURE_DIR / "target_class_distributions.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    saved.append(str(path))

    # 2. Model metric comparison (mean PR-AUC/macro-F1 per target/model)
    fig, ax = plt.subplots(figsize=(8, 5))
    labels, values, colors = [], [], []
    for target, result in secondary_cv_results.items():
        stability = result.get("stability", {})
        for model_name, metrics in stability.items():
            headline = metrics.get("pr_auc") or metrics.get("macro_f1")
            if headline and headline["mean"] is not None:
                labels.append(f"{target.split('_', 1)[-1][:14]}\n{model_name}")
                values.append(headline["mean"])
                colors.append("darkorange" if model_name == "random_forest" else "steelblue")
    ax.bar(labels, values, color=colors)
    ax.set_ylabel("Mean CV headline metric (PR-AUC or macro-F1)")
    ax.tick_params(axis="x", labelsize=7)
    fig.tight_layout()
    path = FIGURE_DIR / "secondary_target_model_comparison.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    saved.append(str(path))

    # 3. Fraud PR-AUC comparison under repeated CV (with std error bars)
    stability = fraud_robustness["repeated_cv"]["stability_by_model"]
    fig, ax = plt.subplots(figsize=(6, 4))
    names = list(stability.keys())
    means = [stability[n]["pr_auc"]["mean"] or 0 for n in names]
    stds = [stability[n]["pr_auc"]["std"] or 0 for n in names]
    ax.bar(names, means, yerr=stds, capsize=4, color="seagreen")
    ax.set_ylabel("PR-AUC (mean +/- std across repeated grouped CV)")
    ax.set_title("Fraud detection: PR-AUC stability under repeated grouped CV")
    ax.tick_params(axis="x", rotation=20, labelsize=8)
    fig.tight_layout()
    path = FIGURE_DIR / "fraud_pr_auc_cv_comparison.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    saved.append(str(path))

    for p in saved:
        print(f"  saved {p}")
    return saved


def main() -> None:
    df = add_engineered_features(build_claim_level_dataset())
    if df["Claim_ID"].duplicated().any():
        raise AssertionError("Claim_ID duplicated in claim-level dataset - refusing to proceed.")
    print(f"Claim-level dataset: {len(df)} rows, Claim_ID unique: {df['Claim_ID'].is_unique}")

    target_audits = section_target_audits(df)
    leakage_reports = section_leakage_reports(df)
    relationship_analysis = section_relationship_analysis(df)
    secondary_cv_results = section_secondary_target_cv(df)
    rule_baseline_results = section_rule_baselines(df)
    fraud_robustness = section_rule_baseline_v2_and_fraud_robustness(df)
    explainability = section_explainability(df)
    figures = section_figures(secondary_cv_results, fraud_robustness, target_audits)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "target_audits": target_audits,
        "leakage_reports": leakage_reports,
        "relationship_analysis": relationship_analysis,
        "secondary_cv_results": secondary_cv_results,
        "rule_baseline_results": rule_baseline_results,
        "fraud_robustness": fraud_robustness,
        "explainability": explainability,
        "figures": figures,
    }
    with open(ARTIFACT_DIR / "secondary_targets_summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print()
    print("=" * 100)
    print("DATA INTEGRITY CHECK")
    print("=" * 100)
    print(f"claims in dataset: {len(df)} (expected 654)")
    print(f"Claim_ID unique: {df['Claim_ID'].is_unique}")
    print(f"Full summary saved to {ARTIFACT_DIR / 'secondary_targets_summary.json'}")


if __name__ == "__main__":
    main()
