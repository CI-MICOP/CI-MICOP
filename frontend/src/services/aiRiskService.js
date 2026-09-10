/**
 * Step 5.5 — AI Risk Insights demonstration service.
 *
 * CI-MICOP has no production AI/ML backend endpoint (see
 * docs/project_documentation/AI_OFFICER_INTEGRATION.md). Rather than
 * building a new backend feature for a research-prototype demo, this
 * service reads the ACTUAL output the Step 5.4 experiment produced
 * (`ai_ml/experiments/run_risk_fusion_experiment.py`), pre-exported once
 * into a static, version-controlled JSON asset bundled with the frontend
 * (`src/data/aiRiskFusionDemo.json`). No filesystem access happens in the
 * browser, no arbitrary path is ever exposed, and nothing here invents a
 * claim, a score, or a signal that Step 5.4 did not actually compute.
 *
 * Every one of the 654 claims in the current dataset has a real
 * (risk score / risk band / confidence / review priority / reason codes)
 * summary. A small subset of claims additionally has the FULL per-signal
 * breakdown, because Step 5.4 only generated deep explanations for its
 * five representative example categories (one of which - "insufficient
 * evidence" - Step 5.4 found no genuine example of in this dataset, and
 * that gap is preserved here rather than fabricated).
 */

import demoData from "../data/aiRiskFusionDemo.json";

const examplesByClaimId = new Map(demoData.examples.map((example) => [example.claim_id, example]));

export const AI_RISK_DATA_SOURCE = demoData.generatedBy;
export const AI_RISK_DISCLAIMER = demoData.disclaimer;
export const AI_RISK_CLAIM_COUNT = demoData.claimCount;

const RISK_BAND_TO_SCORE_100 = (score) => (score == null ? null : Math.round(score * 100));

/**
 * Returns a normalized AI insight object for one claim, or `null` if
 * Step 5.4 produced no result for this Claim_ID (e.g. a claim created
 * after the Step 5.4 export, or one outside the current dataset) - the
 * caller must render an explicit "not available" state, never a
 * fabricated one.
 */
export function getAiInsightsForClaim(claimId) {
  const summary = demoData.claims[claimId];
  if (!summary) return null;

  const example = examplesByClaimId.get(claimId) ?? null;

  return {
    claimId,
    overallRiskScore: summary.overallRiskScore,
    riskScoreOn100: RISK_BAND_TO_SCORE_100(summary.overallRiskScore),
    riskBand: summary.riskBand,
    confidenceScore: summary.confidenceScore,
    confidenceOn100: RISK_BAND_TO_SCORE_100(summary.confidenceScore),
    confidenceBand: summary.confidenceBand,
    uncertaintyReasons: example?.uncertainty_reasons ?? [],
    reviewPriority: summary.reviewPriority,
    humanReviewRequired: example?.human_review_required ?? true,
    evidenceCount: summary.evidenceCount,
    contributingSignalCount: summary.contributingSignalCount,
    unavailableSignalCount: summary.unavailableSignalCount,
    reasonCodes: summary.reasonCodes,
    officerExplanations: example?.officer_explanations ?? null,
    signals: example?.signals ?? null,
    contributingSignals: example?.contributing_signals ?? null,
    unavailableSignals: example?.unavailable_signals ?? null,
    hasFullSignalBreakdown: Boolean(example),
    plainLanguageExplanation:
      example?.explanation ??
      "These are AI risk signals for review prioritization, not a fraud determination. The Claims Officer makes the final decision.",
  };
}

/**
 * The demonstration-example categories Step 5.4 actually produced.
 * "Insufficient evidence" is intentionally absent - Step 5.4 found no
 * claim in the current dataset that genuinely qualifies (every claim has
 * complete document/evidence records), and that absence is itself a
 * reported finding, not a gap to paper over.
 */
export function listDemonstrationExamples() {
  return demoData.examples.map((example) => ({
    key: example.example_type,
    claimId: example.claim_id,
    label: EXAMPLE_LABELS[example.example_type] ?? example.example_type,
    riskBand: example.risk_band,
    confidenceBand: example.confidence_band,
  }));
}

const EXAMPLE_LABELS = {
  low_risk_high_confidence: "Low risk / high confidence",
  high_risk_high_confidence: "High risk / high confidence",
  high_risk_low_confidence: "High risk / low confidence",
  signal_disagreement: "Signal disagreement",
};

export function isKnownDemonstrationExampleClaim(claimId) {
  return examplesByClaimId.has(claimId);
}

/**
 * Aggregate, read-only counts for the officer dashboard (Step 5.5, Part
 * 10). Computed directly from the same Step 5.4 export every per-claim
 * insight uses - never a separately fabricated number.
 */
export function getAiSummaryStats() {
  const rows = Object.values(demoData.claims);
  return {
    totalClaimsAssessed: rows.length,
    highReviewPriority: rows.filter((r) => r.reviewPriority === "URGENT_REVIEW" || r.reviewPriority === "HIGH_REVIEW").length,
    lowConfidence: rows.filter((r) => r.confidenceBand === "LOW_CONFIDENCE" || r.confidenceBand === "INSUFFICIENT_EVIDENCE").length,
    multipleWarningSignals: rows.filter((r) => r.reasonCodes.length >= 3).length,
    insufficientEvidence: rows.filter((r) => r.confidenceBand === "INSUFFICIENT_EVIDENCE").length,
  };
}
