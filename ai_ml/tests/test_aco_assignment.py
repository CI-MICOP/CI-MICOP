"""Tests for the Step 5.6 surveyor-assignment ACO experiment. Run with:
    pytest ai_ml/tests/test_aco_assignment.py -v
Uses small synthetic scenarios throughout (no dependency on live claims/
surveyors data beyond the real Claim_ID/Surveyor_ID pools already used
elsewhere in ai_ml).
"""

from __future__ import annotations

import math

import pytest

from ai_ml.surveyor_assignment.aco_optimizer import ACOParameters, ant_colony_optimize
from ai_ml.surveyor_assignment.baseline_assignment import greedy_nearest_available, least_loaded_assignment
from ai_ml.surveyor_assignment.cost_function import DEFAULT_WEIGHTS, assignment_cost, euclidean_distance, is_feasible
from ai_ml.surveyor_assignment.data_model import (
    Assignment,
    AssignmentResult,
    AssignmentScenario,
    Claim,
    Priority,
    ServiceLevel,
    Surveyor,
)
from ai_ml.surveyor_assignment.synthetic_scenario import generate_scenario
from ai_ml.surveyor_assignment.validation import (
    assert_cost_components_sum_correctly,
    assert_no_capacity_violation,
    assert_no_nan_and_no_negative_costs,
    assert_no_unavailable_surveyor_assignment,
    assert_one_surveyor_per_claim,
    assert_scenarios_match,
    assert_valid_ids,
    validate_result,
)

SMALL_ACO_PARAMS = ACOParameters(n_ants=5, n_iterations=8, random_seed=7)


# ---------------------------------------------------------------- 1. synthetic scenario reproducibility


def test_scenario_generation_is_reproducible():
    a = generate_scenario(n_claims=10, n_surveyors=5, seed=123, use_real_ids=False)
    b = generate_scenario(n_claims=10, n_surveyors=5, seed=123, use_real_ids=False)
    assert [c.claim_id for c in a.claims] == [c.claim_id for c in b.claims]
    assert [(c.location_x, c.location_y, c.priority) for c in a.claims] == [(c.location_x, c.location_y, c.priority) for c in b.claims]
    assert [(s.surveyor_id, s.current_workload, s.availability) for s in a.surveyors] == [(s.surveyor_id, s.current_workload, s.availability) for s in b.surveyors]


def test_different_seeds_produce_different_scenarios():
    a = generate_scenario(n_claims=10, n_surveyors=5, seed=1, use_real_ids=False)
    b = generate_scenario(n_claims=10, n_surveyors=5, seed=2, use_real_ids=False)
    assert [(c.location_x, c.location_y) for c in a.claims] != [(c.location_x, c.location_y) for c in b.claims]


def test_scenario_uses_real_ids_when_requested():
    scenario = generate_scenario(n_claims=15, n_surveyors=10, seed=101, use_real_ids=True)
    assert all(c.is_real_id for c in scenario.claims)
    assert all(c.claim_id.startswith("CLM-") for c in scenario.claims)


# ---------------------------------------------------------------- 2/3. baseline and ACO validity


@pytest.fixture(scope="module")
def small_scenario() -> AssignmentScenario:
    return generate_scenario(n_claims=12, n_surveyors=6, seed=101, use_real_ids=False)


def test_baseline_assignment_is_valid(small_scenario):
    result = greedy_nearest_available(small_scenario, DEFAULT_WEIGHTS)
    validate_result(small_scenario, result, DEFAULT_WEIGHTS)


def test_least_loaded_baseline_is_valid(small_scenario):
    result = least_loaded_assignment(small_scenario, DEFAULT_WEIGHTS)
    validate_result(small_scenario, result, DEFAULT_WEIGHTS)


def test_aco_assignment_is_valid(small_scenario):
    result = ant_colony_optimize(small_scenario, DEFAULT_WEIGHTS, SMALL_ACO_PARAMS)
    validate_result(small_scenario, result, DEFAULT_WEIGHTS)


# ---------------------------------------------------------------- 4/5/6. constraints


def test_capacity_constraint_never_violated(small_scenario):
    for result in [greedy_nearest_available(small_scenario, DEFAULT_WEIGHTS), ant_colony_optimize(small_scenario, DEFAULT_WEIGHTS, SMALL_ACO_PARAMS)]:
        assert_no_capacity_violation(small_scenario, result)


