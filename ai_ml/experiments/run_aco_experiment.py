"""Step 5.6 experiment: Ant Colony Optimization vs. a transparent greedy
baseline for claim-to-surveyor assignment, on a SYNTHETIC optimization
scaffold (real Claim_ID/Surveyor_ID identifiers, synthetic location/
workload/priority/availability attributes - see
ai_ml/surveyor_assignment/synthetic_scenario.py and
docs/project_documentation/ACO_SURVEYOR_ASSIGNMENT.md).

Research question: "Can Ant Colony Optimization provide a better
surveyor assignment strategy than a simple baseline assignment strategy
when considering workload, claim priority and assignment cost?"

Run from the repo root:
    python -m ai_ml.experiments.run_aco_experiment

This is a research-prototype algorithm comparison on a synthetic
scenario. It is NOT connected to the live application (no frontend/
backend/database changes), and does not claim ACO is universally better,
production-ready, or validated on real operational data.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from ai_ml.surveyor_assignment.aco_optimizer import DEFAULT_ACO_PARAMETERS, ant_colony_optimize
from ai_ml.surveyor_assignment.baseline_assignment import greedy_nearest_available, least_loaded_assignment
from ai_ml.surveyor_assignment.cost_function import DEFAULT_WEIGHTS
from ai_ml.surveyor_assignment.evaluation import evaluate_result
from ai_ml.surveyor_assignment.synthetic_scenario import generate_scenario
from ai_ml.surveyor_assignment.validation import assert_scenarios_match, validate_result
from ai_ml.surveyor_assignment.visualization import plot_assignment, plot_convergence

ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "model_artifacts" / "aco"

EVALUATION_SEEDS = [101, 202, 303, 404, 505]
MAIN_SCENARIO_SIZE = {"n_claims": 50, "n_surveyors": 20}
REPRESENTATIVE_SEED = 101  # used for the convergence plot / assignment visualization / saved best-assignment JSON

STRESS_TEST_SIZES = [
    {"n_surveyors": 20, "n_claims": 50},
    {"n_surveyors": 30, "n_claims": 100},
    {"n_surveyors": 40, "n_claims": 150},
]
STRESS_TEST_SEED = 42


def run_one_scenario(n_claims: int, n_surveyors: int, seed: int, use_real_ids: bool) -> dict:
    scenario_baseline = generate_scenario(n_claims, n_surveyors, seed, use_real_ids=use_real_ids)
    scenario_aco = generate_scenario(n_claims, n_surveyors, seed, use_real_ids=use_real_ids)
    assert_scenarios_match(scenario_baseline, scenario_aco)  # same seed -> identical scenario, confirmed

    greedy_result = greedy_nearest_available(scenario_baseline, DEFAULT_WEIGHTS)
    least_loaded_result = least_loaded_assignment(scenario_baseline, DEFAULT_WEIGHTS)
    aco_result = ant_colony_optimize(scenario_aco, DEFAULT_WEIGHTS, DEFAULT_ACO_PARAMETERS)

    for scenario, result in [(scenario_baseline, greedy_result), (scenario_baseline, least_loaded_result), (scenario_aco, aco_result)]:
        validate_result(scenario, result, DEFAULT_WEIGHTS)

    return {
        "seed": seed,
        "scenario": scenario_aco,
        "greedy": greedy_result,
        "least_loaded": least_loaded_result,
        "aco": aco_result,
        "greedy_eval": evaluate_result(scenario_baseline, greedy_result),
        "least_loaded_eval": evaluate_result(scenario_baseline, least_loaded_result),
        "aco_eval": evaluate_result(scenario_aco, aco_result),
    }


def section_five_scenarios() -> pd.DataFrame:
    print("=" * 100)
    print("PART 9: FIVE-SCENARIO EVALUATION (seeds 101/202/303/404/505, 50 claims / 20 surveyors, real IDs)")
    print("=" * 100)
    rows = []
    for seed in EVALUATION_SEEDS:
        outcome = run_one_scenario(seed=seed, use_real_ids=True, **MAIN_SCENARIO_SIZE)
        for strategy in ("greedy", "least_loaded", "aco"):
            row = dict(outcome[f"{strategy}_eval"])
            row["seed"] = seed
            row["strategy"] = strategy
            rows.append(row)
        print(f"  seed={seed}: greedy total_cost={outcome['greedy_eval']['total_cost']:.3f}  "
              f"aco total_cost={outcome['aco_eval']['total_cost']:.3f}  "
              f"least_loaded total_cost={outcome['least_loaded_eval']['total_cost']:.3f}")

    df = pd.DataFrame(rows)
    print("\nMean / std / min / max across the 5 scenarios (greedy vs aco):")
    for metric in ["total_cost", "total_distance_raw", "workload_imbalance_std", "max_load_ratio", "n_unassigned", "runtime_seconds"]:
        for strategy in ("greedy", "aco"):
            values = df[df["strategy"] == strategy][metric]
            print(f"  {strategy:12s} {metric:24s} mean={values.mean():.4f} std={values.std():.4f} min={values.min():.4f} max={values.max():.4f}")
    return df


def section_stress_test() -> pd.DataFrame:
    print()
    print("=" * 100)
    print("PART 10: SCALABILITY STRESS TEST (fully synthetic identifiers - see module docstring)")
    print("=" * 100)
    rows = []
    for size in STRESS_TEST_SIZES:
        outcome = run_one_scenario(seed=STRESS_TEST_SEED, use_real_ids=False, **size)
        for strategy in ("greedy", "aco"):
            row = dict(outcome[f"{strategy}_eval"])
            row["n_surveyors_requested"] = size["n_surveyors"]
            row["n_claims_requested"] = size["n_claims"]
            rows.append(row)
        print(f"  {size}: greedy runtime={outcome['greedy_eval']['runtime_seconds']:.4f}s cost={outcome['greedy_eval']['total_cost']:.3f}  "
              f"aco runtime={outcome['aco_eval']['runtime_seconds']:.4f}s cost={outcome['aco_eval']['total_cost']:.3f}")
    return pd.DataFrame(rows)


def section_convergence_and_visualization(representative_scenario, representative_aco_result) -> list[str]:
    print()
    print("=" * 100)
    print("PARTS 11-12: CONVERGENCE + ASSIGNMENT VISUALIZATION (representative scenario, seed=101)")
    print("=" * 100)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    convergence_path = ARTIFACT_DIR / "aco_convergence.png"
    plot_convergence(representative_aco_result.convergence_history, convergence_path, title="ACO Convergence - Surveyor Assignment (seed=101)")
    print(f"  saved {convergence_path}")

    assignment_path = ARTIFACT_DIR / "aco_assignment_visualization.png"
    plot_assignment(representative_scenario, representative_aco_result, assignment_path, title="ACO Assignment - Synthetic Research Scenario")
    print(f"  saved {assignment_path}")
    return [str(convergence_path), str(assignment_path)]


def section_comparison_table(five_scenario_df: pd.DataFrame) -> pd.DataFrame:
    print()
    print("=" * 100)
    print("PART 16: BASELINE vs ACO COMPARISON (mean across the 5 evaluation scenarios)")
    print("=" * 100)
    metrics = [
        ("total_cost", "Total Cost"), ("total_distance_raw", "Total Distance"),
        ("workload_imbalance_std", "Workload Imbalance (std)"), ("max_load_ratio", "Max Workload Ratio"),
        ("priority_handling_score", "Priority Handling Score (lower=better)"),
        ("runtime_seconds", "Runtime (s)"), ("n_unassigned", "Unassigned Claims"),
    ]
    rows = []
    for key, label in metrics:
        baseline_mean = five_scenario_df[five_scenario_df["strategy"] == "greedy"][key].mean()
        aco_mean = five_scenario_df[five_scenario_df["strategy"] == "aco"][key].mean()
        diff = aco_mean - baseline_mean
        if key == "runtime_seconds":
            interpretation = "ACO is slower (expected - it evaluates many candidate solutions)." if diff > 0 else "ACO is faster."
        else:
            interpretation = "ACO lower (better)" if diff < 0 else ("ACO higher (worse)" if diff > 0 else "No difference")
        rows.append({"Metric": label, "Baseline (greedy)": baseline_mean, "ACO": aco_mean, "Difference (ACO-Baseline)": diff, "Interpretation": interpretation})
        print(f"  {label:38s} baseline={baseline_mean:10.4f}  aco={aco_mean:10.4f}  diff={diff:+10.4f}  {interpretation}")
    return pd.DataFrame(rows)


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    five_scenario_df = section_five_scenarios()
    five_scenario_df.to_csv(ARTIFACT_DIR / "scenario_results.csv", index=False)

    stress_df = section_stress_test()
    stress_df.to_csv(ARTIFACT_DIR / "scalability_results.csv", index=False)

    representative = run_one_scenario(seed=REPRESENTATIVE_SEED, use_real_ids=True, **MAIN_SCENARIO_SIZE)
    figure_paths = section_convergence_and_visualization(representative["scenario"], representative["aco"])

    comparison_df = section_comparison_table(five_scenario_df)
    comparison_df.to_csv(ARTIFACT_DIR / "aco_results.csv", index=False)

    with open(ARTIFACT_DIR / "aco_parameters.json", "w") as f:
        json.dump({
            "aco_parameters": DEFAULT_ACO_PARAMETERS.__dict__,
            "cost_weights": DEFAULT_WEIGHTS.__dict__,
            "note": "Research prototype parameters - not claimed to be globally optimal, not tuned on the evaluation scenarios (see docstrings in aco_optimizer.py / cost_function.py).",
            "evaluation_seeds": EVALUATION_SEEDS,
            "main_scenario_size": MAIN_SCENARIO_SIZE,
            "stress_test_sizes": STRESS_TEST_SIZES,
        }, f, indent=2)

    best_assignments = [
        {"claim_id": a.claim_id, "surveyor_id": a.surveyor_id, "reason": a.reason,
         "cost": None if a.cost is None else a.cost.__dict__}
        for a in representative["aco"].assignments
    ]
    with open(ARTIFACT_DIR / "aco_best_assignments.json", "w") as f:
        json.dump({"seed": REPRESENTATIVE_SEED, "strategy": "aco", "assignments": best_assignments}, f, indent=2, default=str)

    print()
    print("=" * 100)
    print("SUMMARY")
    print("=" * 100)
    baseline_mean_cost = five_scenario_df[five_scenario_df["strategy"] == "greedy"]["total_cost"].mean()
    aco_mean_cost = five_scenario_df[five_scenario_df["strategy"] == "aco"]["total_cost"].mean()
    if aco_mean_cost < baseline_mean_cost:
        print(f"ACO produced a lower mean objective cost ({aco_mean_cost:.4f}) than the greedy baseline ({baseline_mean_cost:.4f}) "
              f"across the {len(EVALUATION_SEEDS)} evaluated synthetic scenarios.")
    elif aco_mean_cost > baseline_mean_cost:
        print(f"ACO produced a HIGHER mean objective cost ({aco_mean_cost:.4f}) than the greedy baseline ({baseline_mean_cost:.4f}) "
              f"across the {len(EVALUATION_SEEDS)} evaluated synthetic scenarios - the baseline was not outperformed here.")
    else:
        print("ACO and the greedy baseline produced statistically indistinguishable mean objective cost.")
    print("This is a synthetic-scenario research prototype - see docs/project_documentation/ACO_SURVEYOR_ASSIGNMENT.md")
    print(f"Artifacts saved under {ARTIFACT_DIR}")


if __name__ == "__main__":
    main()
