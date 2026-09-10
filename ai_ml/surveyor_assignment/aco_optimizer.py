"""Classical Ant Colony Optimization (Ant System, Dorigo 1996 style) for
the claim-to-surveyor assignment problem (Step 5.6, Part 4).

Each ant constructs one complete assignment by visiting claims in a
fixed order (highest priority first, matching baseline_assignment.py for
a fair comparison) and probabilistically choosing a surveyor for each,
using:

    P(claim=i -> surveyor=j) = [tau(i,j)^alpha * eta(i,j)^beta]
                                / sum_k feasible [tau(i,k)^alpha * eta(i,k)^beta]

`eta` (heuristic desirability) is 1/cost and is recomputed at each
construction step because workload - and therefore feasibility and
workload_cost - changes as the ant assigns claims. Distance and priority
cost components are static per (claim, surveyor) pair and are
precomputed once with numpy for performance (Part 10's larger
scalability sizes would otherwise be slow in pure Python).

Only surveyors that are AVAILABLE in the scenario and have remaining
capacity at that point in the ant's construction are ever candidates -
capacity/availability are hard constraints (Part 6), never something the
probabilistic step can violate.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from ai_ml.surveyor_assignment.baseline_assignment import priority_sorted_claims
from ai_ml.surveyor_assignment.cost_function import (
    CAPACITY_VIOLATION_PENALTY,
    DEFAULT_WEIGHTS,
    UNASSIGNED_CLAIM_PENALTY,
    CostWeights,
    assignment_cost,
    euclidean_distance,
)
from ai_ml.surveyor_assignment.data_model import PRIORITY_WEIGHT, Assignment, AssignmentResult, AssignmentScenario

MIN_PHEROMONE = 1e-6
EPSILON = 1e-9


@dataclass(frozen=True)
class ACOParameters:
    """Research prototype parameters (Part 4) - chosen once via a small
    pilot run on seed=999 (NOT one of the 5 evaluation seeds 101/202/
    303/404/505, and NOT one of the stress-test scenarios), then frozen
    and reused unchanged for every experiment in this step. They are not
    claimed to be globally optimal for this or any other problem
    instance."""

    n_ants: int = 15
    n_iterations: int = 60
    alpha: float = 1.0  # pheromone importance
    beta: float = 2.0  # heuristic (1/cost) importance
    evaporation_rate: float = 0.3
    pheromone_deposit_q: float = 1.0
    initial_pheromone: float = 1.0
    random_seed: int = 42


DEFAULT_ACO_PARAMETERS = ACOParameters()


def _priority_weight_vector(claims: list) -> np.ndarray:
    return np.array([PRIORITY_WEIGHT[c.priority] for c in claims], dtype=float)


def ant_colony_optimize(
    scenario: AssignmentScenario,
    weights: CostWeights = DEFAULT_WEIGHTS,
    params: ACOParameters = DEFAULT_ACO_PARAMETERS,
) -> AssignmentResult:
    start = time.perf_counter()
    rng = np.random.RandomState(params.random_seed)

    claims = priority_sorted_claims(scenario)
    surveyors = scenario.surveyors
    n_claims, n_surveyors = len(claims), len(surveyors)

    max_workload = np.array([s.maximum_workload for s in surveyors], dtype=float)
    start_workload = np.array([s.current_workload for s in surveyors], dtype=float)
    available_mask = np.array([s.availability for s in surveyors], dtype=bool)

    from ai_ml.surveyor_assignment.cost_function import MAX_POSSIBLE_DISTANCE

    # Static components (do not depend on workload) - precomputed once.
    dist_matrix = np.zeros((n_claims, n_surveyors))
    for i, claim in enumerate(claims):
        for j, surveyor in enumerate(surveyors):
            dist_matrix[i, j] = euclidean_distance(claim.location_x, claim.location_y, surveyor.location_x, surveyor.location_y)
    distance_cost_matrix = dist_matrix / MAX_POSSIBLE_DISTANCE
    priority_cost_matrix = _priority_weight_vector(claims)[:, None] * distance_cost_matrix

    pheromone = np.full((n_claims, n_surveyors), params.initial_pheromone)
    pheromone[:, ~available_mask] = 0.0  # never-available surveyors get no pheromone at all

    best_cost = float("inf")
    best_assignment_indices: list[int | None] = [None] * n_claims  # claim i -> surveyor index or None
    convergence_history: list[float] = []

    for _iteration in range(params.n_iterations):
        iteration_solutions = []  # (solution_cost, assignment_indices, pairs_used)

        for _ant in range(params.n_ants):
            workload = start_workload.copy()
            assignment_indices: list[int | None] = [None] * n_claims
            pairs_used: list[tuple[int, int]] = []
            unassigned_count = 0
            assigned_cost_sum = 0.0

            for i in range(n_claims):
                feasible = available_mask & (workload < max_workload)
                feasible_js = np.nonzero(feasible)[0]
                if feasible_js.size == 0:
                    unassigned_count += 1
                    continue

                workload_cost = (workload[feasible_js] + 1.0) / max_workload[feasible_js]
                total_cost = (
                    weights.distance_weight * distance_cost_matrix[i, feasible_js]
                    + weights.workload_weight * workload_cost
                    + weights.priority_weight * priority_cost_matrix[i, feasible_js]
                )
                eta = 1.0 / (total_cost + EPSILON)
                tau = np.maximum(pheromone[i, feasible_js], MIN_PHEROMONE)
                desirability = (tau ** params.alpha) * (eta ** params.beta)
                probabilities = desirability / desirability.sum()

                chosen_j = rng.choice(feasible_js, p=probabilities)
                assignment_indices[i] = int(chosen_j)
                pairs_used.append((i, int(chosen_j)))
                assigned_cost_sum += float(total_cost[feasible_js == chosen_j][0])
                workload[chosen_j] += 1

            solution_cost = assigned_cost_sum + UNASSIGNED_CLAIM_PENALTY * unassigned_count
            iteration_solutions.append((solution_cost, assignment_indices, pairs_used))

        iteration_best_cost, iteration_best_indices, _ = min(iteration_solutions, key=lambda item: item[0])
        if iteration_best_cost < best_cost:
            best_cost = iteration_best_cost
            best_assignment_indices = iteration_best_indices
        convergence_history.append(best_cost)

        # Evaporation.
        pheromone *= (1.0 - params.evaporation_rate)
        pheromone[:, ~available_mask] = 0.0
        np.clip(pheromone, MIN_PHEROMONE, None, out=pheromone)
        pheromone[:, ~available_mask] = 0.0

        # Deposit - classical Ant System: every ant reinforces the edges
        # it used, proportional to 1/(its own total solution cost).
        for solution_cost, _indices, pairs_used in iteration_solutions:
            if solution_cost <= 0:
                continue
            deposit = params.pheromone_deposit_q / solution_cost
            for i, j in pairs_used:
                pheromone[i, j] += deposit

    # Materialize the best-so-far solution as a full AssignmentResult,
    # re-deriving each CostBreakdown from the canonical cost_function
    # (using the FINAL workload state built up by that solution, in
    # claim-processing order) so downstream reporting/validation uses
    # exactly the same cost logic as the baselines.
    convergence_iteration = next((i for i, v in enumerate(convergence_history) if v == best_cost), len(convergence_history) - 1)

    workload_state = {s.surveyor_id: s.current_workload for s in surveyors}
    assignments: list[Assignment] = []
    for i, claim in enumerate(claims):
        j = best_assignment_indices[i]
        if j is None:
            assignments.append(Assignment(claim.claim_id, None, None, reason="No available surveyor with remaining capacity."))
            continue
        surveyor = surveyors[j]
        from ai_ml.surveyor_assignment.data_model import Surveyor as _Surveyor

        surveyor_snapshot = _Surveyor(
            surveyor_id=surveyor.surveyor_id, location_x=surveyor.location_x, location_y=surveyor.location_y,
            current_workload=workload_state[surveyor.surveyor_id], maximum_workload=surveyor.maximum_workload,
            availability=surveyor.availability, is_real_id=surveyor.is_real_id,
        )
        cost = assignment_cost(claim, surveyor_snapshot, weights)
        workload_state[surveyor.surveyor_id] += 1
        assignments.append(Assignment(claim.claim_id, surveyor.surveyor_id, cost))

    runtime = time.perf_counter() - start
    return AssignmentResult(
        strategy="aco",
        assignments=assignments,
        runtime_seconds=runtime,
        final_workloads=workload_state,
        convergence_history=convergence_history,
        extra={
            "parameters": params.__dict__,
            "best_cost": best_cost,
            "convergence_iteration": convergence_iteration,
        },
    )
