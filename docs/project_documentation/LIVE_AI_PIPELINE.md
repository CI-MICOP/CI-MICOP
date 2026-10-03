# Live Claim AI Analysis Pipeline (Step 5.8.11)

> **Update (Step 5.8.18):** `document_consistency_mismatch`,
> `evidence_duplication` and `information_quality` (photo part) are now
> computed live from the checks built in Steps 5.8.13-B to 5.8.17, so a claim
> can reach 6 of 7 signals. Fraud screening is still never computed live.
> The audit below describes the Step 5.8.11 state. See
> `LIVE_SIGNAL_INTEGRATION.md`.

**This is a research-prototype live pipeline using synthetic/de-identified reference data. It does not claim production-grade AI, real insurer validation, universal AI superiority, or measured real-world fraud-detection accuracy.**

---

## 1. Purpose

Step 5.8.10 exposed already-computed AI artifacts (the Step 5.4 static risk-fusion export plus three existing DB tables) through a read-only `GET` endpoint - it never processed a claim's own current data. This step closes that specific gap: `POST /officer/claims/{claim_id}/ai-analysis/run` computes a result from the claim's actual live PostgreSQL data, on demand, using only the small subset of the Step 5.4 methodology that genuinely still works once the offline synthetic dataset is replaced with the live application's real (mostly placeholder-heavy) data.

## 2. Architecture

```
Claims Officer clicks "Run AI Analysis"
        |
        v
POST /officer/claims/{claim_id}/ai-analysis/run   (Claims Officer/Admin only)
        |
        v
backend/app/services/ai_pipeline.py :: run_claim_ai_analysis(db, claim_id)
        |
        |-- crud/claim, policy, document, vehicle_damage, evidence,
        |   repair_estimate, surveyor_inspection  (existing CRUD, read-only)
        |
        |-- builds 7 Signal-shaped results: 2 genuinely computed live,
        |   5 explicitly "unavailable" with a specific, accurate reason
        |
        |-- fuses + scores confidence using formulas ported faithfully
        |   from ai_ml/risk_fusion/fusion_engine.py + uncertainty.py
        v
LiveAiAnalysisRunOut  (in-memory only - never written to PostgreSQL)
        |
        v
frontend/src/components/officer/ai/LiveRunPanel.jsx
```

No new database table was created, and the result is **not persisted** (see Section 9). No Alembic migration was required (`alembic upgrade head` reports no pending migrations before and after this step).

## 3. Repository audit - which AI components can genuinely process a NEW claim

Every component was inspected against the actual repository (`ai_ml/`, backend service/model code) before any implementation, per this task's explicit instruction not to assume.

