# AI Backend Integration (Step 5.8.10)

**This is a research-prototype integration using synthetic/de-identified data. Nothing in this document should be read as a measurement of real-world fraud-detection accuracy.**

---

## 1. Purpose

Step 5.8.1's audit identified that the Step 5.5 AI officer integration was entirely static - a hand-exported JSON bundled into the frontend. This step closes that gap for the target architecture `AI/ML → FastAPI → React`: a new read-only backend endpoint aggregates the project's existing, already-computed AI/ML artifacts for a specific claim and serves them live to the Claims Officer portal, replacing the per-open-claim static lookup. It does **not** retrain, recompute, or invent anything - see Section 3.

## 2. What AI artifacts already existed (inspected before writing any code)

| Artifact | Type | Location |
|---|---|---|
| Step 5.4 risk-fusion scores (654 claims) | Precomputed CSV | `ai_ml/model_artifacts/risk_fusion/full_dataset_risk_fusion_scores.csv` |
| Step 5.4 full per-signal breakdowns (4 representative examples) | Precomputed JSON | `ai_ml/model_artifacts/risk_fusion_explanations/*.json` |
| Fraud risk analysis | Database table (part of the approved 15-table schema) | `fraud_risk_analysis` |
| Cross-document consistency analysis | Database table | `cross_document_consistency` |
| Repair-estimate AI-adjacent columns | Database columns on an existing table | `repair_estimates.Excessive_Claim_Amount_Indicator`, `.Estimate_Anomaly_Score` |
| Trained fraud models (LogReg/RF), SHAP explanations, evaluation metrics | Executable pipeline artifacts | `ai_ml/model_artifacts/*.pkl`, `shap_example_explanations.json`, `evaluation_results.json` |
| Step 5.5 static export | Precomputed JSON, bundled into the frontend | `frontend/src/data/aiRiskFusionDemo.json` |

All of the above are **precomputed claim-level results** (category B) - no executable model pipeline is invoked by this step. The `.pkl` models and SHAP explainer were inspected but not wired in: Step 5.4 already found that model-derived signals perform only marginally above chance (see `AI_VS_NON_AI_RESULTS.md`), and this step's job is to expose what already exists honestly, not to run new inference.

## 3. Architecture / data flow

```
ai_ml/experiments/run_risk_fusion_experiment.py   (Step 5.4, unmodified, not re-run)
        |  already produced (before this step)
        v
ai_ml/model_artifacts/risk_fusion/full_dataset_risk_fusion_scores.csv
ai_ml/model_artifacts/risk_fusion_explanations/*.json
        |
        |  read directly by (NEW, Step 5.8.10)
        v
backend/app/services/risk_fusion_artifacts.py   (stdlib csv/json, cached in memory, read-only)
        |
        v
backend/app/services/ai_analysis.py   (merges with 3 existing DB tables via existing CRUD)
        |
        v
GET /api/v1/officer/claims/{claim_id}/ai-analysis   (NEW)
        |
        v
frontend/src/services/officerService.js::getAiAnalysis(claimId)   (NEW)
        |
        v
frontend/src/components/officer/ai/LiveAiAnalysisPanel.jsx   (NEW, reuses existing leaf components)
        |
        v
frontend/src/pages/officer/AiInsightsPage.jsx
```

No new database table was created. No Alembic migration was required (`alembic upgrade head` reports no pending migrations both before and after this step). The backend reads the risk-fusion CSV/JSON files with the standard-library `csv`/`json` modules (not `pandas`, which is not a declared backend dependency) via a `RISK_FUSION_ARTIFACTS_ROOT` setting following the exact same pattern already established for `DOCUMENT_STORAGE_ROOT`/`EVIDENCE_STORAGE_ROOT`.

