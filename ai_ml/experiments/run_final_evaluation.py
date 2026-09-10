"""Step 5.7: consolidates the ACTUAL measured results from Steps 5.2-5.4
and 5.6 into one comparison table, figure, and report. This module runs
NO new experiments - it only reads the artifact files those steps already
produced (`ai_ml/model_artifacts/{evaluation_results.json,
secondary_targets/secondary_targets_summary.json,
risk_fusion/risk_fusion_summary.json, aco/aco_results.csv}`) and fails
loudly if one is missing, rather than fabricating a substitute number.

Run from the repo root:
    python -m ai_ml.experiments.run_final_evaluation

See docs/project_documentation/FINAL_AI_VS_NON_AI_EVALUATION.md for the
narrative report built from this table.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

MODEL_ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "model_artifacts"
OUTPUT_DIR = MODEL_ARTIFACTS_DIR / "final_evaluation"

STEP52_RESULTS = MODEL_ARTIFACTS_DIR / "evaluation_results.json"
STEP53_RESULTS = MODEL_ARTIFACTS_DIR / "secondary_targets" / "secondary_targets_summary.json"
STEP54_RESULTS = MODEL_ARTIFACTS_DIR / "risk_fusion" / "risk_fusion_summary.json"
STEP56_RESULTS = MODEL_ARTIFACTS_DIR / "aco" / "aco_results.csv"

NOT_MEASURED = "Not measured in the current experiment."
NOT_TESTED = "Not formally tested (no significance test was run)."


def _require(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(
            f"Required Step 5.2-5.6 artifact not found: {path}. "
            "Step 5.7 consolidates existing results and does not fabricate a substitute - "
            "re-run the corresponding experiment script (see docs/project_documentation/) first."
        )


def load_source_results() -> dict:
    """Reads every prior-step artifact this report depends on. Raises
    loudly (never silently substitutes a value) if one is missing."""
    for path in (STEP52_RESULTS, STEP53_RESULTS, STEP54_RESULTS, STEP56_RESULTS):
        _require(path)

    with open(STEP52_RESULTS) as f:
        step52 = json.load(f)
    with open(STEP53_RESULTS) as f:
        step53 = json.load(f)
    with open(STEP54_RESULTS) as f:
        step54 = json.load(f)
    step56 = pd.read_csv(STEP56_RESULTS)

    return {"step52": step52, "step53": step53, "step54": step54, "step56": step56}


def _round(value, ndigits=4):
    return None if value is None else round(float(value), ndigits)


def build_quantitative_rows(sources: dict) -> list[dict]:
    step52, step53, step54, step56 = sources["step52"], sources["step53"], sources["step54"], sources["step56"]
    rows: list[dict] = []

    def add(component, baseline_method, ai_method, metric, baseline_value, ai_value, significance, interpretation, data_source):
        diff = None
        if isinstance(baseline_value, (int, float)) and isinstance(ai_value, (int, float)):
            diff = _round(ai_value - baseline_value)
        rows.append({
            "component": component, "baseline_method": baseline_method, "ai_method": ai_method, "metric": metric,
            "baseline_value": baseline_value, "ai_value": ai_value, "difference": diff,
            "statistical_significance": significance, "interpretation": interpretation,
            "data_source": data_source, "measured_or_qualitative": "quantitative",
        })

    # --- A. Fraud screening: Step 5.2 single train/test split ---
    rb = step52["rule_baseline"]
    lr = step52["logistic_regression_0.5"]
    rf = step52["random_forest_0.5"]
    add("Fraud screening (single split)", "Rule Baseline", "Logistic Regression", "PR-AUC",
        _round(rb["pr_auc"]), _round(lr["pr_auc"]), NOT_TESTED,
        "LR had a nominally higher PR-AUC than the rule baseline on this one split.",
        "Step 5.2 evaluation_results.json")
    add("Fraud screening (single split)", "Rule Baseline", "Random Forest", "PR-AUC",
        _round(rb["pr_auc"]), _round(rf["pr_auc"]), NOT_TESTED,
        "RF had the highest single-split PR-AUC in Step 5.2, but see the repeated-CV row below - this did not hold up.",
        "Step 5.2 evaluation_results.json")
    add("Fraud screening (single split)", "Rule Baseline", "Random Forest", "Precision",
        _round(rb["precision"]), _round(rf["precision"]), NOT_TESTED,
        "RF's higher precision came with much lower recall (see Recall row) - a precision/recall trade-off, not an unqualified improvement.",
        "Step 5.2 evaluation_results.json")
    add("Fraud screening (single split)", "Rule Baseline", "Random Forest", "Recall",
        _round(rb["recall"]), _round(rf["recall"]), NOT_TESTED,
        "The rule baseline over-triggers (high recall, low precision); RF under-triggers (the opposite trade-off) at the default 0.5 threshold.",
        "Step 5.2 evaluation_results.json")

    # --- A. Fraud screening: Step 5.3 repeated grouped CV ---
    fr = step53["fraud_robustness"]["repeated_cv"]["stability_by_model"]
    rf_vs_lr_stable = step53["fraud_robustness"]["repeated_cv"]["rf_vs_lr_pr_auc_gap_stable"]
    add("Fraud screening (5-fold x 3-seed grouped CV)", "Rule Baseline v1", "Logistic Regression", "PR-AUC",
        _round(fr["rule_baseline_v1"]["pr_auc"]["mean"]), _round(fr["logistic_regression"]["pr_auc"]["mean"]), NOT_TESTED,
        "LR remained nominally ahead of the rule baseline under repeated CV.",
        "Step 5.3 secondary_targets_summary.json")
    add("Fraud screening (5-fold x 3-seed grouped CV)", "Rule Baseline v1", "Random Forest", "PR-AUC",
        _round(fr["rule_baseline_v1"]["pr_auc"]["mean"]), _round(fr["random_forest"]["pr_auc"]["mean"]), NOT_TESTED,
        "RF remained nominally ahead of the rule baseline under repeated CV, but by less than its single-split margin.",
        "Step 5.3 secondary_targets_summary.json")
    add("Fraud screening (5-fold x 3-seed grouped CV)", "Logistic Regression", "Random Forest", "PR-AUC",
        _round(fr["logistic_regression"]["pr_auc"]["mean"]), _round(fr["random_forest"]["pr_auc"]["mean"]),
        f"NOT stable: gap ({_round(fr['random_forest']['pr_auc']['mean'] - fr['logistic_regression']['pr_auc']['mean'])}) is smaller than the combined standard deviation (LR std={_round(fr['logistic_regression']['pr_auc']['std'])}, RF std={_round(fr['random_forest']['pr_auc']['std'])}).",
        "Step 5.2's single-split finding that Random Forest outperforms Logistic Regression DID NOT hold under repeated grouped cross-validation and reversed in mean.",
        "Step 5.3 secondary_targets_summary.json")

    v1v2 = step53["fraud_robustness"]["test_set_single_split"]
    add("Fraud rule baseline v1 vs v2 (single split)", "Rule Baseline v1", "Rule Baseline v2 (calibrated)", "F1",
        _round(v1v2["rule_baseline_v1"]["f1"]), _round(v1v2["rule_baseline_v2"]["f1"]), NOT_TESTED,
        "v2's higher decision threshold modestly improved precision and F1 at a small recall cost - a real but small improvement, not a breakthrough.",
        "Step 5.3 secondary_targets_summary.json")

    # --- B. Risk fusion: Step 5.4 repeated grouped CV ---
    cv = step54["comparison_cv"]["stability"]
    add("Risk fusion (5-fold x 3-seed grouped CV)", "Individual fraud signal", "Equal-weight fusion", "PR-AUC",
        _round(cv["individual_fraud_signal"]["pr_auc"]["mean"]), _round(cv["equal_weight_fusion"]["pr_auc"]["mean"]), NOT_TESTED,
        "Equal-weight fusion did NOT outperform the individual fraud-screening signal.",
        "Step 5.4 risk_fusion_summary.json")
    weighted_gap = _round(cv["configurable_weighted_fusion"]["pr_auc"]["mean"] - cv["individual_fraud_signal"]["pr_auc"]["mean"])
    add("Risk fusion (5-fold x 3-seed grouped CV)", "Individual fraud signal", "Configurable weighted fusion", "PR-AUC",
        _round(cv["individual_fraud_signal"]["pr_auc"]["mean"]), _round(cv["configurable_weighted_fusion"]["pr_auc"]["mean"]),
        f"Gap ({weighted_gap}) is smaller than weighted fusion's own CV standard deviation ({_round(cv['configurable_weighted_fusion']['pr_auc']['std'])}).",
        "Weighted fusion produced a nominally higher PR-AUC, but the difference was not statistically meaningful.",
        "Step 5.4 risk_fusion_summary.json")

    # --- C. Consistency: Step 5.3 repeated grouped CV ---
    consistency_audit = step53["target_audits"]["cdc_Overall_Consistency_Status"]
    majority_class_pct = max(consistency_audit["class_percentages"].values()) / 100
    consistency_cv = step53["secondary_cv_results"]["cdc_Overall_Consistency_Status"]["stability"]
    add("Document consistency prediction (5-fold x 3-seed grouped CV)", "Majority-class baseline (always predict \"Match\")", "Logistic Regression", "Accuracy",
        _round(majority_class_pct), _round(consistency_cv["logistic_regression"]["accuracy"]["mean"]), NOT_TESTED,
        "Logistic Regression scored BELOW the trivial majority-class baseline on accuracy.",
        "Step 5.3 secondary_targets_summary.json")
    add("Document consistency prediction (5-fold x 3-seed grouped CV)", "Majority-class baseline (always predict \"Match\")", "Random Forest", "Accuracy",
        _round(majority_class_pct), _round(consistency_cv["random_forest"]["accuracy"]["mean"]), NOT_TESTED,
        "Random Forest also scored below the trivial majority-class baseline on accuracy.",
        "Step 5.3 secondary_targets_summary.json")

    # --- D. Excessive claim amount: Step 5.3 repeated grouped CV ---
    excessive_cv = step53["secondary_cv_results"]["est_Excessive_Claim_Amount_Indicator"]["stability"]
    excessive_rule_cv = step53["rule_baseline_results"]["est_Excessive_Claim_Amount_Indicator"]["stability"]
    add("Excessive claim amount prediction (5-fold x 3-seed grouped CV)", "Rule baseline (repair-ratio threshold)", "Logistic Regression", "PR-AUC",
        _round(excessive_rule_cv["pr_auc"]["mean"]), _round(excessive_cv["logistic_regression"]["pr_auc"]["mean"]), NOT_TESTED,
        "Both are at chance level; neither meaningfully beats the other.",
        "Step 5.3 secondary_targets_summary.json")
    add("Excessive claim amount prediction (5-fold x 3-seed grouped CV)", "Rule baseline", "Random Forest", "PR-AUC",
        _round(excessive_rule_cv["pr_auc"]["mean"]), _round(excessive_cv["random_forest"]["pr_auc"]["mean"]), NOT_TESTED,
        "Both are at chance level; RF is nominally lower than the rule baseline here.",
        "Step 5.3 secondary_targets_summary.json")

    # --- E. Surveyor assignment: Step 5.6 ---
    aco = step56.set_index("Metric")
    for metric_name, row_label in [
        ("Total Cost", "Total assignment cost"), ("Total Distance", "Total distance"),
        ("Workload Imbalance (std)", "Workload imbalance"), ("Priority Handling Score (lower=better)", "Priority handling score"),
        ("Runtime (s)", "Runtime (seconds)"), ("Unassigned Claims", "Unassigned claims"),
    ]:
        r = aco.loc[metric_name]
        add("Surveyor assignment (5-scenario mean, seeds 101/202/303/404/505)", "Greedy nearest-available", "Ant Colony Optimization", row_label,
            _round(r["Baseline (greedy)"]), _round(r["ACO"]), NOT_TESTED, r["Interpretation"],
            "Step 5.6 aco_results.csv")

    return rows


CAPABILITY_MATRIX = [
    ("OCR / information extraction", "Manual reading of documents by staff", "PARTIAL", "Document/evidence fields (OCR_Confidence_Score, completeness) exist in the dataset and are consumed as signals; no OCR engine was built or run in Steps 5.1-5.7."),
    ("Cross-document consistency", "Manual comparison across documents", "AVAILABLE", "Implemented as a real signal (document_consistency_mismatch) from existing cross_document_consistency fields, used in the rule baseline and risk fusion."),
    ("Repair-estimate anomaly analysis", "Manual estimate review", "AVAILABLE", "Implemented as a real signal (repair_estimate_anomaly), used in the rule baseline and risk fusion."),
    ("Evidence duplication analysis", "Manual evidence review", "AVAILABLE", "Implemented as a real signal (evidence_duplication)."),
    ("Fraud screening", "Rule-of-thumb / manual judgment", "EXPERIMENTAL", "Rule baseline and ML models implemented and evaluated; predictive performance was weak-to-chance-level on this synthetic dataset (Steps 5.2/5.3)."),
    ("Risk fusion (multi-signal)", "Not applicable (single judgment call)", "EXPERIMENTAL", "Implemented (equal-weight and configurable-weighted fusion); did not show a statistically meaningful improvement over the single strongest signal (Step 5.4)."),
    ("Uncertainty estimation", "Implicit / not formalized", "EXPERIMENTAL", "Implemented as an explicit confidence/uncertainty score, independent of the risk score (Step 5.4)."),
    ("Explainability / reason codes", "Officer's own reasoning, undocumented", "AVAILABLE", "Implemented: every signal and fused score carries a plain-language, officer-facing explanation and reason code (Steps 5.2-5.5)."),
    ("Review prioritization", "FIFO / manual triage", "EXPERIMENTAL", "Implemented as a 4-band recommendation (Step 5.4); prioritization logic is rule-based on risk+confidence, not learned or benchmarked against real triage outcomes."),
    ("Surveyor optimization", "Manual / ad hoc assignment", "EXPERIMENTAL", "Greedy and ACO implemented and compared on a synthetic scenario (Step 5.6); ACO did not consistently outperform the greedy baseline."),
    ("Auditability", "Paper/manual trail", "AVAILABLE", "Every AI signal, fusion score, and reason code is traceable to its source column and computation (Steps 5.1-5.5)."),
    ("Customer-facing explanation", "Officer explains verbally/in writing", "NOT MEASURED", "No customer-facing explanation surface was built or evaluated in Steps 5.1-5.7."),
    ("Human-in-the-loop", "Officer decides everything", "AVAILABLE", "Enforced throughout: no AI/optimization output in this project can approve, reject, or auto-assign a claim (Steps 5.4-5.6)."),
]


def build_capability_rows() -> list[dict]:
    rows = []
    for capability, traditional, ci_micop_status, evidence in CAPABILITY_MATRIX:
        rows.append({
            "component": f"Capability: {capability}", "baseline_method": traditional, "ai_method": f"CI-MICOP: {ci_micop_status}",
            "metric": "Capability status", "baseline_value": "N/A", "ai_value": ci_micop_status, "difference": "N/A",
            "statistical_significance": "N/A (qualitative)", "interpretation": evidence,
            "data_source": "Steps 5.1-5.6 implementation", "measured_or_qualitative": "qualitative",
        })
    return rows


def build_final_comparison_table() -> pd.DataFrame:
    sources = load_source_results()
    rows = build_quantitative_rows(sources) + build_capability_rows()
    return pd.DataFrame(rows, columns=[
        "component", "baseline_method", "ai_method", "metric", "baseline_value", "ai_value",
        "difference", "statistical_significance", "interpretation", "data_source", "measured_or_qualitative",
    ])


def generate_figure(save_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch

    non_ai_steps = ["Claim\nfiled", "Manual\ndocument review", "Manual cross-\ndocument comparison", "Manual risk\nassessment", "Officer\ndecision"]
    ai_steps = ["Claim\nfiled", "OCR /\nextraction", "Multiple AI\nsignals", "Risk\nfusion", "Uncertainty +\nexplainability", "Review\npriority", "Claims\nOfficer", "Final\ndecision (human)"]

    fig, axes = plt.subplots(2, 1, figsize=(11, 7))

    for ax, steps, title, color in [
        (axes[0], non_ai_steps, "Non-AI baseline workflow (research prototype)", "#6b7280"),
        (axes[1], ai_steps, "AI-assisted CI-MICOP workflow", "#2563eb"),
    ]:
        n = len(steps)
        xs = [i / (n - 1) for i in range(n)]
        for x, label in zip(xs, steps):
            is_human = "Officer" in label or "human" in label
            box_color = "#fde68a" if is_human else color
            ax.scatter([x], [0.5], s=3200, color=box_color, edgecolor="black", zorder=3, marker="s")
            ax.text(x, 0.5, label, ha="center", va="center", fontsize=8, zorder=4, wrap=True)
        for x1, x2 in zip(xs, xs[1:]):
            arrow = FancyArrowPatch((x1 + 0.045, 0.5), (x2 - 0.045, 0.5), arrowstyle="-|>", mutation_scale=14, color="black", zorder=2)
            ax.add_patch(arrow)
        ax.set_xlim(-0.06, 1.06)
        ax.set_ylim(0, 1)
        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.axis("off")

    fig.suptitle(
        "CI-MICOP: AI-Assisted vs Non-AI Workflow (research prototype - synthetic dataset)\n"
        "Both workflows end in a human Claims Officer decision - AI never decides autonomously.",
        fontsize=10,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    save_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(save_path, dpi=150)
    plt.close(fig)


def generate_final_conclusion(table: pd.DataFrame) -> str:
    quantitative = table[table["measured_or_qualitative"] == "quantitative"]
    ai_wins = 0
    baseline_wins = 0
    for _, row in quantitative.iterrows():
        if not isinstance(row["difference"], (int, float)) or row["difference"] is None:
            continue
        lower_is_better = row["metric"] in {"Runtime (seconds)", "Workload imbalance", "Priority handling score", "Total distance", "Unassigned claims"}
        if row["difference"] == 0:
            continue
        ai_better = (row["difference"] < 0) if lower_is_better else (row["difference"] > 0)
        if ai_better:
            ai_wins += 1
        else:
            baseline_wins += 1

    return (
        "Does CI-MICOP prove that AI is better than non-AI? Not universally, based on the current synthetic "
        "dataset. The experiments did not establish statistically meaningful predictive superiority: fraud "
        "screening PR-AUC differences between the rule baseline and ML models were within run-to-run "
        "variability under repeated grouped cross-validation, Risk_Category/Consistency/Excessive-Claim-Amount "
        "prediction were approximately chance level, multi-signal risk fusion did not significantly beat the "
        "single strongest signal, and Ant Colony Optimization did not consistently outperform a simple greedy "
        f"surveyor-assignment baseline ({ai_wins} of {ai_wins + baseline_wins} directly-compared quantitative "
        "metrics nominally favored the AI/optimization method; nominal favorability was not confirmed as "
        "statistically significant in any of them). However, CI-MICOP demonstrates a broader decision-support "
        "capability through automated signal generation, multi-signal fusion, uncertainty estimation, "
        "explainability, and structured human-review prioritization - none of which the non-AI baseline "
        "provides in a comparably systematic, auditable form."
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    table = build_final_comparison_table()
    csv_path = OUTPUT_DIR / "final_comparison.csv"
    table.to_csv(csv_path, index=False)
    print(f"Saved {csv_path} ({len(table)} rows)")

    figure_path = OUTPUT_DIR / "ci_micop_ai_vs_non_ai.png"
    generate_figure(figure_path)
    print(f"Saved {figure_path}")

    conclusion = generate_final_conclusion(table)
    conclusion_path = OUTPUT_DIR / "final_conclusion.txt"
    conclusion_path.write_text(conclusion)
    print(f"Saved {conclusion_path}")
    print()
    print("=" * 100)
    print("FINAL CONCLUSION")
    print("=" * 100)
    print(conclusion)


if __name__ == "__main__":
    main()
