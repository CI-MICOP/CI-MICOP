// This project's Claim_Status vocabulary (mirrors backend/app/services/
// claim_status.py). The decision workflow (services/claim_decision.py)
// sets Claim_Status itself: a claim starts "Under Review" and moves to
// "Completed" once an officer records any final decision - Approved,
// Rejected, or Partially Approved alike. Claim_Status tracks lifecycle
// stage only; the differentiated outcome lives in Final_Decision, which is
// why Queue/All-Claims membership is Claim_Status alone.
export const UNDER_REVIEW_STATUS = "Under Review";
export const COMPLETED_STATUS = "Completed";

export function isAwaitingReview(claim) {
  return claim.Claim_Status === UNDER_REVIEW_STATUS;
}

export function isCompleted(claim) {
  return claim.Claim_Status === COMPLETED_STATUS;
}
