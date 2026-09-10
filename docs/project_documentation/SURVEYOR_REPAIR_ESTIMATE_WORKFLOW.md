# Surveyor Repair Estimate Capture

## 1. Purpose

Makes `RepairEstimate` genuinely persisted for the Surveyor portal. Before this task, `RepairEstimatePage.jsx` did not exist and the surveyor's `ClaimDetailsPage` explicitly said repair estimate data was "not available to the Surveyor role - it is only exposed through the Claims Officer processing API." That statement is now stale and has been replaced with a live link to the new page. A surveyor can record one or more repair estimates for a claim they are assigned to; nothing about the AI-adjacent fields on this table is calculated in this step.

## 2. Surveyor workflow

`POST /api/v1/surveyor/repair-estimates` (JSON body). The surveyor submits `Claim_ID` plus the garage/cost/count fields they actually observed or were quoted; the backend derives `Vehicle_ID` from the claim and generates `Estimate_ID`, then persists one `repair_estimates` row. `repair_estimates` is one-to-many with claims (unchanged, no unique constraint on `Claim_ID`) - the surveyor can call this endpoint repeatedly if, for example, a second garage provides a competing quote. No update/delete endpoint was added, matching this task's own "prefer CREATE + LIST first" instruction (same posture as Vehicle Damage/Evidence in Step 5.8.6).

## 3. Authorization

`require_surveyor_employee_id` (added in Step 5.8.5) - JWT required, `Surveyor` role only (not Customer, not Claims Officer, not Admin). `Employee_ID` is resolved exclusively from the token, never from the request body.

## 4. Claim assignment requirement (reused, not reinvented)

The endpoint calls the same assignment check as vehicle-damage and evidence creation: `get_claim_assigned_to_surveyor_or_403(db, claim_id, employee_id)` (added in Step 5.8.6, in `app/services/claim_access.py`), which wraps the existing `crud_claim.surveyor_is_assigned` (a `surveyor_inspections` row for (claim, surveyor) already establishes assignment - unchanged from Step 5.8.5). No new assignment table, column, or mechanism was created.

**This means the same limitation from Steps 5.8.5/5.8.6 applies here unchanged: a brand-new customer-created claim has no surveyor assigned to it yet, so a surveyor cannot record a repair estimate for it until an inspection has been established for that (claim, surveyor) pair by some other means.** This was re-verified live in this task's manual test - the seeded, already-assigned `DEV-CLM-001` was used deliberately.

## 5. Vehicle_ID derivation

`Vehicle_ID` is never accepted from the client. `create_repair_estimate_for_surveyor` (in `app/services/repair_estimate_creation.py`) reads it from the already-fetched, ownership-checked `Claim` row (`claim.Vehicle_ID`) and writes that value - any `Vehicle_ID`, `Surveyor_ID`, or `Customer_ID` the client includes in the request body are schema fields Pydantic doesn't even define, so they are silently ignored, not read. Verified by `test_supplied_vehicle_id_cannot_override_claim_vehicle_id` and `test_supplied_surveyor_id_is_ignored`.

## 6. Estimate creation

The endpoint: (1) authenticates the user via JWT, (2) requires the `Surveyor` role, (3) verifies the claim exists, (4) verifies the claim is assigned to the current surveyor, (5) retrieves `Vehicle_ID` from the claim, (6) generates `Estimate_ID` server-side, (7) creates the `RepairEstimate` row, (8) commits to PostgreSQL, (9) returns the created estimate - exactly the 9-step flow this task specified. `Estimate_ID` follows the same convention as `Document_ID`/`Inspection_ID`/`Damage_ID`/`Evidence_ID`: `EST-YYYYMMDD-XXXXXX`, generated server-side (`crud/repair_estimate.py::generate_estimate_id`) and checked against the primary key before use.

## 7. Validation

Inspected before writing any code - the real values pulled directly from `ai_ml/datasets/CI_MICOP_15_Tables_Complete/09_repair_estimates.xlsx` (654 rows):

| Finding | Detail |
|---|---|
| `Garage_ID` format | Always `GAR-XXXX` in the dataset, but there is no Garage table in the approved design and no fixed vocabulary a surveyor could be constrained to (any real-world garage could be entered) - so it is validated only as required, trimmed, non-blank, max length 30 (matching the column), never against a closed enum. |
| `Actual_Repair_Days` | Every one of the 654 real rows has a nonzero value (min 3, max 20) - the dataset never uses 0 for a completed repair. This makes `0` a safe, unambiguous "not yet available" sentinel: it cannot be confused with a real repair that took zero days. |
| Cost-consistency | See Section 8 below - the dataset proves no fixed relationship exists between `Repair_Cost` and its components, so no rule was invented. |

`Garage_ID` required, trimmed, max length 30. All five monetary fields (`Repair_Estimate`, `Repair_Cost`, `Parts_Cost`, `Labour_Cost`, `Painting_Cost`) are `Decimal`, validated `>= 0` (never `float`). All four count/day fields (`Replacement_Parts_Count`, `Repaired_Parts_Count`, `Estimated_Repair_Days`, `Actual_Repair_Days`) are `int`, validated `>= 0`. `Actual_Repair_Days` is the only optional input field - see Section 9.