The "AI Demonstration Examples" selector on the same page (Step 5.5) is **intentionally left on the static export**: those 4 example claims (`CLM-000007`, etc.) do not exist in the live `claims` table, so the live endpoint would 404 for them. Two data sources coexist on this page for two different, legitimate purposes: the live panel analyzes whichever real claim is currently open; the demonstration selector lets an officer browse Step 5.4's 4 representative research examples by their original dataset IDs.

## 4. Endpoint

`GET /api/v1/officer/claims/{claim_id}/ai-analysis` - read-only, no request body. Response shape (`AiClaimAnalysisOut`):

```json
{
  "claim_id": "DEV-CLM-001",
  "available": false,
  "overall_risk": null,
  "risk_score": null,
  "confidence_score": null,
  "confidence_band": null,
  "review_priority": null,
  "contributing_signal_count": null,
  "unavailable_signal_count": null,
  "human_review_required": true,
  "fraud_analysis": { "available": true, "risk_category": "Low", "fraud_risk_score": "12.00", "anomaly_score": "0.0800", "overall_risk_score": "12.00", "reason_codes": [], "message": null },
  "consistency_analysis": { "available": true, "overall_status": "Partial", "document_consistency_score": "0.9200", "contradictions": ["Claim_Amount_Match: Partial"], "message": null },
  "repair_estimate_analysis": { "available": true, "anomaly_detected": false, "anomaly_score": "0.1200", "reason_codes": [], "message": null },
  "reason_codes": [],
  "officer_explanations": [],
  "signals": [],
  "explanation": [],
  "limitations": ["...", "..."],
  "data_source": "Step 5.4 risk-fusion research prototype (...)"
}
```

This is the actual response for the seeded `DEV-CLM-001` (captured during manual verification, Section 12) - it demonstrates the common case: `overall_risk`/`risk_score`/etc. are `null` with `available: false` (this claim is outside the Step 5.4 dataset), while the three DB-backed sub-analyses are `available: true` because `DEV-CLM-001` has seeded example rows in those tables.

## 5. RBAC

`require_roles("Claims Officer", "Admin")` - the same dependency already used by every other endpoint in `officer.py` (`list_eligible_surveyors`, `list_claims_for_processing`, etc.). No custom authorization logic was written. Customer and Surveyor both receive 403 regardless of which claim is requested (verified live and by test). Unauthenticated requests receive 401. A nonexistent `claim_id` returns 404 before any AI lookup happens.

Unlike `POST /officer/claims/{claim_id}/decision` (Step 5.8.9), this is a pure read with no `Claims_Officer_ID` to persist, so Admin has no structural obstacle here and is fully permitted - consistent with "existing RBAC conventions permit administrative actions" for read access.

## 6. AI data source, per component

- **Overall risk / confidence / signals / explanation / reason_codes**: Step 5.4's risk-fusion CSV, matched by exact `Claim_ID` string. Because the live `claims` table and the Step 5.4 dataset were never merged (the live database only ever contained the small dev seed plus whatever claims the running application itself created), this match succeeds for virtually no real claim today - `available: false` is the expected, honest, common result. This is not a bug; it is a direct, disclosed consequence of the Step 5.4 export being a one-time static artifact (see `AI_OFFICER_INTEGRATION.md`, Section 13, which already documented this limitation for the static version).
- **fraud_analysis**: the existing `fraud_risk_analysis` table, read via the existing `crud/fraud_risk_analysis.py::list_by_claim`. `reason_codes` are derived directly from which of the table's own boolean indicator columns are `True` (e.g. `SUSPICIOUS_GARAGE_INDICATOR`) - never an invented description.
- **consistency_analysis**: the existing `cross_document_consistency` table, read via `crud/cross_document_consistency.py::list_by_claim`. `contradictions` lists the table's own per-field match columns whose value is not the real dataset's `"Match"` value (e.g. `"Claim_Amount_Match: Partial"`).
- **repair_estimate_analysis**: the existing `repair_estimates` table's `Excessive_Claim_Amount_Indicator`/`Estimate_Anomaly_Score` columns. **Important honesty rule**: `services/repair_estimate_creation.py` (Step 5.8.7) always writes `False`/`0.0000` for these two columns for every repair estimate created through the live application - that is a documented "not yet analyzed" placeholder, not a genuine score of zero. `services/ai_analysis.py::_is_unanalyzed_placeholder` detects this exact pattern and reports `available: false` with an explanatory message instead of presenting a placeholder as a real prediction.

