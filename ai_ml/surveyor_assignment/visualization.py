"""Research figures for the Step 5.6 ACO experiment (Parts 11/12). Plain
matplotlib, Agg backend, no styling beyond what is needed for the plot
to be readable. Every figure is explicitly captioned as a synthetic
research scenario - never implied to be a real map or real geography.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ai_ml.surveyor_assignment.data_model import AssignmentResult, AssignmentScenario


def plot_convergence(convergence_history: list[float], save_path: Path, title: str = "ACO Convergence") -> None:
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(range(1, len(convergence_history) + 1), convergence_history, marker="o", markersize=3, color="darkorange")
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Best Objective Cost (so far)")
    ax.set_title(f"{title}\n(Research-prototype parameters - see aco_parameters.json)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(save_path, dpi=150)
    plt.close(fig)


def plot_assignment(scenario: AssignmentScenario, result: AssignmentResult, save_path: Path, title: str = "Surveyor Assignment") -> None:
    fig, ax = plt.subplots(figsize=(7, 7))

    claim_by_id = scenario.claim_by_id()
    surveyor_by_id = scenario.surveyor_by_id()

    for a in result.assignments:
        if a.is_unassigned:
            continue
        claim, surveyor = claim_by_id[a.claim_id], surveyor_by_id[a.surveyor_id]
        ax.plot([claim.location_x, surveyor.location_x], [claim.location_y, surveyor.location_y], color="lightgray", linewidth=0.7, zorder=1)

    claim_x = [c.location_x for c in scenario.claims]
    claim_y = [c.location_y for c in scenario.claims]
    ax.scatter(claim_x, claim_y, c="steelblue", s=25, label="Claims (synthetic location)", zorder=2)

    available_surveyors = [s for s in scenario.surveyors if s.availability]
    unavailable_surveyors = [s for s in scenario.surveyors if not s.availability]
    if available_surveyors:
        ax.scatter([s.location_x for s in available_surveyors], [s.location_y for s in available_surveyors], c="darkorange", marker="^", s=80, label="Available surveyor (synthetic location)", zorder=3)
    if unavailable_surveyors:
        ax.scatter([s.location_x for s in unavailable_surveyors], [s.location_y for s in unavailable_surveyors], c="gray", marker="^", s=80, label="Unavailable surveyor (synthetic location)", zorder=3)

    unassigned = [a for a in result.assignments if a.is_unassigned]
    if unassigned:
        unassigned_x = [claim_by_id[a.claim_id].location_x for a in unassigned]
        unassigned_y = [claim_by_id[a.claim_id].location_y for a in unassigned]
        ax.scatter(unassigned_x, unassigned_y, c="red", marker="x", s=60, label="Unassigned claim", zorder=4)

    ax.set_xlabel("Synthetic grid X (abstract unit - NOT a real coordinate)")
    ax.set_ylabel("Synthetic grid Y (abstract unit - NOT a real coordinate)")
    ax.set_title(f"{title}\nSYNTHETIC RESEARCH SCENARIO (seed={scenario.seed}) - not real geographic coordinates")
    ax.legend(loc="upper right", fontsize=8)
    ax.set_aspect("equal")
    fig.tight_layout()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
