# Claims Officer Final Decision Persistence

## 1. Purpose

Makes the Claims Officer's final decision genuinely persisted. Before this step, `DecisionPage.jsx` collected a decision in local form state and displayed a message that "the CI-MICOP API does not currently expose a write endpoint for recording an officer decision" - nothing entered was ever saved. This step adds real persistence, reusing the existing `claim_decision_audit` table and the `Claim` model's own decision fields, with no schema change.

## 2. Claims Officer workflow

```
Claims Officer opens a claim -> Make Decision tab
                |
                v
   Reviews AI recommendation (if one genuinely exists) - supporting info only
                |
                v
        Selects Final Decision: Approved / Rejected / Partially Approved
                |
                v
       Enters Decision Reason (required) and Approved Amount
                |
                v
        Optionally enters Officer Comments
                |
                v
              Submits
                |
                v
   Claim.Final_Decision/Decision_Reason/Approved_Amount/Decision_Date updated
   AND a new claim_decision_audit row created - in ONE transaction
                |
                v
        Decision History card shows every past decision, oldest kept
```

## 3. Endpoint

`POST /api/v1/officer/claims/{claim_id}/decision` - Claims Officer only (see Section 7 on why Admin is excluded). Request body:

```json
{
  "Final_Decision": "Approved",
  "Decision_Reason": "Documents and evidence are consistent with the claimed damage.",
  "Approved_Amount": "45000.00",
  "Officer_Comments": "Standard approval."
}
```

Returns the created `ClaimDecisionAuditOut` row (201). `Claim_ID` comes from the URL path; `Claims_Officer_ID`, `AI_Recommendation`, `AI_Confidence_Score`, `Human_Review_Required`, `Escalation_Status`, `Escalated_To`, `Audit_Action`, and `Audit_Timestamp` are never accepted from the client - all server-derived (see Section 8).

## 4. Request flow

1. Authenticate the user (JWT).
2. Require the `Claims Officer` role and resolve the acting officer's `Employee_ID` (`api/v1/deps.py::require_claims_officer_employee_id`).
3. Validate the claim exists (404 if not).
4. Validate the decision payload (see Section 5).
5. Look up the claim's latest existing `claim_decision_audit` row, if any, to determine whether a genuine AI recommendation already exists (see Section 8).
6. Update `Claim.Final_Decision`, `Decision_Reason`, `Approved_Amount`, `Decision_Date`.
7. Create a new `ClaimDecisionAudit` row with a server-generated `Audit_ID`.
8. Commit both writes in one transaction; roll back and return 500 if the commit fails (see Section 6).
9. Return the persisted audit row.

## 5. Validation

`Final_Decision` is restricted to the three values that actually occur in the approved dataset (`ai_ml/datasets/CI_MICOP_15_Tables_Complete/14_claim_decision_audit.xlsx`, 654 rows): `Approved`, `Rejected`, `Partially Approved`. `Decision_Reason` is required (rejects empty/whitespace-only), trimmed, capped at 2000 characters (the columns are `Text`/unbounded, so this is an app-level cap consistent with other free-text fields elsewhere in the project, e.g. `Surveyor_Comments`). `Officer_Comments` is optional, trimmed, same cap. `Approved_Amount` is `Decimal`, never `float`, validated `>= 0`.

Cross-field rules, and what the approved dataset actually supports:

| Rule | Enforced? | Dataset finding |
|---|---|---|
| Rejected claims cannot have a positive Approved_Amount | **Yes** | The real dataset does NOT follow this (209/654 Rejected rows have Approved_Amount > 0, up to 148,862) - that is treated as pre-existing historical noise in synthetic data, not a rule to preserve, since the task explicitly asked for this rule to be enforced going forward. |
| Approved / Partially Approved require a positive Approved_Amount | **Yes** | Fully supported - 0 real rows of either type have Approved_Amount == 0. |
| Approved_Amount must not exceed Claim_Amount | **No** | Explicitly NOT implemented - 252 of 654 real rows (38.5%) have Approved_Amount > Claim_Amount, including 83 of 239 "Partially Approved" rows. This is not a rare exception; it disproves any such cap as an actual business rule. Per this task's own instruction not to invent an unsupported rule, no cap was added. |

## 6. Transaction behavior

The `Claim` update and the `ClaimDecisionAudit` insert are staged in the same SQLAlchemy session and committed with a single `db.commit()`. If the commit fails (verified with a forced primary-key collision on `Audit_ID`), the transaction rolls back as a whole - the claim's decision fields are left at their pre-decision values and no audit row is created. There is no separate, unrelated-transaction path where one write could succeed while the other fails.

## 7. Audit trail

`claim_decision_audit` is treated as fully append-only: `crud/claim_decision_audit.py::list_by_claim` was changed from ascending to **descending** `Audit_Timestamp` order (a small, in-scope fix - both existing consumers, `DecisionPage.jsx` and the officer claim-detail aggregate, already assumed `audits[0]` meant "the latest," which only became correct once this step makes claims genuinely accumulate more than one audit row). Repeated decisions on the same claim create new rows; nothing is ever deleted or overwritten. Verified by `test_decision_history_is_preserved_across_repeated_submissions`.

## 8. Human-in-the-loop principle: AI recommendation vs. officer final decision

The backend never computes, infers, or auto-selects a `Final_Decision`. `Final_Decision` is always exactly what the officer submitted.