No row in any of these three tables is currently written by a live model pipeline in this codebase - today, the only populated example rows are the ones `backend/seed_dev_data.py` inserted directly for `DEV-CLM-001`. This endpoint reads whatever is actually stored, honestly, without trying to guess whether a given row is "real" versus example data (that distinction is undecidable in general - the repair-estimate case above is the one narrow exception, because this project's own code is the only thing that has ever written that specific placeholder pattern). A future automated pipeline could populate these same tables through the same schema, and this endpoint would serve its output with no code change.

## 7. Explainability

Where a full per-signal breakdown exists (4 of 654 Step 5.4 claims), the actual `signals` array (7 entries: `signal_name`, `category`, `signal_value`, `availability`, `explanation`) and `officer_explanations` (title/detail/severity per reason code) are returned exactly as Step 5.4 computed them - the frontend renders them with the same `SignalBreakdown`/`ReasonCodeList` components Step 5.5 already built. For the other 650 claims, only the bare `reason_codes` list and summary risk/confidence values exist; `signals`/`officer_explanations` are empty, and the UI shows "Full signal breakdown not generated for this claim" rather than fabricating one. If neither reason codes nor a full breakdown exist for a claim (the no-risk-fusion-result case), the panel shows the honest "No overall AI risk assessment available" state instead of an empty chart.

## 8. Uncertainty / confidence

Confidence is served as a value entirely separate from risk (`confidence_score`/`confidence_band` vs. `risk_score`/`overall_risk`), preserving Step 5.4's central finding that these are independent axes (see `AI_OFFICER_INTEGRATION.md`, Section 5-6). `human_review_required` defaults to `true` whenever no full breakdown exists for a claim (matching the same human-in-the-loop-safe default already used in `services/claim_decision.py` for a fresh `claim_decision_audit` row) - the system never assumes review is unnecessary just because detailed data is missing.

## 9. Human-in-the-loop principle

`services/ai_analysis.py` has no write path whatsoever - it imports no CRUD `create`/`update` function, and `get_ai_analysis_for_claim` never touches `Claim.Final_Decision` or `claim_decision_audit`. This was verified by a dedicated test (`test_ai_analysis_endpoint_does_not_modify_claim_decision`) that reads a claim's decision fields before and after calling the AI-analysis endpoint and asserts they are byte-identical, with zero new audit rows created.

`POST /officer/claims/{claim_id}/decision` (Step 5.8.9) remains the **only** place a Claims Officer's decision is persisted, and it is completely independent of this endpoint - `DecisionPage.jsx` was not modified in this step and still only reads AI-adjacent information from `claim_decision_audit` (its own existing, separate "AI Recommendation (Supporting Information)" card). `LiveAiAnalysisPanel.jsx` (this step's new component) contains zero buttons and zero form controls - verified by a dedicated frontend test asserting the rendered page has no `button` or `textbox` elements.

## 10. Frontend changes

- `frontend/src/services/officerService.js`: added `getAiAnalysis(claimId)`.
- `frontend/src/components/officer/ai/LiveAiAnalysisPanel.jsx` (new): composes the existing `RiskScoreCard`, `ConfidenceCard`, `SignalBreakdown`, `ReasonCodeList`, `HumanReviewNotice` components (all unchanged) with three new small sections (Fraud/Risk Signals, Consistency Analysis, Repair Estimate Analysis) and a Limitations card, all built from the same `Card`/`EmptyState`/`StatusBadge` primitives already used everywhere else in the CI-MICOP officer portal - no new visual language was introduced.
- `frontend/src/pages/officer/AiInsightsPage.jsx`: the per-open-claim panel now fetches live data via `getAiAnalysis` instead of the static `aiRiskService.getAiInsightsForClaim`; the "AI Demonstration Examples" section is unchanged (see Section 3 for why).

