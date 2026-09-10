"""Builds reproducible `AssignmentScenario`s for the Step 5.6 ACO
experiment.

REAL vs SYNTHETIC - read before changing anything here:

  REAL (from ai_ml.common.data_loader, unmodified):
    - Claim_ID, sampled from the actual `claims` table
    - Surveyor_ID, the 20 distinct surveyors that actually appear in
      `surveyor_inspections`

  SYNTHETIC (generated here, from a fixed seed, documented per-field):
    - location_x / location_y for both claims and surveyors - abstract
      grid coordinates in [0, GRID_SIZE], NOT latitude/longitude and NOT
      associated with any real address or accident location
    - Claim.priority - drawn High/Medium/Low with fixed weights
    - Claim.required_service_level - drawn Standard/Express
    - Surveyor.current_workload / maximum_workload / availability

These attributes are synthetic because the current dataset does not
contain operational surveyor-location and availability information (see
docs/project_documentation/ACO_SURVEYOR_ASSIGNMENT.md, Section 5).
"""

from __future__ import annotations

import numpy as np

from ai_ml.common.data_loader import load_table
from ai_ml.surveyor_assignment.data_model import (
    AssignmentScenario,
    Claim,
    Priority,
    ServiceLevel,
    Surveyor,
)

GRID_SIZE = 100.0  # abstract units - not kilometers, not any real distance unit

PRIORITY_DISTRIBUTION = {Priority.HIGH: 0.20, Priority.MEDIUM: 0.50, Priority.LOW: 0.30}
SERVICE_LEVEL_DISTRIBUTION = {ServiceLevel.STANDARD: 0.75, ServiceLevel.EXPRESS: 0.25}
AVAILABILITY_PROBABILITY = 0.85  # fraction of surveyors marked available in a given scenario
WORKLOAD_MAX_RANGE = (5, 9)  # inclusive - assumed max concurrent open claims per surveyor
WORKLOAD_CURRENT_FRACTION_RANGE = (0.0, 0.7)  # starting load as a fraction of that surveyor's max


def real_claim_id_pool() -> list[str]:
    """All real Claim_ID values from the actual `claims` table - used
    only as anonymized experiment identifiers, never combined with any
    other real claim attribute in this module."""
    return load_table("claims")["Claim_ID"].tolist()


def real_surveyor_id_pool() -> list[str]:
    """The 20 real Surveyor_ID values that actually appear in
    `surveyor_inspections` - used only as identifiers."""
    return sorted(load_table("surveyor_inspections")["Surveyor_ID"].dropna().unique().tolist())


def _make_claim_ids(n: int, use_real_ids: bool, rng: np.random.RandomState) -> tuple[list[str], bool]:
    if use_real_ids:
        pool = real_claim_id_pool()
        if n > len(pool):
            raise ValueError(f"Requested {n} claims but only {len(pool)} real Claim_IDs exist.")
        chosen = rng.choice(pool, size=n, replace=False)
        return list(chosen), True
    return [f"SYNTH-CLAIM-{i:04d}" for i in range(n)], False


def _make_surveyor_ids(n: int, use_real_ids: bool, rng: np.random.RandomState) -> tuple[list[str], list[bool]]:
    if use_real_ids:
        pool = real_surveyor_id_pool()
        if n <= len(pool):
            chosen = list(rng.choice(pool, size=n, replace=False))
            return chosen, [True] * n
        # Scalability sizes (Part 10) can exceed the 20 real surveyors on
        # record. Reuse all 20 real IDs, then extend with clearly
        # synthetic IDs - never silently pad with fabricated "real" IDs.
        extra = [f"SYNTH-SURV-{i:03d}" for i in range(n - len(pool))]
        return list(pool) + extra, [True] * len(pool) + [False] * len(extra)
    return [f"SYNTH-SURV-{i:03d}" for i in range(n)], [False] * n


def generate_scenario(n_claims: int, n_surveyors: int, seed: int, use_real_ids: bool = True) -> AssignmentScenario:
    """Builds one reproducible scenario. Same (n_claims, n_surveyors,
    seed, use_real_ids) always produces an identical scenario (verified
    by ai_ml/tests/test_aco_assignment.py)."""
    rng = np.random.RandomState(seed)

    claim_ids, claims_are_real = _make_claim_ids(n_claims, use_real_ids, rng)
    surveyor_ids, surveyor_real_flags = _make_surveyor_ids(n_surveyors, use_real_ids, rng)

    priority_options = list(PRIORITY_DISTRIBUTION.keys())
    priority_probs = list(PRIORITY_DISTRIBUTION.values())
    service_level_options = list(SERVICE_LEVEL_DISTRIBUTION.keys())
    service_level_probs = list(SERVICE_LEVEL_DISTRIBUTION.values())

    claims = []
    for claim_id in claim_ids:
        # rng.choice() on a list of (str, Enum) members would coerce them
        # through numpy's string-array inference and corrupt the values
        # (observed: truncated to a fixed-width numpy string) - choosing
        # an index and indexing the plain Python list avoids that.
        priority = priority_options[rng.choice(len(priority_options), p=priority_probs)]
        service_level = service_level_options[rng.choice(len(service_level_options), p=service_level_probs)]
        claims.append(Claim(
            claim_id=str(claim_id),
            location_x=float(rng.uniform(0, GRID_SIZE)),
            location_y=float(rng.uniform(0, GRID_SIZE)),
            priority=priority,
            required_service_level=service_level,
            is_real_id=claims_are_real,
        ))

    surveyors = []
    for surveyor_id, is_real in zip(surveyor_ids, surveyor_real_flags):
        max_workload = int(rng.randint(WORKLOAD_MAX_RANGE[0], WORKLOAD_MAX_RANGE[1] + 1))
        current_fraction = rng.uniform(*WORKLOAD_CURRENT_FRACTION_RANGE)
        current_workload = int(round(current_fraction * max_workload))
        current_workload = min(current_workload, max_workload)
        available = bool(rng.uniform() < AVAILABILITY_PROBABILITY)
        surveyors.append(Surveyor(
            surveyor_id=str(surveyor_id),
            location_x=float(rng.uniform(0, GRID_SIZE)),
            location_y=float(rng.uniform(0, GRID_SIZE)),
            current_workload=current_workload,
            maximum_workload=max_workload,
            availability=available,
            is_real_id=is_real,
        ))

    metadata = {
        "seed": seed,
        "n_claims": n_claims,
        "n_surveyors": n_surveyors,
        "use_real_ids": use_real_ids,
        "real_fields": ["claim_id" if claims_are_real else None, "surveyor_id (partially, up to 20)" if use_real_ids else None],
        "synthetic_fields": [
            "location_x", "location_y", "priority", "required_service_level",
            "current_workload", "maximum_workload", "availability",
        ],
        "grid_size": GRID_SIZE,
        "disclaimer": (
            "These attributes are synthetic because the current dataset does not contain operational "
            "surveyor-location and availability information. location_x/location_y are abstract grid "
            "units, not latitude/longitude, and are not associated with any real address."
        ),
    }

    return AssignmentScenario(claims=claims, surveyors=surveyors, seed=seed, metadata=metadata)
