# AI Officer Integration (Step 5.5)

**The current implementation is a research prototype using synthetic/de-identified data and should not be interpreted as a production insurance decision system.**

---

## 1. Purpose

Step 5.4 built a transparent, multi-signal risk-fusion research prototype (`ai_ml/risk_fusion/`) with an explicit finding: fusing several weak signals did not meaningfully outperform the single fraud-screening signal (PR-AUC 0.167 vs. 0.156, well within one standard deviation - see `RISK_FUSION_AND_UNCERTAINTY.md`). Step 5.5 does not change that methodology or attempt to improve it. Its purpose is narrower: **demonstrate how CI-MICOP would present this kind of AI-assisted analysis to a Claims Officer**, using the existing Claims Officer portal and design system, as a read-only prototype surface.

## 2. Data flow

```
ai_ml/experiments/run_risk_fusion_experiment.py   (Step 5.4, unmodified)
        │  produces
        ▼
ai_ml/model_artifacts/risk_fusion/full_dataset_risk_fusion_scores.csv   (654 claims: score/band/confidence/priority/reason codes)
ai_ml/model_artifacts/risk_fusion_explanations/*.json                   (4 fully-detailed representative examples)
        │  exported once, by hand, into a bundled frontend asset
        ▼
frontend/src/data/aiRiskFusionDemo.json
        │  read by
        ▼
frontend/src/services/aiRiskService.js
        │  used by
        ▼
frontend/src/components/officer/ai/*   (AIInsightCard and its sub-components)
        │  rendered on
        ▼
frontend/src/pages/officer/AiInsightsPage.jsx  +  a small summary card on
frontend/src/pages/officer/DashboardPage.jsx
```

There is **no new backend endpoint or database table**. The 15-table schema is unchanged. No filesystem path is exposed to the browser: the JSON asset is a normal bundled frontend file, produced once from Step 5.4's real output and committed like any other source file - the browser never reads from `ai_ml/` at runtime.

## 3. How Step 5.4 connects to the officer UI

`aiRiskService.getAiInsightsForClaim(claimId)` looks up the officer's currently open claim (`claim.Claim_ID`, e.g. `"CLM-000007"`) in the bundled export. Because the Postgres `claims` table and the `ai_ml` dataset are both seeded from the same underlying `CI_MICOP_15_Tables_Complete` export, every one of the 654 claims in the database has a real Step 5.4 summary (risk score, risk band, confidence, confidence band, review priority, reason codes). A small subset of claims - the four representative examples Step 5.4 generated a full per-signal breakdown for - additionally show the complete signal-by-signal explanation. If a `Claim_ID` has no Step 5.4 result at all (e.g. data added after the Step 5.4 export), the UI shows an explicit "No AI risk assessment available" state - never a fabricated one.

## 4. Risk score

