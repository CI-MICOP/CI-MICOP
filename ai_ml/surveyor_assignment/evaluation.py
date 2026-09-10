"""Evaluation metrics for one AssignmentResult against its scenario
(Step 5.6, Part 8).
"""

from __future__ import annotations

import numpy as np

from ai_ml.surveyor_assignment.data_model import AssignmentResult, AssignmentScenario, Priority


def evaluate_result(scenario: AssignmentScenario, result: AssignmentResult) -> dict:
    surveyors_by_id = scenario.surveyor_by_id()
    claims_by_id = scenario.claim_by_id()

    assigned = [a for a in result.assignments if not a.is_unassigned]
    unassigned = [a for a in result.assignments if a.is_unassigned]

    total_distance = sum(a.cost.distance_cost for a in assigned)  # normalized units; see distance_raw below
    distances_raw = []
    for a in assigned:
        claim, surveyor = claims_by_id[a.claim_id], surveyors_by_id[a.surveyor_id]
        from ai_ml.surveyor_assignment.cost_function import euclidean_distance

        distances_raw.append(euclidean_distance(claim.location_x, claim.location_y, surveyor.location_x, surveyor.location_y))

    total_cost = sum(a.cost.total for a in assigned)
    from ai_ml.surveyor_assignment.cost_function import UNASSIGNED_CLAIM_PENALTY

    total_cost_with_penalty = total_cost + UNASSIGNED_CLAIM_PENALTY * len(unassigned)

    load_ratios = [
        result.final_workloads[s.surveyor_id] / s.maximum_workload for s in scenario.surveyors
    ]
    overloaded = [
        s for s in scenario.surveyors if result.final_workloads[s.surveyor_id] > s.maximum_workload
    ]

    high_priority_claim_ids = {c.claim_id for c in scenario.claims if c.priority == Priority.HIGH}
    high_priority_assigned = [a for a in assigned if a.claim_id in high_priority_claim_ids]
    priority_handling_score = (
        float(np.mean([a.cost.distance_cost for a in high_priority_assigned]))
        if high_priority_assigned else None
    )

    return {
        "strategy": result.strategy,
        "n_claims": len(scenario.claims),
        "n_surveyors": len(scenario.surveyors),
        "n_assigned": len(assigned),
        "n_unassigned": len(unassigned),
        "unassigned_claim_ids": [a.claim_id for a in unassigned],
        "total_cost": total_cost,
        "total_cost_with_unassigned_penalty": total_cost_with_penalty,
        "total_distance_raw": float(sum(distances_raw)),
        "average_distance_per_claim": float(np.mean(distances_raw)) if distances_raw else None,
        "workload_imbalance_std": float(np.std(load_ratios)),
        "max_surveyor_workload": int(max(result.final_workloads.values())) if result.final_workloads else 0,
        "max_load_ratio": float(max(load_ratios)) if load_ratios else None,
        "n_overloaded_assignments": len(overloaded),
        "priority_handling_score": priority_handling_score,
        "runtime_seconds": result.runtime_seconds,
        "convergence_iteration": result.extra.get("convergence_iteration") if result.extra else None,
    }
