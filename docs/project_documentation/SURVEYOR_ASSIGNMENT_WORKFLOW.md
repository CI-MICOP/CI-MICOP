# Surveyor Assignment Workflow

## 1. Purpose

Closes the gap documented in `SURVEYOR_INSPECTION_WORKFLOW.md`: a brand-new, customer-created claim previously had no way to ever acquire its first `surveyor_inspections` row, because `services/inspection_creation.py` requires the surveyor to already be "assigned" before they can self-start an inspection. This step gives the Claims Officer/Admin role a way to create that first row - the assignment act itself - connecting Customer claim creation to the existing Surveyor workflow (Inspection, Vehicle Damage, Evidence, Repair Estimate, Survey Report) without changing any of it.

## 2. Current problem (before this step)

```
Customer -> Creates Claim -> Claim exists, Claim_Status = "Under Review"
                                       |
                                       v
                        No surveyor_inspections row exists
                                       |
                                       v
                 No Surveyor can ever pass surveyor_is_assigned()
                                       |
                                       v
                    Claim is permanently unreachable by any Surveyor
```

## 3. Assignment workflow (after this step)

```
Customer -> Creates Claim -> Claim exists without Surveyor
                                       |
                                       v
                     Claims Officer opens the claim, "Surveyor Assignment" card
                                       |
                                       v
                GET /api/v1/officer/surveyors -> eligible active Surveyors
                                       |
                                       v
             POST /api/v1/officer/claims/{claim_id}/assign-surveyor
                                       |
                                       v
        A surveyor_inspections row is created: Inspection_Status = "Assigned"
                                       |
                                       v
        Surveyor sees the claim in GET /claims and GET /surveyor/claims/{id}
                                       |
                                       v
        Existing, unmodified Inspection / Vehicle Damage / Evidence /
        Repair Estimate / Survey Report workflows become available
```

No new table, column, or assignment mechanism was created. Assignment **is** the creation of a `surveyor_inspections` row - exactly the definition of "assigned" already established in Steps 5.8.5-5.8.7 (`crud_claim.surveyor_is_assigned`, reused unchanged by `get_claim_or_403`, `get_claim_assigned_to_surveyor_or_403`, and `crud_claim.list_by_surveyor`).

## 4. Officer responsibilities

The Claims Officer (or Admin) opens a claim, sees whether it is assigned, selects an eligible active Surveyor from a real list, and confirms. The officer never supplies a `Surveyor_ID`/`Claim_ID` combination that bypasses server-side validation - the endpoint independently verifies the claim exists, the selected account exists, is role `Surveyor`, and is `Active` before creating anything.

## 5. Surveyor responsibilities

Unchanged. Once assigned, the surveyor's existing `GET /claims`, `GET /surveyor/claims/{claim_id}`, inspection, vehicle-damage, evidence, and repair-estimate endpoints work exactly as before - all of them already derive "is this surveyor allowed to touch this claim" from the same `surveyor_inspections` row this step creates. No surveyor-side code was changed.

## 6. API endpoints

### `GET /api/v1/officer/surveyors`

Claims Officer/Admin only. Returns active Surveyor accounts:

```json
[
  { "Employee_ID": "DEV-SURV-001", "Username": "dev_surveyor", "Email": "dev.surveyor@ci-micop.local", "Account_Status": "Active" }
]
```

`AuthenticationUser` has no `Name` field (unlike `Customer.Customer_Name`), so `Username` is used as the display identifier rather than fabricating one. No workload, location, availability, rating, specialization, or distance is included - none of those fields exist in the approved schema, and the task explicitly forbids fabricating them. `Password_Hash` and every other authentication-only field are excluded.

### `POST /api/v1/officer/claims/{claim_id}/assign-surveyor`

Claims Officer/Admin only. Request body:

```json
{ "surveyor_employee_id": "DEV-SURV-001" }
```

