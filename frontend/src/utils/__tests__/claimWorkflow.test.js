import { describe, expect, it } from "vitest";

import { isAwaitingReview, isCompleted } from "../claimWorkflow";

describe("claimWorkflow", () => {
  it("treats an Under Review claim as awaiting review, not completed", () => {
    const claim = { Claim_Status: "Under Review", Final_Decision: "Pending" };
    expect(isAwaitingReview(claim)).toBe(true);
    expect(isCompleted(claim)).toBe(false);
  });

  it("treats a Completed claim as completed, not awaiting review", () => {
    const claim = { Claim_Status: "Completed", Final_Decision: "Approved" };
    expect(isAwaitingReview(claim)).toBe(false);
    expect(isCompleted(claim)).toBe(true);
  });

  it("treats a rejected or partially approved claim as completed too, once the backend has finalized it", () => {
    for (const decision of ["Rejected", "Partially Approved"]) {
      const claim = { Claim_Status: "Completed", Final_Decision: decision };
      expect(isAwaitingReview(claim)).toBe(false);
      expect(isCompleted(claim)).toBe(true);
    }
  });

  it("excludes a claim from both buckets when its persisted status is neither value", () => {
    const claim = { Claim_Status: "Withdrawn", Final_Decision: "Pending" };
    expect(isAwaitingReview(claim)).toBe(false);
    expect(isCompleted(claim)).toBe(false);
  });

  it("never classifies the same claim as both awaiting review and completed", () => {
    const claims = [
      { Claim_Status: "Under Review", Final_Decision: "Pending" },
      { Claim_Status: "Completed", Final_Decision: "Approved" },
      { Claim_Status: "Under Review", Final_Decision: "Rejected" },
      { Claim_Status: "Withdrawn", Final_Decision: "Pending" },
    ];
    for (const claim of claims) {
      expect(isAwaitingReview(claim) && isCompleted(claim)).toBe(false);
    }
  });
});
