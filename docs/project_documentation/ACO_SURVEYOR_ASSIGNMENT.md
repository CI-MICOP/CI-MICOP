# Ant Colony Optimization for Surveyor Assignment (Step 5.6)

**This is a research-prototype algorithm comparison on a synthetic optimization scaffold. It is not connected to the live CI-MICOP application, does not use real surveyor operational data, and does not claim ACO is universally better, production-ready, or validated on real-world data.**

---

## 1. Motivation

Steps 5.1-5.5 built and honestly validated CI-MICOP's claim-analysis AI/ML layer (fraud/risk signals, multi-signal fusion, explainability) as decision support for the Claims Officer. Step 5.6 asks a different, complementary operational question: once a claim needs a physical inspection, **which surveyor should be assigned to it?** This is a classic combinatorial assignment/optimization problem, distinct from the predictive-modeling work in Steps 5.1-5.5, and is evaluated here as a self-contained research experiment.

## 2. The surveyor assignment problem

Given a set of claims (each needing an inspection) and a set of surveyors (each with a location, a current workload, a maximum capacity, and an availability status), assign each claim to at most one surveyor such that: every surveyor's capacity is respected, only available surveyors receive claims, and the total assignment quality (distance, workload balance, priority handling) is as good as possible. This is an NP-hard generalized assignment problem in general - exhaustive search is not tractable at realistic scale, which motivates comparing a fast heuristic (greedy) against a metaheuristic (ACO).

## 3. Why optimization is useful

A purely manual or first-come-first-served assignment process ignores surveyor workload balance and claim urgency. An automated *recommendation* (never an automatic decision - see Section 12/Part 20 of the implementation) could help a claims operations team see a considered, explainable option before making the actual assignment.

## 4. Why ACO was selected

Ant Colony Optimization was chosen because (a) it naturally handles combinatorial assignment problems with multiple competing objectives via a single scalar cost, (b) its pheromone/heuristic mechanism is more transparent and inspectable than a black-box learned policy, matching CI-MICOP's existing explainability-first approach (Steps 5.2-5.4), and (c) it is a well-established, classical technique (Ant System, Dorigo 1996) - **this step does not claim ACO itself is novel** (see Section 21).

## 5. Dataset limitation

The CI-MICOP dataset contains 654 claims and 531 surveyor inspection records referencing **20 distinct real surveyors** (`surveyor_inspections.Surveyor_ID`). It does **not** contain:
- surveyor home/base coordinates
- claim incident coordinates suitable for routing
- actual road distance or travel time
- surveyor specialization
- real-time availability
- real-time workload
- live location

**Real data used (unmodified, read-only):**
- `Claim_ID` - sampled from the actual `claims` table
- `Surveyor_ID` - the 20 real surveyor identifiers from `surveyor_inspections`

**Synthetic data introduced only for this experiment** (`ai_ml/surveyor_assignment/synthetic_scenario.py`):
- `location_x`, `location_y` for both claims and surveyors - abstract grid coordinates in `[0, 100]`, **not** latitude/longitude, **not** associated with any real address or accident location
- `Claim.priority` (High/Medium/Low, weighted 20%/50%/30%) - no legitimate pre-inspection priority field exists in the real schema (the closest real field, `Damage_Severity`, is only known *after* a surveyor has already inspected the claim)
- `Claim.required_service_level` (Standard/Express) - recorded for realism; not used by the cost function
- `Surveyor.current_workload`, `maximum_workload`, `availability`

These attributes are synthetic because the current dataset does not contain operational surveyor-location and availability information. Every scenario's `metadata` dict states this explicitly and lists exactly which fields are real vs. synthetic.

## 6. Synthetic scenario design