`surveyor_employee_id` (not a generic `surveyor_id`) was chosen because the project consistently identifies staff by `Employee_ID` everywhere else (`require_surveyor_employee_id`, `SurveyorInspection.Surveyor_ID` -> `authentication_users.Employee_ID`). `Claim_ID` always comes from the URL path, never the body. Returns the created `SurveyorInspectionOut` row (201).

## 7. RBAC

Both endpoints use the project's existing `require_roles("Claims Officer", "Admin")` dependency (already used by every other endpoint in `officer.py`) - no custom authorization logic was written in either route. Customer and Surveyor both receive 403 from both endpoints. No existing authorization was weakened.

## 8. Database representation

The assignment is a single `surveyor_inspections` row, built with the identical honest "not yet assessed" sentinel values already established in `services/inspection_creation.py`:

| Field | Value | Why |
|---|---|---|
| `Vehicle_Condition`, `Damage_Observed`, `Damage_Severity`, `Repair_Recommendation` | `"Pending"` | The project's existing sentinel for "not yet assessed" (schemas/surveyor.py's `PENDING`) - never a fabricated finding. |
| `Parts_Required` | `0` | Nothing has been assessed yet. |
| `Surveyor_Comments` | `""` | Nothing has been written yet. |
| `Inspection_Status` | `"Assigned"` | A real value from the approved dataset - means "surveyor assigned; inspection not yet completed." |
| `Survey_Report_Submitted` | `False` | Not submitted. |
| `Surveyor_Confidence_Score` | `0.0000` | No assessment has occurred. |
| `Inspection_Location` | `claim.Place_of_Accident` | Real, already-known data copied from the claim - not fabricated. |
| `Surveyor_ID` | The looked-up, validated surveyor's `Employee_ID` | Never a raw, unvalidated client string. |

No columns were added. No new table was created.

## 9. Duplicate assignment behavior

If the claim already has a `surveyor_inspections` row with `Survey_Report_Submitted == False` (an active, not-yet-completed assignment), a new assignment request - to the same surveyor or a different one - is rejected with **409 Conflict**, naming the existing `Surveyor_ID` and `Inspection_ID`.

## 10. Reassignment behavior

Reassignment (replacing an already-actively-assigned surveyor with a different one) is **not implemented** as a distinct operation - it is rejected the same way as a duplicate assignment, with the same 409 Conflict. This was a deliberate choice, not an oversight:

The real dataset's `Inspection_Status` vocabulary is exactly `{Assigned, Scheduled, In Progress, Completed}` - there is no "Cancelled" or "Reassigned" value. Safely retiring an existing active assignment without silently creating an ambiguous second active row would require inventing a new status value not present in the approved dataset, which the task explicitly disallows ("Do not invent new business values"). Rather than invent a schema-adjacent workaround, this step returns a clear, explicit conflict and documents the limitation here, per the task's own guidance: *"If reassignment cannot be represented safely without schema changes, return a clear conflict and document it rather than inventing a new database design."*

If a claim's active surveyor genuinely needs to be replaced, the existing inspection must first be completed (`Survey_Report_Submitted = True`, via the existing `PATCH /surveyor/inspections/{id}`) - at that point it is no longer "active," and a new assignment (to any surveyor, including the same one, e.g. for a re-inspection) succeeds normally. A dedicated reassignment operation is a reasonable future enhancement but was out of scope here.

## 11. Security considerations

- `Surveyor_ID` is never accepted as a raw, trusted string: the request only carries an `Employee_ID` to look up, and the value actually written to the database comes from the looked-up `AuthenticationUser` row, not the request body echoed back.
- Role is re-validated server-side (`Role == "Surveyor"`) even though only Surveyor accounts realistically have an `Employee_ID` populated - this is defense-in-depth, verified by a dedicated test using a synthetic fixture.
- Account status is re-validated server-side using the exact same `"Active"` convention already used to gate login (`api/v1/deps.py::get_current_user`, `api/v1/routers/auth.py`) - no new status value was invented.
- The assignment write is wrapped in a try/commit/rollback: if the commit fails (e.g. a generated `Inspection_ID` collision), the transaction is rolled back and no partial assignment row is left behind - verified by a dedicated rollback test.
- Extra/unexpected fields in the request body (e.g. a client-supplied `Claim_ID`, `Inspection_ID`, or `Inspection_Status`) have no effect - the Pydantic schema defines only `surveyor_employee_id`, and `Claim_ID` always comes from the URL path.

