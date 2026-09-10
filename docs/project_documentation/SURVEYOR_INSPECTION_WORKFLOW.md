# Surveyor Inspection Workflow

Makes the Surveyor Inspection workflow real for claims a surveyor is actually assigned to, and honestly documents the one remaining gap: **a brand-new customer-created claim currently has no path to surveyor assignment.** This is explained in detail in Section 1.

## 1. The existing assignment mechanism (read this first)

The approved 15-table schema has **no dedicated assignment table or column**. Before this task, the project already established - and this task deliberately preserves - a single implicit rule, used consistently everywhere a surveyor's access is checked:

> **A `surveyor_inspections` row for (Claim_ID, Surveyor_ID) is what "this surveyor is assigned to this claim" means.**

This is visible in three places that already existed before this task:

- `app/crud/claim.py::surveyor_is_assigned(db, claim_id, employee_id)` - queries for a matching `surveyor_inspections` row.
- `app/services/claim_access.py::get_claim_or_403` - a Surveyor may read a claim only if `surveyor_is_assigned` is true.
- `app/crud/claim.py::list_by_surveyor` - `GET /claims` for a Surveyor joins through `surveyor_inspections` to find "their" claims.

**Consequence:** a claim with zero `surveyor_inspections` rows (which is exactly the state of every claim created through the new Customer Create Claim flow) is invisible to every surveyor - it doesn't appear in their claim list, `GET /surveyor/claims/{id}` 403s, and (per this task's new rule) `POST /surveyor/inspections` also 403s. There is currently **no action any role can take through the API to change this** - no "assign surveyor" endpoint exists anywhere in the project (checked: `app/api/v1/routers/officer.py` and every other router has no such endpoint).

This task does not invent a fix for that gap - see Section 9 (Limitations) and the explicit instruction that shaped this decision ("Do not solve assignment by creating a new table, randomly assigning a Surveyor, hardcoding a Surveyor, or integrating ACO prematurely").

## 2. What this task adds

`POST /api/v1/surveyor/inspections` - lets a surveyor start an inspection on a claim they are **already** assigned to (via the mechanism above), i.e. a claim where a `surveyor_inspections` row for them already exists (typically from a prior, now-completed inspection - a re-inspection scenario) or from data seeded outside this API. It reuses `surveyor_is_assigned` unchanged rather than defining a second, competing notion of "assigned."

## 3. Authentication / RBAC

- `require_surveyor_employee_id` (new, in `app/api/v1/deps.py`) - stricter than the existing `require_employee_id` (which also allows Claims Officer): only a `Surveyor`-role user may call `POST /surveyor/inspections`. `Surveyor_ID` is resolved exclusively from this - never from the request body.
- No token -> `401`. Customer or Claims Officer role -> `403`.
- `GET`/`PATCH` endpoints are unchanged - still `Surveyor` or `Admin`, exactly as before.

## 4. Inspection creation rules (`app/services/inspection_creation.py`)

1. Claim must exist -> else `404`.
2. `surveyor_is_assigned(claim_id, employee_id)` must be true -> else `403` ("You are not assigned to this claim"). This is what rejects both "another surveyor's claim" and "a claim nobody has ever inspected."
3. The surveyor must not already have an **active** inspection on this claim - "active" means `Survey_Report_Submitted == False`. If one exists -> `409 Conflict`. This is what allows a genuine re-inspection (a prior inspection was completed and submitted) while blocking a duplicate open one.
4. `Inspection_ID` is generated server-side (`INSP-YYYYMMDD-XXXXXX`, collision-checked against the primary key - same pattern as `Claim_ID`/`Document_ID` from earlier steps).

## 5. Initial values for a newly created inspection

Nothing has actually been inspected yet, so nothing is fabricated:

| Field | Value | Why |
|---|---|---|
| `Inspection_Date` | today | Real date the inspection was opened. |
| `Inspection_Location` | the claim's own `Place_of_Accident` | Real, already-known data - not invented, and a reasonable proxy for where the inspection will happen. |
| `Vehicle_Condition`, `Damage_Observed`, `Damage_Severity`, `Repair_Recommendation` | `"Pending"` | See Section 6 - a clearly-labeled sentinel, never one of the dataset's real conclusion values. |
| `Parts_Required` | `0` | Explicit initial value; `>= 0` is a legitimate value, not a placeholder. |
| `Surveyor_Comments` | `""` | Nothing recorded yet. |
| `Inspection_Status` | `"Assigned"` | A **real** value from the approved dataset (see Section 6) - the natural initial state, no sentinel needed. |
| `Survey_Report_Submitted` | `False` | No report has been submitted. |
| `Surveyor_Confidence_Score` | `0.0000` | Column is non-nullable; `0` is the honest "no assessment yet" value, not a real confidence figure. |