def test_unavailable_surveyor_never_assigned():
    # Built explicitly (rather than relying on a random scenario happening
    # to include an unavailable surveyor) so this test is deterministic
    # regardless of RNG luck.
    claims = [Claim(f"C{i}", location_x=float(i), location_y=float(i), priority=Priority.MEDIUM, required_service_level=ServiceLevel.STANDARD) for i in range(6)]
    surveyors = [
        Surveyor("S1", 0, 0, current_workload=0, maximum_workload=10, availability=False),
        Surveyor("S2", 1, 1, current_workload=0, maximum_workload=10, availability=True),
    ]
    scenario = AssignmentScenario(claims=claims, surveyors=surveyors, seed=1)

    for result in [greedy_nearest_available(scenario, DEFAULT_WEIGHTS), ant_colony_optimize(scenario, DEFAULT_WEIGHTS, SMALL_ACO_PARAMS)]:
        assert_no_unavailable_surveyor_assignment(scenario, result)
        assert all(a.surveyor_id == "S2" for a in result.assignments if not a.is_unassigned)


def test_one_surveyor_per_claim(small_scenario):
    result = greedy_nearest_available(small_scenario, DEFAULT_WEIGHTS)
    assert_one_surveyor_per_claim(small_scenario, result)
    surveyor_assignments = [a.surveyor_id for a in result.assignments if not a.is_unassigned]
    # a claim never receives more than one surveyor by construction (Assignment has a single surveyor_id) -
    # explicitly confirm the output shape enforces this (one field, not a list).
    assert all(isinstance(sid, str) for sid in surveyor_assignments)


# ---------------------------------------------------------------- 7. no feasible surveyor handling


def test_unassigned_when_no_feasible_surveyor_exists():
    claim = Claim(claim_id="C1", location_x=10, location_y=10, priority=Priority.HIGH, required_service_level=ServiceLevel.STANDARD)
    full_surveyor = Surveyor(surveyor_id="S1", location_x=0, location_y=0, current_workload=3, maximum_workload=3, availability=True)
    unavailable_surveyor = Surveyor(surveyor_id="S2", location_x=5, location_y=5, current_workload=0, maximum_workload=5, availability=False)
    scenario = AssignmentScenario(claims=[claim], surveyors=[full_surveyor, unavailable_surveyor], seed=1)

    result = greedy_nearest_available(scenario, DEFAULT_WEIGHTS)
    assert len(result.assignments) == 1
    assert result.assignments[0].is_unassigned
    assert result.assignments[0].reason is not None

    aco_result = ant_colony_optimize(scenario, DEFAULT_WEIGHTS, ACOParameters(n_ants=3, n_iterations=3, random_seed=1))
    assert aco_result.assignments[0].is_unassigned
    validate_result(scenario, result, DEFAULT_WEIGHTS)
    validate_result(scenario, aco_result, DEFAULT_WEIGHTS)


def test_is_feasible_checks_availability_and_capacity():
    available_with_room = Surveyor("S1", 0, 0, current_workload=1, maximum_workload=3, availability=True)
    at_capacity = Surveyor("S2", 0, 0, current_workload=3, maximum_workload=3, availability=True)
    unavailable = Surveyor("S3", 0, 0, current_workload=0, maximum_workload=3, availability=False)
    assert is_feasible(available_with_room)
    assert not is_feasible(at_capacity)
    assert not is_feasible(unavailable)


# ---------------------------------------------------------------- 8. cost calculation


def test_assignment_cost_components_and_total():
    claim = Claim(claim_id="C1", location_x=0, location_y=0, priority=Priority.HIGH, required_service_level=ServiceLevel.STANDARD)
    surveyor = Surveyor(surveyor_id="S1", location_x=3, location_y=4, current_workload=1, maximum_workload=4, availability=True)
    cost = assignment_cost(claim, surveyor, DEFAULT_WEIGHTS)

    expected_distance = euclidean_distance(0, 0, 3, 4)  # = 5.0
    assert expected_distance == pytest.approx(5.0)
    assert cost.distance_cost > 0
    assert cost.workload_cost == pytest.approx(2 / 4)  # (current_workload + 1) / max
    assert cost.priority_cost == pytest.approx(1.0 * cost.distance_cost)  # HIGH priority weight = 1.0
    expected_total = (
        DEFAULT_WEIGHTS.distance_weight * cost.distance_cost
        + DEFAULT_WEIGHTS.workload_weight * cost.workload_cost
        + DEFAULT_WEIGHTS.priority_weight * cost.priority_cost
    )
    assert cost.total == pytest.approx(expected_total)


def test_cost_components_sum_correctly_across_a_full_result(small_scenario):
    result = greedy_nearest_available(small_scenario, DEFAULT_WEIGHTS)
    assert_cost_components_sum_correctly(result, DEFAULT_WEIGHTS)