No existing component under `frontend/src/components/officer/ai/` was modified - `AIInsightCard.jsx` (used only by the demonstration-examples section now) and its existing tests are untouched.

## 11. Why AI does not make the final decision

Unchanged from Step 5.8.9/Step 5.5: the Claims Officer makes the final decision through a completely separate write endpoint that has no dependency on this one. This step only adds a second, richer, live read surface for AI-adjacent information - it introduces no new way for AI output to reach `Claim.Final_Decision`.

## 12. Test coverage

**Backend** (`backend/tests/test_ai_analysis.py`, 11 tests, all passing against real PostgreSQL): Officer/Admin access (200); Customer/Surveyor/unauthenticated rejected (403/401); unknown claim (404); a valid Step 5.4 result returned correctly (using a test claim whose `Claim_ID` exactly matches a real representative example, `CLM-000007`); all three DB-backed sub-analyses returned correctly from freshly-inserted non-placeholder rows; missing/unavailable results represented honestly with explanatory messages and no fabricated zero values; the Step 5.8.7 repair-estimate placeholder correctly reported as unavailable; and the endpoint proven not to modify `Claim.Final_Decision` or create any `claim_decision_audit` row.

**Frontend** (`frontend/src/pages/officer/__tests__/AiInsightsPage.test.jsx`, 6 tests): the live analysis loads and calls the API with the correct claim ID; a loading state renders before it resolves; an available analysis renders risk/confidence cards; every component renders an honest "unavailable" state (with no fabricated "0/100" score) when nothing exists; the human-review warning notice renders; and the page contains zero buttons or text inputs (cannot modify the human decision).

All prior tests still pass: 171/171 backend (160 pre-existing + 11 new), 88/88 frontend (82 pre-existing + 6 new).

## 13. Manual API verification

Performed against the live server and PostgreSQL using `dev_officer`/`dev_customer`/`dev_surveyor`: `GET /officer/claims/DEV-CLM-001/ai-analysis` as `dev_officer` returned 200 with the exact response shown in Section 4 (fraud/consistency/repair-estimate available from the dev seed, overall risk-fusion unavailable since `DEV-CLM-001` is outside the Step 5.4 dataset); the same call as `dev_customer` and `dev_surveyor` both returned 403; a nonexistent claim ID returned 404; an unauthenticated request returned 401. This endpoint performs no writes, so no test records were left in the database.

## 14. Limitations

- The Step 5.4 risk-fusion result is `available: false` for almost every real claim in the live system today, because the live `claims` table and the 654-row Step 5.4 dataset share no common `Claim_ID`s outside of hand-crafted test fixtures. This is disclosed, not hidden - the response's own `limitations` array says so explicitly for every unavailable claim.
- `fraud_risk_analysis` and `cross_document_consistency` currently have exactly one populated row each in the live database (the `DEV-CLM-001` seed example) - no pipeline in this codebase writes to them yet. This endpoint would serve real output from either table the moment such a pipeline exists, with no code change required.
- No SHAP values from the trained fraud models (`ai_ml/model_artifacts/*.pkl`) are surfaced - Step 5.4's own risk-fusion reason codes/signals are the most claim-specific explainability artifact that already exists; wiring in raw SHAP output was not attempted, to avoid overstating what this step verified.
- This remains a research-prototype integration validated only on a synthetic/de-identified dataset (`AI_VS_NON_AI_RESULTS.md`) - no claim about real-world fraud-detection accuracy is made anywhere in this endpoint's response or the UI that renders it.