`RiskScoreCard.jsx` shows `overallRiskScore` scaled to a 0-100 display value and its risk band (LOW/MEDIUM/HIGH/CRITICAL), captioned "Risk indicates the strength of available warning signals" and explicitly labeled a prototype research score - never presented as a validated insurance risk threshold (per `ai_ml/risk_fusion/fusion_engine.py`'s own "prototype research thresholds" labeling, unchanged from Step 5.4).

## 5. Confidence

`ConfidenceCard.jsx` is a **separate** card from the risk score - not a shared meter, not a derived sub-value. It shows `confidenceScore` (0-100) and confidence band (HIGH/MEDIUM/LOW/INSUFFICIENT EVIDENCE), captioned "Confidence indicates how reliable and complete the available evidence and signals are - it is not a measure of risk." This physical separation is deliberate: Step 5.4's central research contribution is that risk and confidence are independent axes, and collapsing them into one indicator would erase that finding in the UI.

## 6. Uncertainty

`ConfidenceCard.jsx` also lists the specific `uncertaintyReasons` Step 5.4 computed for a representative example claim (e.g. "signals disagree with each other", "includes a model/rule-screening-derived signal ... performs only marginally above chance"). For claims with only summary-level data (no full breakdown), this list is empty rather than invented.

## 7. Signal explanations

`SignalBreakdown.jsx` renders each of the 7 Step 5.4 signals (see `ai_ml/risk_fusion/signal_schema.py`) using a human-readable label (`frontend/src/utils/aiSignalLabels.js` maps `repair_estimate_anomaly` → "Repair Estimate", never showing an internal name or a raw feature value) and its plain-language `explanation` string exactly as Step 5.4 generated it. This is only available for the four representative example claims - for every other claim, the component shows an explicit "full signal breakdown not generated for this claim" message pointing the officer to the demonstration examples, rather than fabricating a breakdown.

## 8. Reason codes

`ReasonCodeList.jsx` renders the Step 5.4 reason codes (`ai_ml/risk_fusion/reason_codes.py`, unchanged) using officer-facing wording where available ("AI risk signal: repair estimate anomaly detected") and falls back to the bare code as a badge otherwise. No code or wording anywhere claims "fraud confirmed" or "fraud detected with certainty" (enforced by dedicated frontend tests, mirroring the equivalent Step 5.4 backend test).

## 9. Review priority

The `AIInsightCard` shows the Step 5.4 `reviewPriority` (URGENT_REVIEW/HIGH_REVIEW/STANDARD_REVIEW/LOW_REVIEW) with a short officer-facing message (`frontend/src/utils/aiReviewPriority.js`) - e.g. a HIGH_REVIEW claim with unreliable confidence explicitly says "High risk with low confidence — human investigation recommended before any decision." This is presented as a prototype research prioritization mechanism, never a decision.

## 10. Human-in-the-loop principle

Every AI Insights view shows `HumanReviewNotice.jsx` at least once (top and bottom of the panel), with one of three fixed messages depending on the claim's risk/confidence combination: the default disclaimer, the high-risk/low-confidence warning, or the insufficient-evidence warning. `humanReviewRequired` is always displayed as YES. No wording anywhere says "automatically rejected" or "claim should be rejected" (tested).

## 11. Why AI does not make the final decision

`AIInsightCard` and every component under `frontend/src/components/officer/ai/` are **read-only**: they contain zero buttons, zero form controls, and call no write endpoint (verified by a dedicated test asserting the rendered tree contains no `button` elements). The existing "Make Decision" tab (`DecisionPage.jsx`) is completely unmodified and remains the only place a Claims Officer records a decision - it was already, and remains, disconnected from any AI output and from any backend write endpoint (the CI-MICOP API has none). AI Insights and the officer's decision are two separate tabs reached via the existing `ClaimTabs` navigation, never merged into one flow.

## 12. Synthetic dataset limitation

All risk scores, confidence values, and reason codes shown come from Step 5.1-5.4's synthetic/de-identified 654-claim dataset. Step 5.2/5.3 found the underlying predictive signal is weak-to-chance-level for every target tested; Step 5.4 found multi-signal fusion did not meaningfully improve on the single strongest signal. Nothing in this UI should be read as evidence the system can accurately detect fraud.

## 13. Prototype/demo limitations

- Only 4 of the 654 claims have a full per-signal breakdown; the rest show summary-level risk/confidence/reason-code data only.
- The data source is a static, one-time export of Step 5.4's output, not a live-refreshing feed - if `ai_ml/experiments/run_risk_fusion_experiment.py` is re-run with different results, `frontend/src/data/aiRiskFusionDemo.json` would need to be regenerated and re-bundled by hand; there is no automatic sync.
- The fifth demonstration category Step 5.4 specified ("insufficient evidence") is intentionally absent from the UI's example selector: Step 5.4 found no claim in the current dataset that genuinely has too little evidence to assess (every claim has complete document/evidence records), and that gap is preserved here rather than papered over with a fabricated example.
- The dashboard's "AI Risk Insights Summary" card shows real counts computed from the same export (e.g. claims flagged HIGH_REVIEW/URGENT_REVIEW, claims with low confidence) - it does not reflect live claim intake.

## 14. Future real-data integration

If CI-MICOP obtains governed, real (de-identified) insurer claims data in the future (see `RISK_FUSION_AND_UNCERTAINTY.md`, Section 19), this integration point is where a genuine backend AI endpoint would eventually replace the static JSON: `aiRiskService.js`'s function signatures (`getAiInsightsForClaim`, `listDemonstrationExamples`, `getAiSummaryStats`) were kept deliberately narrow so that swapping the static import for a real `apiClient.get("/officer/ai-insights/:claimId")` call would not require changing any component. That backend endpoint does not exist today and was explicitly out of scope for this step.
