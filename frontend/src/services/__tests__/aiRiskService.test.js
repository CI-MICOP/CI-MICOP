import { describe, expect, it } from "vitest";

import {
  getAiInsightsForClaim,
  getAiSummaryStats,
  isKnownDemonstrationExampleClaim,
  listDemonstrationExamples,
} from "../aiRiskService";

describe("aiRiskService", () => {
  it("returns null for a claim ID that has no Step 5.4 result (invalid/missing handling)", () => {
    expect(getAiInsightsForClaim("CLM-DOES-NOT-EXIST")).toBeNull();
  });

  it("returns a real, non-fabricated insight for a known claim", () => {
    const examples = listDemonstrationExamples();
    expect(examples.length).toBeGreaterThan(0);
    const insight = getAiInsightsForClaim(examples[0].claimId);
    expect(insight).not.toBeNull();
    expect(insight.claimId).toBe(examples[0].claimId);
    expect(insight.overallRiskScore).toBeGreaterThanOrEqual(0);
    expect(insight.overallRiskScore).toBeLessThanOrEqual(1);
  });

  it("exposes risk and confidence as independent fields, never derived from one another", () => {
    const examples = listDemonstrationExamples();
    const highRiskLowConfidence = examples.find((e) => e.key === "high_risk_low_confidence");
    expect(highRiskLowConfidence).toBeDefined();
    const insight = getAiInsightsForClaim(highRiskLowConfidence.claimId);
    expect(["HIGH", "CRITICAL"]).toContain(insight.riskBand);
    expect(["LOW_CONFIDENCE", "INSUFFICIENT_EVIDENCE"]).toContain(insight.confidenceBand);
  });

  it("only lists demonstration examples Step 5.4 actually generated, never a fabricated insufficient-evidence example", () => {
    const examples = listDemonstrationExamples();
    expect(examples.map((e) => e.key)).not.toContain("insufficient_evidence");
    expect(examples.length).toBe(4);
  });

  it("full signal breakdown is only present for known demonstration example claims", () => {
    const examples = listDemonstrationExamples();
    const exampleInsight = getAiInsightsForClaim(examples[0].claimId);
    expect(exampleInsight.hasFullSignalBreakdown).toBe(true);
    expect(Array.isArray(exampleInsight.signals)).toBe(true);
    expect(exampleInsight.signals.length).toBeGreaterThan(0);

    expect(isKnownDemonstrationExampleClaim("CLM-DOES-NOT-EXIST")).toBe(false);
  });

  it("computes dashboard summary stats without fabricating a count", () => {
    const stats = getAiSummaryStats();
    expect(stats.totalClaimsAssessed).toBeGreaterThan(0);
    expect(stats.highReviewPriority).toBeGreaterThanOrEqual(0);
    expect(stats.insufficientEvidence).toBeGreaterThanOrEqual(0);
  });
});
