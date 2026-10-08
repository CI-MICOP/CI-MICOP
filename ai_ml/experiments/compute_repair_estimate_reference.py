"""Step 5.8.22: reference ranges for the repair estimate checks
(roadmap item 10, second part).

Prints the median and 90th percentile of three quantities across the
approved 654-claim reference dataset. The values are copied by hand into
backend/app/services/repair_estimate_checks.py, the same way
REPAIR_RATIO_P50 / REPAIR_RATIO_P90 were copied into ai_pipeline.py. Run
from the repo root:

    python -m ai_ml.experiments.compute_repair_estimate_reference

It also prints how each pair of columns relates in the dataset (see
docs/project_documentation/REPAIR_ESTIMATE_CHECKS.md, Section 6). The
dataset is synthetic: these ranges describe what is common in it, not what
is right or wrong in real insurer claims.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ai_ml.common.data_loader import load_table


def reference_quantities() -> dict[str, pd.Series]:
    estimates = load_table("repair_estimates")
    damage = load_table("vehicle_damage")
    damage_cost = damage.groupby("Claim_ID")["Estimated_Damage_Cost"].sum().replace(0, np.nan).rename("damage_cost")
    merged = estimates.merge(damage_cost, on="Claim_ID", how="left")
    return {
        "cost_ratio (Repair_Cost / Repair_Estimate)": estimates["Repair_Cost"] / estimates["Repair_Estimate"].replace(0, np.nan),
        "damage_cost_ratio (Repair_Estimate / total Estimated_Damage_Cost)": merged["Repair_Estimate"] / merged["damage_cost"],
        "extra_repair_days (Actual_Repair_Days - Estimated_Repair_Days)": (
            estimates["Actual_Repair_Days"] - estimates["Estimated_Repair_Days"]
        ),
    }


def main() -> None:
    estimates = load_table("repair_estimates")
    damage = load_table("vehicle_damage")
    print(f"repair_estimates rows: {len(estimates)}, vehicle_damage rows: {len(damage)}")
    print(f"estimates per claim (max): {estimates.groupby('Claim_ID').size().max()}")

    for name, values in reference_quantities().items():
        p90 = values.quantile(0.90)
        print(f"\n{name}")
        print(f"  rows used: {int(values.notna().sum())}  min: {values.min():.4f}  max: {values.max():.4f}")
        print(f"  p50 = {float(values.quantile(0.50))!r}")
        print(f"  p90 = {float(p90)!r}")
        print(f"  share of reference rows above p90: {float((values > p90).mean()):.4f}")

    damage_cost = damage.groupby("Claim_ID")["Estimated_Damage_Cost"].sum().rename("damage_cost")
    merged = estimates.merge(damage_cost, on="Claim_ID", how="left")
    print("\nHow the two sides of each comparison relate in the dataset (Pearson correlation):")
    print(f"  Repair_Cost vs Repair_Estimate:               {merged['Repair_Cost'].corr(merged['Repair_Estimate']):.3f}")
    print(f"  Repair_Estimate vs Estimated_Damage_Cost:     {merged['Repair_Estimate'].corr(merged['damage_cost']):.3f}")
    print(f"  Actual_Repair_Days vs Estimated_Repair_Days:  {merged['Actual_Repair_Days'].corr(merged['Estimated_Repair_Days']):.3f}")


if __name__ == "__main__":
    main()
