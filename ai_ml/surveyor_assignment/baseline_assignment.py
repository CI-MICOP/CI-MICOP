"""Transparent, deterministic baseline strategies (Step 5.6, Part 3).

Both baselines process claims in a fixed order (highest priority first,
then claim_id, for a deterministic tie-break) and greedily commit one
claim at a time - no lookahead, no backtracking. `AssignmentScenario` is
never mutated; each run works on its own copy of surveyor workloads.
"""

from __future__ import annotations

import time

from ai_ml.surveyor_assignment.cost_function import DEFAULT_WEIGHTS, CostWeights, assignment_cost, is_feasible
from ai_ml.surveyor_assignment.data_model import (
    Assignment,
    AssignmentResult,
    AssignmentScenario,
    PRIORITY_WEIGHT,
    Surveyor,
)


def priority_sorted_claims(scenario: AssignmentScenario) -> list:
    return sorted(scenario.claims, key=lambda c: (-PRIORITY_WEIGHT[c.priority], c.claim_id))


def _working_workloads(scenario: AssignmentScenario) -> dict[str, int]:
    return {s.surveyor_id: s.current_workload for s in scenario.surveyors}


def _feasible_surveyor(surveyor: Surveyor, workload: int) -> Surveyor:
    """Returns a Surveyor snapshot reflecting the CURRENT working
    workload (not the scenario's original starting value), so
    feasibility/cost reflect claims already assigned earlier in this run."""
    return Surveyor(
        surveyor_id=surveyor.surveyor_id, location_x=surveyor.location_x, location_y=surveyor.location_y,
        current_workload=workload, maximum_workload=surveyor.maximum_workload,
        availability=surveyor.availability, is_real_id=surveyor.is_real_id,
    )


def greedy_nearest_available(scenario: AssignmentScenario, weights: CostWeights = DEFAULT_WEIGHTS) -> AssignmentResult:
    """Part 3's preferred baseline: for each claim, among available
    surveyors with remaining capacity, pick the lowest-cost one. Ties
    broken by surveyor_id for determinism."""
    start = time.perf_counter()
    workloads = _working_workloads(scenario)
    assignments: list[Assignment] = []

    for claim in priority_sorted_claims(scenario):
        candidates = [_feasible_surveyor(s, workloads[s.surveyor_id]) for s in scenario.surveyors]
        candidates = [s for s in candidates if is_feasible(s)]
        if not candidates:
            assignments.append(Assignment(claim.claim_id, None, None, reason="No available surveyor with remaining capacity."))
            continue

        scored = [(assignment_cost(claim, s, weights), s) for s in candidates]
        scored.sort(key=lambda pair: (pair[0].total, pair[1].surveyor_id))
        best_cost, best_surveyor = scored[0]

        workloads[best_surveyor.surveyor_id] += 1
        assignments.append(Assignment(claim.claim_id, best_surveyor.surveyor_id, best_cost))

    runtime = time.perf_counter() - start
    return AssignmentResult(strategy="greedy_nearest_available", assignments=assignments, runtime_seconds=runtime, final_workloads=workloads)


def least_loaded_assignment(scenario: AssignmentScenario, weights: CostWeights = DEFAULT_WEIGHTS) -> AssignmentResult:
    """Secondary, even simpler baseline (Part 3): ignores distance
    entirely and always picks the feasible surveyor with the lowest
    current load ratio. Useful as an additional reference point, not the
    primary Baseline-vs-ACO comparison (see run_aco_experiment.py)."""
    start = time.perf_counter()
    workloads = _working_workloads(scenario)
    assignments: list[Assignment] = []

    for claim in priority_sorted_claims(scenario):
        candidates = [_feasible_surveyor(s, workloads[s.surveyor_id]) for s in scenario.surveyors]
        candidates = [s for s in candidates if is_feasible(s)]
        if not candidates:
            assignments.append(Assignment(claim.claim_id, None, None, reason="No available surveyor with remaining capacity."))
            continue

        candidates.sort(key=lambda s: (s.current_workload / s.maximum_workload, s.surveyor_id))
        best_surveyor = candidates[0]
        cost = assignment_cost(claim, best_surveyor, weights)

        workloads[best_surveyor.surveyor_id] += 1
        assignments.append(Assignment(claim.claim_id, best_surveyor.surveyor_id, cost))

    runtime = time.perf_counter() - start
    return AssignmentResult(strategy="least_loaded", assignments=assignments, runtime_seconds=runtime, final_workloads=workloads)
