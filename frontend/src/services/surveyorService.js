import { apiClient } from "./apiClient";

export async function getMyInspections() {
  const response = await apiClient.get("/surveyor/inspections");
  return response.data;
}

export async function getAssignedClaimDetail(claimId) {
  const response = await apiClient.get(`/surveyor/claims/${claimId}`);
  return response.data;
}

export async function updateInspection(inspectionId, data) {
  const response = await apiClient.patch(`/surveyor/inspections/${inspectionId}`, data);
  return response.data;
}

// Surveyor_ID is never sent - the backend always derives it from the JWT.
export async function startInspection(claimId) {
  const response = await apiClient.post("/surveyor/inspections", { Claim_ID: claimId });
  return response.data;
}

// Vehicle_ID is never sent - the backend derives it from the claim itself.
export async function createVehicleDamage(payload) {
  const response = await apiClient.post("/surveyor/vehicle-damage", payload);
  return response.data;
}

// Vehicle_ID is never sent - the backend derives it from the claim itself.
export async function createRepairEstimate(payload) {
  const response = await apiClient.post("/surveyor/repair-estimates", payload);
  return response.data;
}

// multipart/form-data - Content-Type (with its boundary) is left for
// Axios/the browser to set automatically; never set it manually here.
export async function createEvidence(claimId, { evidenceType, evidenceDate, evidenceSource, file }) {
  const formData = new FormData();
  formData.append("claim_id", claimId);
  formData.append("evidence_type", evidenceType);
  formData.append("evidence_date", evidenceDate);
  formData.append("evidence_source", evidenceSource);
  formData.append("file", file);
  const response = await apiClient.post("/surveyor/evidence", formData);
  return response.data;
}
