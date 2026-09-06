import { apiClient } from "./apiClient";

export async function listClaimsForProcessing(params = {}) {
  const response = await apiClient.get("/officer/claims", { params });
  return response.data;
}

export async function getClaimProcessingDetail(claimId) {
  const response = await apiClient.get(`/officer/claims/${claimId}`);
  return response.data;
}