def test_no_nan_or_negative_costs(small_scenario):
    for result in [greedy_nearest_available(small_scenario, DEFAULT_WEIGHTS), ant_colony_optimize(small_scenario, DEFAULT_WEIGHTS, SMALL_ACO_PARAMS)]:
        assert_no_nan_and_no_negative_costs(result)


# ---------------------------------------------------------------- 9/13. pheromone update / convergence output


def test_convergence_history_is_non_increasing_and_correct_length(small_scenario):
    result = ant_colony_optimize(small_scenario, DEFAULT_WEIGHTS, SMALL_ACO_PARAMS)
    history = result.convergence_history
    assert len(history) == SMALL_ACO_PARAMS.n_iterations
    for earlier, later in zip(history, history[1:]):
        assert later <= earlier + 1e-9, "best-so-far cost must never get worse across iterations"
    assert not any(math.isnan(v) for v in history)


def test_more_iterations_do_not_worsen_the_best_solution(small_scenario):
    short_run = ant_colony_optimize(small_scenario, DEFAULT_WEIGHTS, ACOParameters(n_ants=5, n_iterations=2, random_seed=7))
    long_run = ant_colony_optimize(small_scenario, DEFAULT_WEIGHTS, ACOParameters(n_ants=5, n_iterations=20, random_seed=7))
    assert long_run.extra["best_cost"] <= short_run.extra["best_cost"] + 1e-9


# ---------------------------------------------------------------- 10. deterministic seed


def test_aco_is_deterministic_given_a_fixed_seed(small_scenario):
    result_1 = ant_colony_optimize(small_scenario, DEFAULT_WEIGHTS, SMALL_ACO_PARAMS)
    result_2 = ant_colony_optimize(small_scenario, DEFAULT_WEIGHTS, SMALL_ACO_PARAMS)
    assert result_1.convergence_history == result_2.convergence_history
    assert [(a.claim_id, a.surveyor_id) for a in result_1.assignments] == [(a.claim_id, a.surveyor_id) for a in result_2.assignments]


def test_aco_different_seeds_can_differ(small_scenario):
    result_1 = ant_colony_optimize(small_scenario, DEFAULT_WEIGHTS, ACOParameters(n_ants=5, n_iterations=8, random_seed=1))
    result_2 = ant_colony_optimize(small_scenario, DEFAULT_WEIGHTS, ACOParameters(n_ants=5, n_iterations=8, random_seed=2))
    # not asserting they MUST differ (small problems can coincidentally match) - just that both are valid
    validate_result(small_scenario, result_1, DEFAULT_WEIGHTS)
    validate_result(small_scenario, result_2, DEFAULT_WEIGHTS)


# ---------------------------------------------------------------- 11. result structure


def test_assignment_result_structure(small_scenario):
    result = ant_colony_optimize(small_scenario, DEFAULT_WEIGHTS, SMALL_ACO_PARAMS)
    assert isinstance(result, AssignmentResult)
    assert result.strategy == "aco"
    assert len(result.assignments) == len(small_scenario.claims)
    assert all(isinstance(a, Assignment) for a in result.assignments)
    assert set(result.final_workloads.keys()) == {s.surveyor_id for s in small_scenario.surveyors}
    assert "parameters" in result.extra and "best_cost" in result.extra


# ---------------------------------------------------------------- 14. scenario comparison


def test_scenario_comparison_passes_for_identical_seed():
    a = generate_scenario(n_claims=10, n_surveyors=5, seed=55, use_real_ids=False)
    b = generate_scenario(n_claims=10, n_surveyors=5, seed=55, use_real_ids=False)
    assert_scenarios_match(a, b)


def test_scenario_comparison_fails_for_different_seeds():
    a = generate_scenario(n_claims=10, n_surveyors=5, seed=55, use_real_ids=False)
    b = generate_scenario(n_claims=10, n_surveyors=5, seed=56, use_real_ids=False)
    with pytest.raises(AssertionError):
        assert_scenarios_match(a, b)


def test_assert_valid_ids_rejects_unknown_surveyor():
    claim = Claim(claim_id="C1", location_x=0, location_y=0, priority=Priority.LOW, required_service_level=ServiceLevel.STANDARD)
    surveyor = Surveyor(surveyor_id="S1", location_x=0, location_y=0, current_workload=0, maximum_workload=2, availability=True)
    scenario = AssignmentScenario(claims=[claim], surveyors=[surveyor], seed=1)
    bad_result = AssignmentResult(
        strategy="fake", assignments=[Assignment("C1", "S-UNKNOWN", None)], runtime_seconds=0.0, final_workloads={"S1": 0},
    )
    with pytest.raises(AssertionError):
        assert_valid_ids(scenario, bad_result)