| Component | Existing code | Trained artifact | Can process a NEW live claim? | Required inputs | Output | Safe to integrate? |
|---|---|---|---|---|---|---|
| OCR / information extraction | None anywhere in the repo (`ai_ml/ocr_pipeline/` is an empty `.gitkeep` placeholder) | None | No | N/A | N/A | **No** - never implemented |
| Cross-document consistency | `cross_document_consistency` DB table; `ai_ml/common/feature_builder.py` only ever *reads* this table's columns as model features, never computes them | None (no algorithm) | No | N/A | N/A | **No** - no consistency-computation code exists anywhere; the table's only populated row today is a hand-seeded dev example, not the output of any live process |
| Trained fraud model (LogReg/RF) | `ai_ml/models/train_fraud_models.py` | `logistic_regression_fraud_label.pkl`, `random_forest_fraud_label.pkl` (real, trained) | **No** | 40+ features across `vehicle_damage`/`repair_estimates`/`cross_document_consistency`/`evidence`/`documents`, built by `ai_ml/common/feature_builder.py` from the offline XLSX dataset | Fraud probability/label | **No** - most required features are either absent for a new claim or are Step 5.8.x's own honest "not yet analyzed" placeholders (always `False`/`0.0000`). Feeding those to the model as if genuine would systematically bias every live prediction toward "no risk", regardless of the claim's true risk - textbook training-serving skew, effectively a fabricated result |
| Rule-based fraud screener | `ai_ml/baselines/rule_based_fraud.py` | Calibrated thresholds (not a black box, but not runnable on placeholder-only inputs either) | **Partially** | 4 of its 6 rule components depend on the same permanently-placeholder columns as the trained model | 0/1 flag + reason codes | **No** (full screener) - only its 2 purely-numeric sub-components are safe; see the next two rows |
| Repair-estimate ratio (`repair_estimate_anomaly`, ratio component only) | `ai_ml/risk_fusion/signal_builder.py` | None (deterministic ratio vs. reference percentiles) | **Yes**, once a repair estimate exists | `RepairEstimate.Repair_Estimate`, `Claim.Claim_Amount` | Ratio-based anomaly value in [0,1] | **Yes** - integrated (Section 4) |
| Claim-timing anomaly (`claim_pattern_anomaly`) | `ai_ml/risk_fusion/signal_builder.py` | None (deterministic ratio vs. reference percentiles) | **Yes**, for any claim | `Claim.Claim_Date`, `Policy.Policy_Start_Date` (always present) | Timing anomaly value in [0,1] | **Yes** - integrated (Section 4) |
| Evidence duplication | `ai_ml/risk_fusion/signal_builder.py` | None | No | `Evidence.Duplicate_Evidence_Indicator` | N/A | **No** - Step 5.8.6's `evidence_upload.py` always writes `False` (no live duplicate-detection pipeline exists) |
| Document completeness | `ai_ml/risk_fusion/signal_builder.py` | None | No | `Document.Document_Completeness` | N/A | **No** - Step 5.8.4's `document_upload.py` always writes `0.0000` |
| Information quality (OCR/image quality) | `ai_ml/risk_fusion/signal_builder.py` | None | No | `Document.OCR_Confidence_Score`, `Evidence.Image_Quality`, `Evidence.Evidence_Confidence_Score` | N/A | **No** - all three are always `0.0000` placeholders on live uploads |
| Risk fusion (weighted average) | `ai_ml/risk_fusion/fusion_engine.py` | None - transparent formula, not trained | **Yes** - the formula itself has no dependency on the synthetic dataset | Whichever signals are actually available | Renormalized weighted risk score | **Yes** - ported faithfully (Section 4) |
| Uncertainty / confidence | `ai_ml/risk_fusion/uncertainty.py` | None - transparent formula | **Yes** | The same signal list | Confidence score + band + reasons | **Yes** - ported faithfully (Section 4) |
| Explainability / SHAP | `ai_ml/explainability/shap_explainer.py`, `shap_example_explanations.json` | Depends on the trained fraud model | No | Trained model + full feature row | Per-feature attribution | **No** - blocked by the same trained-model issue above; explaining a placeholder-driven prediction would be explaining nothing real |
| Reason-code vocabulary | `ai_ml/explainability/reason_codes.py` | None - static lookup dict | Yes, as labeling only | N/A | Human-readable text | **Yes** - reused only for wording (`ReasonCodeList.jsx`, unchanged from Step 5.8.10), not for live scoring |

**Conclusion: only 2 of the 7 Step 5.4 signal families are genuinely, honestly live-computable today.** This matches the task's own fallback instruction - the repository does not contain enough live-capable implementation for a full live inference pipeline, so this step implements exactly the safe subset plus an honest orchestration/status layer for everything else, rather than inventing a pipeline the evidence doesn't support.

## 4. What was actually integrated

`backend/app/services/ai_pipeline.py`:

- **`claim_pattern_anomaly`**: `(Claim.Claim_Date - Policy.Policy_Start_Date).days`, scaled against reference 10th/50th percentiles computed once from the approved 654-claim dataset (`ai_ml/datasets/CI_MICOP_15_Tables_Complete/{05_claims,04_policies}.xlsx`), using the exact same formula as `ai_ml.risk_fusion.signal_builder.ReferenceStats`/`_scale_between`. Always computable for any claim, since every claim has a policy with a start date.
- **`repair_estimate_anomaly` (ratio only)**: `RepairEstimate.Repair_Estimate / Claim.Claim_Amount`, scaled against reference 50th/90th percentiles computed the same way. Computable once at least one repair estimate exists. The `Excessive_Claim_Amount_Indicator` flag is deliberately **excluded** from this live computation - see Section 9 of `SURVEYOR_REPAIR_ESTIMATE_WORKFLOW.md` and Step 9 below.
- **Fusion**: `_fuse()` ports `ai_ml/risk_fusion/fusion_engine.py::equal_weight_fusion` exactly (equal weight per available signal, renormalized - with 1-2 signals this is just their arithmetic mean) and the same `RISK_BAND_THRESHOLDS` (CRITICAL/HIGH/MEDIUM/LOW).
- **Uncertainty**: `_compute_uncertainty()` ports `ai_ml/risk_fusion/uncertainty.py::compute_uncertainty` exactly - same `coverage x agreement x signal_trust` formula, same `MIN_SIGNALS_FOR_ANY_CONFIDENCE = 2` and `CONFIDENCE_BAND_THRESHOLDS`, using `statistics.pstdev` in place of `numpy.std` (identical result for this use, and avoids adding `numpy` as a new backend dependency for a formula that does not need it).
- The other 5 signal families are represented as explicit `LiveSignalOut` entries with `availability: "unavailable"` and the specific reason from the audit table above - never a fabricated value, never silently omitted.

The reference percentiles were computed once, offline, from the approved training dataset (documented, reproducible command in the module's own comments) - never recomputed from the live claim being scored, which would leak that claim into its own normalization reference.

## 5. Evidence requirements / input availability

Every run first counts the claim's actual current data via existing CRUD (`documents`, `vehicle_damage`, `evidence`, `repair_estimates`, `surveyor_inspections`) and returns this as `evidence_summary` - real counts, never estimated. A brand-new claim (0 documents, 0 damage, 0 estimate, 0 inspection) genuinely has only 1 of the 7 signals available (`claim_pattern_anomaly`) - this was verified directly:

```json
{"available": false, "status": "insufficient_evidence", "overall_risk_score": null, ...}
```

Once a repair estimate is submitted (Step 5.8.7 workflow), `repair_estimate_anomaly` becomes available too (2/7). This is the realistic ceiling for today's live pipeline - see Section 11.

## 6. Persistence

**Nothing is written to PostgreSQL.** The task explicitly required persistence only if an existing schema/field is appropriate, and none is: this result doesn't correspond to any single existing row-shape (`fraud_risk_analysis`, `cross_document_consistency`, and `repair_estimates` each represent a different, narrower analysis than this claim-timing + repair-ratio combination), and creating a partial/placeholder-mixed row in any of those tables to hold it would misrepresent what that table means to every other reader (e.g. `POST .../ai-analysis` from Step 5.8.10, which treats a `fraud_risk_analysis` row's presence as "a real analysis exists"). The result is computed fresh on every call and returned directly - it is not cached, not stored, and disappears once the HTTP response is sent. Re-running the analysis is the only way to see it again.

## 7. Inference process (step by step)

1. Look up the claim (404 if it does not exist).
2. Look up its policy (for `Policy_Start_Date`) and count its documents/damage/evidence/repair-estimates/inspections.
3. Build all 7 signal entries: 2 genuinely computed, 5 explicitly unavailable with a specific reason.
4. Run the ported uncertainty formula on whichever signals are available.
5. If fewer than 2 signals are available, report `status: "insufficient_evidence"`, `available: false`, and suppress the overall score entirely (a score built from 0-1 signals would overstate what was analyzed).
6. Otherwise, run the ported fusion formula and report `status: "partial"` (the ceiling this pipeline can reach today - see Section 11) with the genuinely computed score/band/confidence.
7. Return the full structured result - never persisted (Section 6).

## 8. Confidence handling

No new confidence formula was invented. `_compute_uncertainty()` is the same `coverage x agreement x signal_trust` calculation as `ai_ml/risk_fusion/uncertainty.py`, using the same thresholds. Because at most 2 of 7 signal families are ever available, `coverage` is at most `2/7 ≈ 0.286` - the formula therefore almost always lands in `LOW_CONFIDENCE` or `INSUFFICIENT_EVIDENCE`, which is the methodology working correctly, not a bug (see Section 11).