## 8. Financial fields / cost-consistency finding

All five monetary columns use `Numeric(14, 2)` in the database and `Decimal` in the API - never `FLOAT`, matching every other monetary field in this project.

This task asked for a "basic deterministic validation" checking whether `Repair_Cost` approximately corresponds to `Parts_Cost + Labour_Cost + Painting_Cost`, but only if the dataset supports such a rule. It does not: computing this difference across all 654 real rows shows **every single row differs** from an exact match, by amounts ranging from a few rupees up to roughly ₹63,000 in either direction, with no consistent tolerance band. Enforcing any tolerance here would therefore be an arbitrary, invented business rule contradicted by the project's own approved data - not a deterministic validation grounded in the dataset, and explicitly against this task's "do not invent an arbitrary business rule without checking the dataset" instruction. **No cost-consistency check was implemented, and none is claimed.**

## 9. Storage / database behavior

No file storage is involved - `RepairEstimate` has no evidence/document component, only numeric and identifier fields committed directly to PostgreSQL. `Estimate_Date` uses `Decimal`/`Date` types throughout (no floats). The full create flow is a single `commit()` + `refresh()`; there is no multi-step transaction/rollback concern the way file uploads have (see Step 5.8.6's Evidence upload for that pattern).

## 10. Multiple estimates

Confirmed via `test_multiple_estimates_can_coexist_for_same_claim` and the manual HTTP test (`DEV-CLM-001`'s count went from 1 seeded estimate to 2 after the manual POST, then back to 1 after cleanup): `Claim_ID` has no unique constraint on `repair_estimates`, so a claim may have several estimate rows - for example, quotes from two different garages. The frontend lists every estimate returned for the claim.

## 11. AI analysis pending state

Per this task's explicit "DO NOT IMPLEMENT AI YET" instruction, no anomaly detection, claim-leakage detection, XGBoost/SHAP scoring, historical estimate comparison, or expected-cost prediction was implemented. `Excessive_Claim_Amount_Indicator` is stored as `False` ("not flagged", never "AI-verified normal") and `Estimate_Anomaly_Score` is stored as `Decimal("0.0000")` (a placeholder, never a real model score - `0.0000` also appears as a genuine value twice in the 654-row real dataset, so this mirrors the exact same convention already established for `Evidence.Image_Quality`/`Evidence_Confidence_Score` in Step 5.8.6). The frontend never presents these as completed analysis: both the estimate-creation form and every estimate card show a clearly separated "Automated Analysis" section reading "AI repair-estimate analysis: Pending" / "AI analysis pending - this estimate has not been analyzed yet," and explicitly does **not** render a numeric "Anomaly Score" field anywhere in the UI.

## 12. Excessive_Claim_Amount_Indicator limitation

This column is not computed by comparing `Repair_Estimate` to the claim's `Claim_Amount`, and the UI does not auto-label an estimate as excessive merely because `Repair_Estimate > Claim_Amount` - there can be legitimate reasons for that relationship (e.g. partial claims, excess/deductible amounts, prior part replacements). The real, meaningful value for this field is a future AI/rule-based analysis output; until that pipeline exists, it is always `False` here.

## 13. Estimate_Anomaly_Score limitation

Likewise not computed from any statistical or ML process in this step. It is a `Decimal("0.0000")` placeholder awaiting the future leakage/anomaly-detection pipeline described in Section 14. The UI never surfaces this raw value to avoid it being mistaken for a genuine low-anomaly finding.

## 14. Future Smart Repair Estimate & Claim Leakage Detection integration

The pending fields in Sections 11-13 are exactly where a future AI/ML step would write real results, per this project's documented pipeline:

```
Repair Estimate
      |
Leakage / Anomaly Detection
      |
AI Risk Fusion
      |
Claims Officer
```

**Repair-estimate anomaly detection is not executed during estimate capture. The stored AI-adjacent fields remain pending until the AI/ML pipeline is connected.** A future background job or Claims Officer-triggered analysis would read a claim's repair estimate(s), run cost/anomaly modeling, and update `Excessive_Claim_Amount_Indicator` and `Estimate_Anomaly_Score` on the existing row(s) - no schema change needed.

## Limitations

- New customer-created claims still require a separate Surveyor assignment mechanism before a Surveyor can work on them (unchanged from Steps 5.8.5/5.8.6).
- No update or delete endpoint for `RepairEstimate` - only creation and listing (via the existing claim-detail endpoint) were implemented, per this task's explicit preference.
- No cost-consistency validation between `Repair_Cost` and its components - the approved dataset itself proves no such relationship holds (Section 8).
- No AI/ML anomaly detection, fraud analysis, or claim-leakage detection - all explicitly out of scope for this task.
- No Garage table - `Garage_ID` remains a plain identifier by the approved design.

## Confirmation

No schema changes were made (`alembic upgrade head` reports no pending migrations); no new tables were created; no AI/ML capability was implemented or falsely presented as already having analyzed a repair estimate.
