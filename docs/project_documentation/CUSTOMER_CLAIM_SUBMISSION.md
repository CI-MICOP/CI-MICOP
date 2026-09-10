# Customer Claim Creation / FNOL Workflow

Implements the real `Customer -> New Claim -> Submit -> PostgreSQL -> My Claims -> Claim Details` flow. Before this change, `NewClaimPage` collected information across four steps and then discarded it, showing a message that claim creation was not connected to the backend. This document describes what was added, why each default value was chosen, and what is intentionally still out of scope.

## 1. Endpoint

`POST /api/v1/claims` - added to the existing `claims` router alongside the pre-existing `GET /claims` and `GET /claims/{claim_id}`. Requires the `Customer` role via the existing `require_customer_id` dependency. No new router, no new prefix, no new database tables.

## 2. Customer_ID is never trusted from the client

`ClaimCreate` (in `backend/app/schemas/claim.py`) has no `Customer_ID` field at all. The router resolves it exclusively from the authenticated JWT via `require_customer_id`, and that value is what gets written to `claims.Customer_ID`. A customer cannot file a claim as anyone else, regardless of what the request body contains.

## 3. Fields the customer can submit

`Policy_ID`, `Vehicle_ID`, `Claim_Date` (incident date), `Claim_Type` (`Own Damage` / `Third Party` / `Theft` - the three values actually present in the approved dataset), `Claim_Amount`, `Claim_Description`, `Place_of_Accident`, `Accident_Pincode`, plus the accident details the existing `NewClaimPage` UI already collected: `Accident_Time`, `Third_Party_Involved`, `Injury_Reported`, and (derived) `Police_Report_Available`.

No internal/processing field (`Approved_Amount`, `Final_Decision`, `Decision_Date`, `Decision_Reason`, `Claim_Processing_Days`, any AI/fraud/audit field) is accepted from the client. They are always server-assigned in `app/services/claim_creation.py`.

## 4. Ownership validation (`_validate_ownership`)

Before any row is written:

1. The policy must exist (else `404`).
2. `policy.Customer_ID` must equal the authenticated customer (else `403`).
3. The vehicle must exist (else `404`).
4. `vehicle.Customer_ID` must equal the authenticated customer (else `403`).
5. The policy and vehicle must reference each other (`policy.Vehicle_ID == vehicle.Vehicle_ID` and `vehicle.Policy_ID == policy.Policy_ID`) - else `400`.

This never trusts the pairing the frontend sent; it re-derives it from the existing `policies`/`vehicles` relationship every time.

## 5. Claim_ID / Claim_Number generation

Both are generated server-side in `app/crud/claim.py` and checked against the database before being handed back:

- `Claim_ID`: `CLM-<10 hex chars>` (fits the existing `String(30)` primary key).
- `Claim_Number`: `CLM-<year>-<8 hex chars>`, matching the format requested for this feature and distinct from the placeholder `DEV-CLAIM-001` used by the seed script. Checked against the `Claim_Number` unique constraint before use (20 attempts, extremely unlikely to ever collide, but the check is explicit rather than assumed).

## 6. Initial claim state

- `Claim_Status = "Under Review"`, `Final_Decision = "Pending"`, `Approved_Amount = 0.00`.
- `Decision_Reason = "Awaiting Claims Officer review. No decision has been made yet."`
- `Claim_Processing_Days = 0`, `Repair_Duration_Days = 0`.
- No AI/fraud fields are populated by this endpoint - the Claims Officer remains the sole decision-maker, and nothing here writes a decision.

## 7. Safe defaults for non-nullable columns the FNOL form doesn't collect

The approved `claims` table has several non-nullable columns that belong to later processing stages, not FNOL intake. Rather than changing the schema, each gets a documented, non-fabricated default:

| Column | Value | Rationale |
|---|---|---|
| `Claim_Year` | `str(Claim_Date.year)` | Derived directly from the submitted incident date. |
| `Claims_History_Code` | `"C0"` if the vehicle has no prior claims, else `"C1"` | Derived from `vehicles.Previous_Claim_Count`, matching `seed_dev_data.py`'s convention. |
| `Incurred_Claims_Code` | `"I1"` | Fixed "claim incurred/open" code, matching the seed convention. No richer codebook exists in the approved schema/dataset to derive this from. |
| `Nature_of_Loss_Code` | `"COL"` (Own Damage) / `"THEFT"` (Theft) / `"TP"` (Third Party) | Mapped directly from the customer's own `Claim_Type` selection. |
| `Insurer_NOL_Code` | `"NOL1"` | Fixed project-convention default (matches the seed script); no per-claim signal exists yet to vary it. |
| `TPPD_Statutory_Cover_Flag` | Copied from `policies.TPPD_Statutory_Cover_Flag` | Real, already-known policy-level data - not invented. |
| `Claim_Intimation_Date` | Today's server date | The actual date the claim was filed, distinct from the incident date. |
| `Date_of_Disbursement` | Today's server date (same as intimation date) | **Not a real payment date.** The column is non-nullable with no "not yet disbursed" representation in the approved schema. This placeholder must never be read as evidence a disbursement occurred - `Claim_Status`/`Final_Decision` are the fields that reflect real claim state. |
| `Decision_Date` | Today's server date | Same placeholder rationale as above - no decision has actually been made. |
| `TP_*` / `Wider_Legal_Liability_Amount` / `PA_*` fields | `0.00` | None of these third-party amounts are known at FNOL time, regardless of claim type. |
| `Nature_of_Injury_Code` | `"NONE"` or `"PENDING"` | Set from the customer's own "Injury Reported" answer; `"PENDING"` reflects that no medical assessment has happened yet. |
| `Interim_Award_Flag` | `False` | No award has been made. |
| `Settlement_Basis_Code` | `"PENDING"` | Explicitly required by the task spec. |
| `Fatal_NonFatal_Flag` | `False` | The FNOL workflow does not currently collect fatality information. |
| `Open_Provision_Main` | `Claim_Amount` | Initial reserve equal to the amount claimed, matching `seed_dev_data.py`'s convention. |
| `Open_Provision_Expenses` / `Open_Provision_Interest` / all `Closing_Provision_*` | `0.00` | No expenses/interest/closure exist yet for an open claim. |

A `tp_claims` row is **not** created at FNOL time - the task scoped required child-record creation to `accidents` only; a third-party claim record is normally established later once a third party actually claims against the policy.

## 8. Accident child record

The `accidents` table already exists in the approved 15-table schema. A row is created in the same transaction as the claim, using the existing model - no new columns, no new table:

- `Accident_Date` = the submitted `Claim_Date`; `Accident_Time` = the submitted time, or midnight if not provided.
- `Accident_Location` / `Accident_Description` come directly from the customer's own text.
- `Accident_City` reuses the free-text "Place of Accident" value (the form has no separate city field); `Accident_State` falls back to the customer's registered state. Both are documented best-effort values, not verified accident-site facts.
- `Weather_Condition` / `Road_Condition` default to `"Not Reported"` (not collected by the form).
- `Road_Type_Code` is copied from the vehicle's own `Road_Type_Code` (real, existing data).
- `Accident_Type` defaults to `"Not Specified"` (the form's `Claim_Type` taxonomy - Own Damage/Third Party/Theft - is not the same concept as an accident type like Collision/Fire).
- `Police_Report_Available` is derived from whether the customer filled in a police station name.
- **Limitation:** the "Police Station" text field on the existing `NewClaimPage` UI is not persisted anywhere. The approved `accidents` table only has `FIR_Number` (a different concept - an FIR number, not a station name), and the task instructions explicitly prohibit inventing new columns. This is a known, documented gap rather than a silently dropped or fabricated value.
- `Witness_Available` defaults to `False` (not collected by the form).

## 9. Transaction

`create_claim_for_customer` writes the `Claim` then the `Accident` inside one transaction (`flush()` between them so the accident's FK is valid, single `commit()` at the end). Any failure rolls back both and raises a `500` with a generic message - no partial claim is ever left in the database. Verified by `test_transaction_rolls_back_if_accident_creation_fails`.

## 10. Frontend changes

- `frontend/src/services/claimService.js`: added `createClaim(payload)`, using the existing `apiClient` (no second Axios instance).
- `frontend/src/pages/customer/NewClaimPage.jsx`: the existing four-step wizard is unchanged in structure. Three fields required by the backend but not previously collected were added to Step 1 (Incident Details) as small, in-place additions - Claim Type, Estimated Claim Amount, and Accident Pincode - rather than adding a new step or redesigning the page. "Submit Claim" now calls the real endpoint, shows a loading state, is disabled while a request is in flight (preventing duplicate submissions), and on success shows the generated `Claim_Number`, the `Under Review` status, and buttons to view the claim or return to My Claims. The old "not yet connected to the backend" message has been removed. If documents were selected in Step 3, the success screen clarifies that document upload is a separate, not-yet-connected workflow rather than pretending the files were saved.

## 11. Out of scope (unchanged in this task)

Document upload/storage, OCR, AI risk scoring on new claims, fraud auto-rejection, surveyor auto-assignment, and any Claims Officer decision-writing endpoint. This task only makes the FNOL submission itself real; everything downstream of "Under Review" is unchanged.