`generate_scenario(n_claims, n_surveyors, seed, use_real_ids)` is fully deterministic: the same arguments always produce an identical scenario (`numpy.random.RandomState(seed)`), verified in `ai_ml/tests/test_aco_assignment.py`. For the main 5-scenario evaluation and the representative visualization, real Claim_ID/Surveyor_ID values are sampled (`use_real_ids=True`); the scalability stress test (Section 15) uses fully synthetic identifiers throughout, since real-ID authenticity is irrelevant to measuring runtime scaling and the stress sizes exceed the 20 real surveyors on record.

## 7. Baseline algorithm

`ai_ml/surveyor_assignment/baseline_assignment.py` implements two transparent, deterministic baselines, both processing claims highest-priority-first (ties broken by `claim_id`):

1. **Greedy nearest available surveyor** (primary baseline): for each claim, among surveyors that are available and under capacity, pick the one with the lowest total assignment cost. This is the baseline used throughout the Baseline-vs-ACO comparison.
2. **Least-loaded** (secondary reference): ignores distance entirely, always picking the feasible surveyor with the lowest current load ratio - included only for additional context (Section 13).

## 8. ACO algorithm

`ai_ml/surveyor_assignment/aco_optimizer.py` implements a classical Ant System. Each of `n_ants` ants constructs one complete assignment per iteration by visiting claims in the same fixed priority order as the baseline and, for each claim, choosing a surveyor probabilistically from the feasible candidates:

```
P(claim=i -> surveyor=j) = [tau(i,j)^alpha * eta(i,j)^beta] / sum_k feasible [tau(i,k)^alpha * eta(i,k)^beta]
```

`eta` (heuristic desirability) is `1 / cost` and is recomputed at every construction step because workload - and therefore both feasibility and the workload-cost component - changes as an ant assigns claims one by one. Only surveyors that are available **and** have remaining capacity at that point in the ant's own construction are ever candidates; this is a hard constraint, never a soft penalty an ant can choose to violate.

## 9. Pheromone mechanism

- Pheromone matrix `tau[claim, surveyor]`, initialized to `1.0` for every (claim, surveyor) pair where the surveyor is available in the scenario (zero otherwise).
- **Evaporation** each iteration: `tau *= (1 - evaporation_rate)`, floored at `1e-6` for numerical stability.
- **Deposit**: classical Ant System - every ant reinforces every (claim, surveyor) pair it used, by `pheromone_deposit_q / (that ant's own total solution cost)`, so lower-cost solutions reinforce their paths more strongly.
- Best-so-far solution and its cost are tracked across iterations for the convergence plot (Section 18).

## 10. Heuristic function

`eta(claim, surveyor) = 1 / (total_assignment_cost + epsilon)`, using the SAME `assignment_cost` function the baseline uses (Section 11) - the heuristic and the objective are the same cost model, not two different ones, so ACO and the baseline are optimizing an identical, comparable quantity.

## 11. Objective function

`ai_ml/surveyor_assignment/cost_function.py`:

```
total_cost = distance_weight * distance_cost
           + workload_weight * workload_cost
           + priority_weight * priority_cost
```

- `distance_cost = euclidean_distance(claim, surveyor) / (GRID_SIZE * sqrt(2))` - normalized to `[0, 1]` by the grid's diagonal.
- `workload_cost = (surveyor.current_workload + 1) / surveyor.maximum_workload` - the *projected* load ratio if this assignment is made; always in `(0, 1]` for a feasible surveyor.
- `priority_cost = priority_weight(claim.priority) * distance_cost`, where `priority_weight` is `1.0`/`0.5`/`0.0` for High/Medium/Low - a high-priority claim placed far from its surveyor is penalized more than a low-priority claim in the same position.
- **Capacity violations** are enforced as a hard constraint (surveyors are filtered out, not penalized) - `CAPACITY_VIOLATION_PENALTY` exists in code only as a defensive fallback that should never actually trigger (verified by `ai_ml/surveyor_assignment/validation.py`).
- An **unassigned claim** contributes a fixed `UNASSIGNED_CLAIM_PENALTY = 5.0` to a solution's total cost, so both algorithms are incentivized to find a feasible assignment whenever one exists.