If the claim's latest existing `claim_decision_audit` row has a genuine AI recommendation - a value from the approved dataset's real vocabulary (`Approve`, `Reject`, `Investigate`) - it is carried forward into the new audit row as supporting information only (`AI_Recommendation`, `AI_Confidence_Score`, `Human_Review_Required` are copied, never regenerated). It has no influence on `Final_Decision`, which always comes from the officer's own request body.

If no genuine AI recommendation exists for the claim (the common case in this project's live database - see Section 9), the new audit row honestly records `AI_Recommendation = "Pending"` (the project's existing sentinel convention, e.g. `schemas/surveyor.py::PENDING`) and `AI_Confidence_Score = 0.0000`, and the frontend explicitly shows "No AI recommendation is available for this claim" rather than presenting a placeholder as a real signal. The API response and the UI both make clear that the final decision is the officer's own selection - never an automated one.

## 9. What "genuine AI analysis" actually means in this project right now

The approved 654-row `claim_decision_audit` dataset (research/reference file, not loaded into the live database) has real `AI_Recommendation` values. The live PostgreSQL database, however, only ever had one seeded `claim_decision_audit` row (`DEV-AUD-001`, for `DEV-CLM-001`), and it deliberately uses `AI_Recommendation = "Review"` and `Final_Decision = "Pending"` - both intentional placeholders from the Step 3 dev seed script, not real dataset values. `services/claim_decision.py::REAL_AI_RECOMMENDATION_VALUES = {"Approve", "Reject", "Investigate"}` is the check used to distinguish a genuine prior recommendation from a placeholder; `"Review"` correctly falls outside that set and is treated as "no AI recommendation available," exactly as manually verified in this task (see Section 12).

## 10. Claim status / state machine

`Claim.Claim_Status` is deliberately left untouched by this endpoint. The approved dataset shows no discoverable correlation between `Claim_Status` and `Final_Decision` - a crosstab of all 654 rows shows an almost-uniform distribution across every (status × decision) combination, meaning there is no existing state-machine rule linking the two to reuse, and inventing one was out of scope ("Do NOT invent a new claim lifecycle"). Only the four decision fields the `Claim` model already has - `Final_Decision`, `Decision_Reason`, `Approved_Amount`, `Decision_Date` - are updated.

## 11. Why Admin cannot submit a decision

`ClaimDecisionAudit.Claims_Officer_ID` is a `NOT NULL` foreign key to `authentication_users.Employee_ID`, and it must reference the **acting user's own** identity (unlike claim assignment, where the `Employee_ID` being validated belongs to the *target* surveyor, not the actor). Admin accounts in this project have no `Employee_ID` - the approved 660-row authentication dataset has no `Admin` role at all; Admin is a synthetic, project-added role. A new `api/v1/deps.py::require_claims_officer_employee_id` dependency (mirroring the existing `require_surveyor_employee_id` pattern from Step 5.8.5) therefore restricts this endpoint to `Claims Officer` accounts only. This was verified live: `dev_admin` receives 403.

## 12. Test coverage

**Backend** (`backend/tests/test_claim_decision.py`, 20 tests, all passing against real PostgreSQL): valid Approved/Rejected/Partially Approved submissions; required decision reason; negative amount rejected; invalid decision value rejected; Rejected-with-positive-amount rejected; Approved/Partially-Approved-with-zero-amount rejected; Approved_Amount may legitimately exceed Claim_Amount (201, not rejected); Customer/Surveyor/unauthenticated/Admin all rejected; nonexistent claim 404; Claim fields updated correctly; audit record created with the correct `Claims_Officer_ID`; honest placeholder AI fields when no genuine recommendation exists; a genuine prior AI recommendation is carried forward unchanged; decision history preserved across repeated submissions (both rows survive, `Claim` reflects only the latest); and a forced-collision rollback test proving neither the claim update nor the audit insert survives a failed commit.

**Frontend** (`frontend/src/pages/officer/__tests__/DecisionPage.test.jsx`, 9 tests): page renders; real Final_Decision options render; decision-reason validation blocks submission; approved-amount validation blocks submission; a valid submission calls `submitDecision` with only the human-entered fields; rapid repeated clicks call the API exactly once; a successful submission shows the success message; an API error is displayed verbatim; and AI information is shown as supporting/recommendation text (never presented as the final decision), including the explicit "not available" state when no genuine recommendation exists.

All prior tests still pass: 160/160 backend (140 pre-existing + 20 new), 82/82 frontend (73 pre-existing + 9 new).

## Limitations

- No escalation workflow is implemented in this step - every new audit row uses the real, neutral `Escalation_Status = "Not Escalated"` value; the existing `EscalationsPage`/`RfiPage` remain untouched, read-only, and out of scope.
- No upper-bound relationship is enforced between `Approved_Amount` and `Claim_Amount` (see Section 5) - the approved dataset disproves any such fixed rule.
- `Claim_Status` is not updated by a decision - no existing state-machine rule links it to `Final_Decision` (see Section 10); this is a reasonable future enhancement if such a rule is later formally specified.
- The AI "carried forward" recommendation is exactly the prior audit row's own value - this step performs no new AI computation of any kind, consistent with the human-in-the-loop principle and the project's read-only, static Step 5.4/5.5 AI Insights architecture.
