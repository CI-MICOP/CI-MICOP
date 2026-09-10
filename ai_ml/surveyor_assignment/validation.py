"""Integrity checks for surveyor-assignment results (Step 5.6, Part 14).
Every check raises `AssertionError` on failure - the same "fail loudly"
convention used throughout ai_ml (Step 5.2/5.3/5.4).
"""

from __future__ import annotations

import math

from ai_ml.surveyor_assignment.data_model import AssignmentResult, AssignmentScenario


def assert_one_surveyor_per_claim(scenario: AssignmentScenario, result: AssignmentResult) -> None:
    claim_ids_seen = [a.claim_id for a in result.assignments]
    if len(claim_ids_seen) != len(set(claim_ids_seen)):
        raise AssertionError(f"[{result.strategy}] a claim appears more than once in the assignment output.")
    expected = {c.claim_id for c in scenario.claims}
    if set(claim_ids_seen) != expected:
        missing = expected - set(claim_ids_seen)
        raise AssertionError(f"[{result.strategy}] {len(missing)} claim(s) silently missing from the assignment output: {sorted(missing)[:5]}")


def assert_no_unavailable_surveyor_assignment(scenario: AssignmentScenario, result: AssignmentResult) -> None:
    surveyors = scenario.surveyor_by_id()
    for a in result.assignments:
        if a.is_unassigned:
            continue
        surveyor = surveyors.get(a.surveyor_id)
        if surveyor is None:
            raise AssertionError(f"[{result.strategy}] claim {a.claim_id} assigned to unknown surveyor_id {a.surveyor_id}.")
        if not surveyor.availability:
            raise AssertionError(f"[{result.strategy}] claim {a.claim_id} assigned to unavailable surveyor {a.surveyor_id}.")


def assert_no_capacity_violation(scenario: AssignmentScenario, result: AssignmentResult) -> None:
    surveyors = scenario.surveyor_by_id()
    for surveyor_id, final_load in result.final_workloads.items():
        surveyor = surveyors[surveyor_id]
        if final_load > surveyor.maximum_workload:
            raise AssertionError(
                f"[{result.strategy}] surveyor {surveyor_id} final workload {final_load} exceeds capacity {surveyor.maximum_workload}."
            )


def assert_valid_ids(scenario: AssignmentScenario, result: AssignmentResult) -> None:
    claim_ids = {c.claim_id for c in scenario.claims}
    surveyor_ids = {s.surveyor_id for s in scenario.surveyors}
    for a in result.assignments:
        if a.claim_id not in claim_ids:
            raise AssertionError(f"[{result.strategy}] assignment references unknown claim_id {a.claim_id}.")
        if a.surveyor_id is not None and a.surveyor_id not in surveyor_ids:
            raise AssertionError(f"[{result.strategy}] assignment references unknown surveyor_id {a.surveyor_id}.")


def assert_no_nan_and_no_negative_costs(result: AssignmentResult) -> None:
    for a in result.assignments:
        if a.cost is None:
            continue
        for name, value in (("distance_cost", a.cost.distance_cost), ("workload_cost", a.cost.workload_cost), ("priority_cost", a.cost.priority_cost), ("total", a.cost.total)):
            if math.isnan(value) or math.isinf(value):
                raise AssertionError(f"[{result.strategy}] claim {a.claim_id} has invalid {name}={value}.")
            if value < 0:
                raise AssertionError(f"[{result.strategy}] claim {a.claim_id} has negative {name}={value}.")


def assert_cost_components_sum_correctly(result: AssignmentResult, weights) -> None:
    for a in result.assignments:
        if a.cost is None:
            continue
        expected = (
            weights.distance_weight * a.cost.distance_cost
            + weights.workload_weight * a.cost.workload_cost
            + weights.priority_weight * a.cost.priority_cost
        )
        if not math.isclose(expected, a.cost.total, rel_tol=1e-6, abs_tol=1e-9):
            raise AssertionError(f"[{result.strategy}] claim {a.claim_id} cost components do not sum to total: {expected} != {a.cost.total}")


def assert_scenarios_match(scenario_a: AssignmentScenario, scenario_b: AssignmentScenario) -> None:
    """Confirms the baseline and ACO were evaluated on the identical
    scenario (same claim/surveyor sets and attributes), so a comparison
    between them is meaningful."""
    if {c.claim_id for c in scenario_a.claims} != {c.claim_id for c in scenario_b.claims}:
        raise AssertionError("Baseline and ACO scenarios have different claim sets - not comparable.")
    if {s.surveyor_id for s in scenario_a.surveyors} != {s.surveyor_id for s in scenario_b.surveyors}:
        raise AssertionError("Baseline and ACO scenarios have different surveyor sets - not comparable.")
    if scenario_a.seed != scenario_b.seed:
        raise AssertionError(f"Baseline and ACO scenarios were generated from different seeds ({scenario_a.seed} vs {scenario_b.seed}).")


def validate_result(scenario: AssignmentScenario, result: AssignmentResult, weights) -> None:
    """Runs every check above - use this in the experiment script and
    tests rather than calling each check individually."""
    assert_one_surveyor_per_claim(scenario, result)
    assert_no_unavailable_surveyor_assignment(scenario, result)
    assert_no_capacity_violation(scenario, result)
    assert_valid_ids(scenario, result)
    assert_no_nan_and_no_negative_costs(result)
    assert_cost_components_sum_correctly(result, weights)