`CostWeights(distance_weight=0.5, workload_weight=0.3, priority_weight=0.2)` are configurable, research-prototype defaults chosen once by reasoning (distance is the most direct real-world driver of assignment quality; workload balance second; priority a tie-breaking nudge third) - **not tuned against the evaluation scenarios**.

## 12. Constraints

Enforced identically by both the baseline and ACO (Part 6): one surveyor per claim; only available surveyors are ever candidates; a surveyor's workload never exceeds its maximum capacity; every claim receives an assignment if any feasible surveyor exists at that point. When no feasible surveyor exists, the claim is returned as `UNASSIGNED` with an explicit reason string - never silently dropped or given an infeasible surveyor. All of this is checked programmatically after every run by `ai_ml/surveyor_assignment/validation.py` (`validate_result`), and by dedicated tests.

## 13. Experimental setup

`ai_ml/experiments/run_aco_experiment.py`, run once end-to-end (`python -m ai_ml.experiments.run_aco_experiment`):

- **Research-prototype ACO parameters** (frozen before evaluation, chosen via a small pilot on seed `999` - not one of the evaluation/stress seeds): `n_ants=15`, `n_iterations=60`, `alpha=1.0`, `beta=2.0`, `evaporation_rate=0.3`, `pheromone_deposit_q=1.0`, `initial_pheromone=1.0`, `random_seed=42`.
- Main scenario size: 50 claims / 20 surveyors, real Claim_ID/Surveyor_ID.
- Every result is validated (`validate_result`) before being reported.

## 14. Five-scenario evaluation

Seeds 101/202/303/404/505, 50 claims / 20 surveyors, real IDs. Mean/std/min/max across the 5 scenarios:

| Metric | Greedy (baseline) | ACO |
|---|---:|---:|
| Total cost | mean 13.299, std 1.041, min 12.249, max 14.994 | mean 13.307, std 1.179, min 12.179, max 15.227 |
| Total distance (raw) | mean 935.97, std 82.13 | mean 953.23, std 76.92 |
| Workload imbalance (std of load ratios) | mean 0.2064, std 0.0329 | mean 0.2010, std 0.0377 |
| Max load ratio | 1.0000 (all seeds) | 1.0000 (all seeds) |
| Unassigned claims | 0 (all seeds) | 0 (all seeds) |
| Runtime (s) | mean 0.011, std 0.002 | mean 11.505, std 0.183 |

