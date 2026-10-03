import { apiClient } from "./apiClient";
import { getCustomerById } from "./customerService";
import { getPolicyById } from "./policyService";
import { getVehicleById } from "./vehicleService";

export async function listClaimsForProcessing(params = {}) {
  const response = await apiClient.get("/officer/claims", { params });
  return response.data;
}

export async function getClaimProcessingDetail(claimId) {
  const response = await apiClient.get(`/officer/claims/${claimId}`);
  return response.data;
}

// Live AI/ML -> FastAPI -> React integration (Step 5.8.10). Read-only:
// this call cannot create, update, or influence Claim.Final_Decision -
// see services/claim_decision.py, which remains the only decision
// write path.
export async function getAiAnalysis(claimId) {
  const response = await apiClient.get(`/officer/claims/${claimId}/ai-analysis`);
  return response.data;
}

// On-demand live analysis of this claim's actual current data (Step
// 5.8.11). Analyze-only, not persisted server-side - see
// services/ai_pipeline.py, which cannot touch Claim.Final_Decision or
// Approved_Amount.
export async function runAiAnalysis(claimId) {
  const response = await apiClient.post(`/officer/claims/${claimId}/ai-analysis/run`);
  return response.data;
}

// OCRs every document on this claim and persists only each document's own
// analysis fields (Extracted_Text, OCR_Confidence_Score,
// Document_Completeness) - Step 5.8.12. Never touches Final_Decision,
// Approved_Amount, or claim_decision_audit.
export async function analyzeClaimDocuments(claimId) {
  const response = await apiClient.post(`/officer/claims/${claimId}/documents/analyze`);
  return response.data;
}

// Read-only (Step 5.8.13-B/C): returns the deterministic registration/policy
// result and the FIR <-> Survey Report narrative result as two SEPARATE
// fields - see services/semantic_consistency.py. Reads already-extracted
// text only; never re-runs OCR and never writes to the database.
export async function checkClaimConsistency(claimId) {
  const response = await apiClient.post(`/officer/claims/${claimId}/documents/semantic-consistency`);
  return response.data;
}

// Read-only (Step 5.8.14): compares each evidence photo on this claim with
// every other stored evidence photo (this claim and other claims) by
// SHA-256 and a 64-bit difference hash - see
// services/evidence_duplication.py. Never writes to the database.
export async function checkEvidenceDuplication(claimId) {
  const response = await apiClient.post(`/officer/claims/${claimId}/evidence/duplication-check`);
  return response.data;
}

// Read-only (Step 5.8.15): measures each evidence photo on this claim for
// resolution, brightness, contrast and blur, returning plain flags - see
// services/evidence_quality.py. Never writes to the database.
export async function checkPhotoQuality(claimId) {
  const response = await apiClient.post(`/officer/claims/${claimId}/evidence/quality-check`);
  return response.data;
}

export async function getSurveyors() {
  const response = await apiClient.get("/officer/surveyors");
  return response.data;
}

// Surveyor_ID/Claim_ID are never sent as free-form identifiers beyond the
// URL path and the selected surveyor's Employee_ID - the backend always
// re-derives and validates both from authoritative records.
export async function assignSurveyor(claimId, surveyorEmployeeId) {
  const response = await apiClient.post(`/officer/claims/${claimId}/assign-surveyor`, {
    surveyor_employee_id: surveyorEmployeeId,
  });
  return response.data;
}

// Only the officer's own human-entered fields are sent - AI_Recommendation/
// AI_Confidence_Score/Claims_Officer_ID are never accepted from the
// frontend, the backend derives/carries them forward server-side only.
export async function submitDecision(claimId, { finalDecision, decisionReason, approvedAmount, officerComments }) {
  const response = await apiClient.post(`/officer/claims/${claimId}/decision`, {
    Final_Decision: finalDecision,
    Decision_Reason: decisionReason,
    Approved_Amount: approvedAmount,
    Officer_Comments: officerComments,
  });
  return response.data;
}

// Claims Officer/Admin are authorized to read full customer, vehicle, and
// policy records (unlike Surveyor, who is explicitly blocked) - this
// composes the claim-processing aggregate with those three lookups for
// the Claim Details workspace and its tabs.
export async function getClaimWorkspaceData(claimId) {
  const detail = await getClaimProcessingDetail(claimId);
  const { claim } = detail;
  const [customer, vehicle, policy] = await Promise.all([
    getCustomerById(claim.Customer_ID).catch(() => null),
    getVehicleById(claim.Vehicle_ID).catch(() => null),
    getPolicyById(claim.Policy_ID).catch(() => null),
  ]);
  return { ...detail, customer, vehicle, policy };
}