## 6. Vocabulary - inspected from the real dataset, not invented

Before adding any validation, the actual historical values were read from `ai_ml/datasets/CI_MICOP_15_Tables_Complete/11_surveyor_inspections.xlsx` (531 rows):

| Field | Real values found |
|---|---|
| `Vehicle_Condition` | Good, Fair, Poor |
| `Damage_Observed` | Yes, No |
| `Damage_Severity` | Minor, Moderate, Severe |
| `Repair_Recommendation` | Repair, Replace, Total Loss |
| `Inspection_Status` | Assigned, Scheduled, In Progress, Completed |

None of these include a neutral "not yet assessed" placeholder - every value is a genuine conclusion. Since the columns are non-nullable and the task explicitly forbids pretending an assessment happened, this project adds exactly one small, clearly-named sentinel, `"Pending"`, for the four judgment-call fields (not `Inspection_Status`, which already has the perfect real value `"Assigned"` for this purpose). This mirrors the project's own existing convention of a `"Pending"` sentinel for `Final_Decision`/`Settlement_Basis_Code` on claims (see `CUSTOMER_CLAIM_SUBMISSION.md`). `app/schemas/surveyor.py` is the single source of truth for both the real-value sets and the sentinel, and both the create and update schemas validate against it - **arbitrary strings are rejected with `422`.**

## 7. Update / Save vs. Submit

- **Save Inspection** (`PATCH /surveyor/inspections/{id}` without `Survey_Report_Submitted`) - unchanged mechanism, but now every field is validated against the vocabulary above (`Parts_Required >= 0`, `Surveyor_Comments` capped at 2000 characters). Saving never touches `Survey_Report_Submitted`.
- **Submit Survey Report** (`PATCH .../{id}` with `Survey_Report_Submitted: true`) - before this task, this always succeeded unconditionally. It now requires the *effective* post-update state (existing values merged with whatever this request also changes) to satisfy:
  - `Vehicle_Condition` is a real value (not `"Pending"`).
  - `Damage_Observed` is a real value.
  - If `Damage_Observed == "Yes"`, `Damage_Severity` must also be a real value.
  - `Repair_Recommendation` is a real value.

  If any of these are still `"Pending"`, the request is rejected with `400` and a message naming exactly which field(s) are missing - `Survey_Report_Submitted` is **not** set, and the row is left unchanged. If the checks pass, `Survey_Report_Submitted` is set `True` and `Inspection_Status` is force-set to `"Completed"` (the existing terminal status - report submission and inspection completion are the same real-world event in this data model).

## 8. Ownership on update (unchanged, verified)

The existing `PATCH` handler already rejected a surveyor updating another surveyor's inspection (`inspection.Surveyor_ID != current_user.Employee_ID -> 403`) before this task - this covers both "update another's inspection" and "submit another's report" with the same check, and is now covered by explicit tests.

## 9. Limitations

- **A brand-new customer-created claim cannot be inspected by any surveyor yet.** This is the direct, documented consequence of Section 1: there is no assignment action anywhere in the current system. Closing this gap requires either (a) a future Claims-Officer-driven "assign surveyor" step (explicitly out of scope for this task), or (b) the separate ACO research prototype (`ai_ml/surveyor_assignment/`) being wired into the live system as a production feature (also explicitly out of scope - it remains a standalone research module). Verified live in this task's manual test: attempting `POST /surveyor/inspections` for a freshly created claim returned `403 "You are not assigned to this claim"`, exactly as expected.
- No Vehicle Damage, Evidence, or Repair Estimate creation - untouched, per this task's scope.
- No AI, fraud, or consistency analysis of inspection findings.
- `Inspection_Location` is copied from the claim's accident location rather than being independently confirmed by the surveyor - the model has no separate "surveyor-confirmed location" field.
- Only one inspection may be *active* per (claim, surveyor) at a time; multiple *historical* (submitted) inspections are allowed, matching a realistic re-inspection workflow.

## 10. Relationship to future ACO assignment

`ai_ml/surveyor_assignment/` (from the earlier ACO research step) computes an *optimized* claim-to-surveyor mapping as a standalone, synthetic-data research prototype - it is not wired into the live database or API, and this task does not integrate it. If/when a real assignment mechanism is built, the natural integration point is whatever creates the *first* `surveyor_inspections` row for a claim (today, nothing does) - ACO's output could inform *which* surveyor that first row names, but the row itself would still need to be created through an explicit, human-in-the-loop action (e.g. a Claims Officer decision), not automatically by this task's endpoint.