(Full per-seed rows: `ai_ml/model_artifacts/aco/scenario_results.csv`, including the `least_loaded` secondary baseline, which was consistently worse on distance across all 5 seeds - e.g. seed 101: total distance 2570.2 vs. greedy's 913.7 - confirming the cost function rewards distance-aware assignment as intended.)

## 15. Scalability experiment

Three sizes, fully synthetic identifiers, seed 42, same frozen ACO parameters:

| Size (surveyors/claims) | Greedy runtime | ACO runtime | Greedy total cost | ACO total cost | Unassigned |
|---|---:|---:|---:|---:|---:|
| 20 / 50 | 0.009 s | 12.27 s | 12.900 | 12.986 | 0 (both) |
| 30 / 100 | 0.036 s | 23.90 s | 30.384 | 30.297 | 0 (both) |
| 40 / 150 | 0.051 s | 34.58 s | 42.624 | 43.278 | **1 (both)** |

At the largest tested size, both algorithms left the same claim (`SYNTH-CLAIM-0142`) unassigned - a genuine feasibility limit of that scenario (not enough available/under-capacity surveyors), correctly and identically detected by both algorithms rather than one silently forcing an infeasible assignment. Greedy's runtime stays under 0.06s at every tested size; ACO's runtime grows roughly linearly with claim count (~12s to ~35s) at these fixed ant/iteration counts. **These are small research-prototype problem sizes and do not demonstrate production scalability.**

## 16. Results

Across every evaluated scenario, ACO and the greedy baseline produce **very similar total cost** - within roughly 1-2% of each other in every one of the 5 main scenarios - with no consistent winner: ACO was lower-cost in 3 of 5 seeds (202, 404, 505) and higher-cost in 2 of 5 (101, 303). ACO consistently used several orders of magnitude more runtime.

## 17. Baseline vs. ACO comparison

Mean across the 5 evaluation scenarios (`ai_ml/model_artifacts/aco/aco_results.csv`):

| Metric | Baseline | ACO | Difference | Interpretation |
|---|---:|---:|---:|---|
| Total Cost | 13.2991 | 13.3070 | +0.0079 | ACO higher (worse) |
| Total Distance | 935.97 | 953.23 | +17.26 | ACO higher (worse) |
| Workload Imbalance (std) | 0.2064 | 0.2010 | -0.0054 | ACO lower (better) |
| Max Workload Ratio | 1.0000 | 1.0000 | 0.0000 | No difference |
| Priority Handling Score (lower=better) | 0.1299 | 0.1296 | -0.0002 | ACO lower (better) |
| Runtime (s) | 0.0111 | 11.5046 | +11.4934 | ACO is slower (expected - it evaluates many candidate solutions) |
| Unassigned Claims | 0 | 0 | 0 | No difference |

**Honest conclusion: ACO did not produce a meaningfully lower total assignment cost than the greedy baseline in these evaluated synthetic scenarios** (a +0.06% difference in mean total cost, well within the run-to-run standard deviation of both algorithms). ACO showed small, consistent improvements in workload balance and priority handling, and a small degradation in total distance, at a runtime cost roughly 1000x greater than the baseline. **This step does not claim ACO is better - it reports what was actually measured.**

## 18. Convergence

The representative run (seed 101, 50 claims / 20 surveyors) improved its best-so-far cost from 16.89 at iteration 1 to 13.52 by iteration 53, then held flat through iteration 60 (`ai_ml/model_artifacts/aco/aco_convergence.png`) - the algorithm visibly converges within the allotted 60 iterations for this problem size, rather than still improving when the run was stopped. Convergence iteration varied 45-54 across the 5 evaluation seeds.

## 19. Limitations

- All location, workload, priority, and availability data are synthetic; none of it reflects real surveyor geography, real caseloads, or real claim urgency.
- The ACO parameters were frozen from a single informal pilot, not a systematic hyperparameter search - a different parameter set could plausibly change the comparison's outcome in either direction.
- "Distance" is Euclidean on an abstract grid, not road distance or travel time.
- Priority is synthetic and does not reflect any real underwriting or claims-triage judgment.
- The 5-scenario and 3-size evaluations are small research-prototype experiments, not a statistically powered study.
- ACO's runtime, as implemented, is far higher than the greedy baseline's; no attempt was made to further optimize this beyond the numpy-vectorized cost precomputation already used.

## 20. Future real-data implementation

Genuine surveyor-assignment optimization would require, at minimum: surveyor home/base location, claim incident location, actual travel distance/time, surveyor specialization, real-time availability, real-time workload, service-level agreements, claim urgency, and regional/state operational constraints. Obtaining these would require insurer collaboration, proper data governance, privacy protection and de-identification, approvals where legally required, secure infrastructure, and ground-truth operational evaluation (e.g. comparing recommended vs. actually-assigned surveyors and measured outcomes) - none of which currently exists for CI-MICOP. This document does not claim any of this data is currently available.

## 21. Research contribution

This step does not claim Ant Colony Optimization itself is novel - it is a well-established classical metaheuristic. The potential contribution, consistent with Steps 5.1-5.5's explainability-first, human-in-the-loop approach, is framed as: **an integrated decision-support workflow combining claim intelligence (risk/priority information from Steps 5.1-5.5) with optimization-assisted surveyor assignment, kept fully transparent (inspectable cost function, pheromone mechanism, and hard constraints) and never autonomous.** No claim of "first" or "unique" is made, and none should be inferred without independent literature verification.