## 12. Testing

`backend/tests/test_surveyor_assignment.py` - 22 tests, all against real PostgreSQL: unauthenticated/role-based access to both endpoints, active-only surveyor listing, successful assignment by Officer and Admin, claim/surveyor not-found (404), Customer/Claims-Officer/inactive accounts rejected as invalid surveyors (422), duplicate assignment and reassignment both rejected (409), extra body fields cannot redirect the assignment, persistence with zero fabricated findings, assigned surveyor gaining claim access, a different surveyor still being denied, and a forced-failure rollback test proving no partial row survives a failed commit.

`frontend/src/pages/officer/__tests__/ClaimDetailsPage.test.jsx` - 7 tests: unassigned state and button, surveyor list loading (only the API's real eligible surveyors, never fabricated ones), selection + confirmation prompt, successful assignment refreshing the card, API error display, the Assign button disappearing once assigned, and pre-existing officer claim-detail sections (summary, documents, repair estimate) still rendering correctly.

All prior Step 5.8.5/5.8.6/5.8.7 backend tests (118) and frontend tests (66) still pass unmodified.

## 13. Manual verification

Performed against the live server and PostgreSQL: logged in as `dev_customer` and created a brand-new claim (confirming zero surveyor access beforehand); logged in as `dev_officer`, called `GET /officer/surveyors` (returned the real seeded `dev_surveyor`/`DEV-SURV-001`), and assigned it to the new claim; confirmed `dev_surveyor` could then read the claim via `GET /surveyor/claims/{id}` and see it in `GET /claims`; confirmed a duplicate assignment attempt returned 409; confirmed the existing, unmodified Vehicle Damage and Repair Estimate endpoints both succeeded (201) against the newly assigned claim, proving the downstream Surveyor workflow needed no changes. All manual-test rows (claim, accident, inspection, vehicle-damage, repair-estimate) were deleted afterward; the pre-existing seeded `DEV-CLM-001` assignment was left untouched throughout and verified unchanged at the end.

Only one Surveyor account exists in the development seed data (`dev_surveyor`), so "a different surveyor cannot access the claim" could not be re-demonstrated manually against a second real dev account; this exact scenario is covered by the automated test `test_different_surveyor_still_cannot_access_claim_after_assignment`, which creates a second surveyor fixture for the purpose.

## 14. Limitations

- No reassignment operation - see Section 10.
- No update/delete of an assignment beyond the existing `PATCH /surveyor/inspections/{id}` (already used to complete an inspection).
- `GET /officer/surveyors` returns only `Employee_ID`/`Username`/`Email`/`Account_Status` - no workload, caseload count, location, or specialization, because none of those fields exist in the approved schema.
- The manual test could only demonstrate the "different surveyor denied" scenario indirectly (via the automated test suite), since only one Surveyor account exists in the seeded dev data.

## 15. Why ACO is not used directly in production assignment

`ai_ml/surveyor_assignment/` is a research prototype exploring Ant Colony Optimization against a greedy baseline, using synthetic location/workload/availability/priority data - none of it derived from the approved 15-table schema (which has no surveyor location, workload, or availability columns to optimize over in the first place). The experiment's own results (mean cost 13.299 greedy vs. 13.307 ACO, with ACO roughly 1000x slower) show ACO did not consistently outperform greedy assignment in the tested scenarios.

This step's production assignment is therefore a simple, transparent, officer-driven selection from a real list of active surveyors - not an optimization algorithm, not AI-powered, not distance-based, and not workload-based. It does not claim intelligent optimization of any kind. The ACO module remains an experimental/research component, untouched and unconnected to this workflow.