## 9. Explainability

Each signal carries its own real, computed `explanation` string (e.g. the actual ratio and the actual reference percentiles it was compared against - `"Repair-estimate/claim-amount ratio 0.96 (reference median 0.84, 90th percentile 2.97)"`), matching the same style as the Step 5.4 signal explanations. Every unavailable signal's explanation states the specific, real reason it could not be computed rather than a generic "N/A". Per this task's Step 9, the `repair_estimate_anomaly` explanation explicitly discloses that `Excessive_Claim_Amount_Indicator` was excluded because it is always the Step 5.8.7 "not yet analyzed" placeholder (`False`), never treating that placeholder as a genuine prediction.

## 10. Human-in-the-loop

`ai_pipeline.py` imports no CRUD `create`/`update` function and never references `Claim.Final_Decision`, `Claim.Approved_Amount`, or `claim_decision_audit` - verified by a dedicated test (`test_ai_analysis_run_cannot_modify_final_decision_or_approved_amount`) that reads those fields before and after a run and asserts they are unchanged, with zero new audit rows. `POST /officer/claims/{claim_id}/decision` (Step 5.8.9) remains the only place a decision is persisted, completely independent of this endpoint. The frontend (`LiveRunPanel.jsx`) shows "AI-assisted analysis. Final claim decision remains with the Claims Officer." on every render and does not touch `DecisionPage.jsx`.

## 11. Failure handling

- **Nonexistent claim** -> 404, before any signal is computed.
- **Wrong role** (Customer/Surveyor) -> 403, via the same `require_roles("Claims Officer", "Admin")` dependency already used by every other officer endpoint - no custom authorization logic was written.
- **Unauthenticated** -> 401.
- **Insufficient live data** -> `status: "insufficient_evidence"`, `available: false`, no numeric score shown - not an HTTP error, since the claim itself is valid and the request succeeded; there is simply not enough to say anything reliable yet.
- **Frontend request failure** (network/500) -> `LiveRunPanel.jsx`'s `status: "error"` state shows the actual API error message.

## 12. Limitations

- Only 2 of the 7 Step 5.4 signal families can be computed live today; the other 5 require OCR, cross-document consistency, or duplicate-evidence detection capabilities that do not exist anywhere in this codebase (Section 3). This is disclosed in every response's own `limitations` array, not hidden.
- Given the above, the live pipeline's `status` can only ever reach `"insufficient_evidence"` or `"partial"` - `"completed"` (all 7 signals available) is not currently reachable and the code never claims it is.
- Confidence will realistically never exceed `LOW_CONFIDENCE` for the foreseeable future, because coverage is capped at `2/7`. This is an honest consequence of what can genuinely be computed, not a defect in the confidence formula.
- The trained fraud model, the full rule-based screener, and SHAP explainability are **not** part of this live pipeline (Section 3) - integrating them would require either a genuine document/evidence analysis pipeline (OCR, consistency-checking, duplicate-detection) to populate their real inputs, or accepting the training-serving skew this document explicitly documents as unacceptable.
- This remains a research-prototype methodology validated only on a synthetic/de-identified dataset (`AI_VS_NON_AI_RESULTS.md`) - no claim of production-grade accuracy, real insurer validation, or universal AI superiority is made anywhere in this endpoint's response, the frontend, or this document.

## 13. Future production work

To genuinely raise the live pipeline's coverage beyond 2/7 signals, in priority order: (1) build a real OCR/document-completeness pipeline that writes genuine, non-placeholder values to `Document.OCR_Confidence_Score`/`Document_Completeness`/`Extracted_Text`; (2) build a real cross-document consistency checker that compares actual submitted document text/fields and writes genuine values to `cross_document_consistency` (or a live-computed equivalent); (3) build genuine duplicate-evidence detection (e.g. perceptual image hashing) for `Evidence.Duplicate_Evidence_Indicator`. Only once those exist would running the trained fraud model or the full rule-based screener live stop being training-serving skew, since their required inputs would then reflect genuine analysis instead of universal placeholders.
