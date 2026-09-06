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
