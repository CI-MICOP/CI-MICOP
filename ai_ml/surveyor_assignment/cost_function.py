"""Transparent, 4-component assignment objective (Step 5.6, Part 5).

    total_cost = distance_cost + workload_imbalance_cost + priority_penalty + capacity_penalty

Every component is normalized to roughly [0, 1] before weighting so that
none dominates purely because of scale (distance is in abstract grid
units up to GRID_SIZE*sqrt(2); workload is a 0..1 load ratio; priority is
a 0..1 weight). `CostWeights` are configurable and were chosen once, by
simple reasoning, BEFORE any of the 5 evaluation scenarios were
generated - they are never tuned against evaluation results (see
ai_ml/experiments/run_aco_experiment.py and
docs/project_documentation/ACO_SURVEYOR_ASSIGNMENT.md, Section 11).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ai_ml.surveyor_assignment.data_model import PRIORITY_WEIGHT, Claim, CostBreakdown, Surveyor
from ai_ml.surveyor_assignment.synthetic_scenario import GRID_SIZE

MAX_POSSIBLE_DISTANCE = GRID_SIZE * math.sqrt(2)  # the grid's diagonal - a fixed, scenario-independent normalizer

# Applied only defensively (see aco_optimizer.py / baseline_assignment.py,
# which never let an infeasible surveyor reach this function in the first
# place - Part 6 treats capacity/availability as hard constraints, not a
# soft penalty to optimize around). Kept here, documented, so any future
# caller that DOES pass an infeasible pair gets an unmistakable signal
# rather than a quietly wrong low cost.
CAPACITY_VIOLATION_PENALTY = 1000.0

# The cost assigned to a claim that could not be assigned to anyone
# feasible - large enough that ACO / any future strategy is always
# incentivized to find a feasible assignment over leaving a claim
# unassigned, but distinguishable from an actual capacity violation.
UNASSIGNED_CLAIM_PENALTY = 5.0


@dataclass(frozen=True)
class CostWeights:
    """Research-prototype configurable weights - NOT learned, NOT tuned
    on the final evaluation scenarios. distance is weighted highest
    because it is the most direct, real-world-motivated driver of
    assignment quality; workload second (keeps the workforce balanced);
    priority third (a tie-breaking/quality nudge, not a hard rule)."""

    distance_weight: float = 0.5
    workload_weight: float = 0.3
    priority_weight: float = 0.2


DEFAULT_WEIGHTS = CostWeights()


def euclidean_distance(a_x: float, a_y: float, b_x: float, b_y: float) -> float:
    return math.hypot(a_x - b_x, a_y - b_y)


def is_feasible(surveyor: Surveyor) -> bool:
    """Hard constraint check (Part 6) - availability and remaining
    capacity. Does not depend on the claim being assigned."""
    return surveyor.availability and surveyor.current_workload < surveyor.maximum_workload


def assignment_cost(claim: Claim, surveyor: Surveyor, weights: CostWeights = DEFAULT_WEIGHTS) -> CostBreakdown:
    """Cost of assigning `claim` to `surveyor`, given `surveyor`'s
    CURRENT (pre-assignment) workload. Callers must only invoke this for
    a feasible pair (`is_feasible(surveyor)` True) - see module docstring."""
    if not is_feasible(surveyor):
        return CostBreakdown(0.0, 0.0, 0.0, CAPACITY_VIOLATION_PENALTY)

    distance = euclidean_distance(claim.location_x, claim.location_y, surveyor.location_x, surveyor.location_y)
    distance_cost = distance / MAX_POSSIBLE_DISTANCE

    projected_workload = surveyor.current_workload + 1
    workload_cost = projected_workload / surveyor.maximum_workload  # in (0, 1] given feasibility above

    priority_cost = PRIORITY_WEIGHT[claim.priority] * distance_cost

    total = (
        weights.distance_weight * distance_cost
        + weights.workload_weight * workload_cost
        + weights.priority_weight * priority_cost
    )
    return CostBreakdown(distance_cost=distance_cost, workload_cost=workload_cost, priority_cost=priority_cost, total=total)
