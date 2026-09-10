// Officer-facing copy for each Step 5.4 review-priority band
// (ai_ml/risk_fusion/review_priority.py). This module NEVER recommends
// approving or rejecting a claim - only how urgently a human should look
// at it.

export const REVIEW_PRIORITY_TONE = {
  URGENT_REVIEW: "danger",
  HIGH_REVIEW: "warning",
  STANDARD_REVIEW: "info",
  LOW_REVIEW: "success",
};

export const REVIEW_PRIORITY_LABEL = {
  URGENT_REVIEW: "URGENT REVIEW",
  HIGH_REVIEW: "HIGH REVIEW",
  STANDARD_REVIEW: "STANDARD REVIEW",
  LOW_REVIEW: "LOW REVIEW",
};

const UNRELIABLE_CONFIDENCE = new Set(["LOW_CONFIDENCE", "INSUFFICIENT_EVIDENCE"]);

export function reviewPriorityMessage(reviewPriority, confidenceBand) {
  if (reviewPriority === "URGENT_REVIEW") {
    return "Multiple strong risk signals require immediate investigation.";
  }
  if (reviewPriority === "HIGH_REVIEW") {
    if (UNRELIABLE_CONFIDENCE.has(confidenceBand)) {
      return "High risk with low confidence — human investigation recommended before any decision.";
    }
    return "Multiple risk signals require additional investigation.";
  }
  if (reviewPriority === "STANDARD_REVIEW") {
    return "Evidence is mixed or moderate — review in the normal queue.";
  }
  if (reviewPriority === "LOW_REVIEW") {
    return "Low risk with reliable evidence — standard processing.";
  }
  return "This is a prototype research prioritization, not an automated decision.";
}
