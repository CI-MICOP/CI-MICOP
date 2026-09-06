import { apiClient } from "./apiClient";

// GET /claims is role-scoped by the backend: a customer sees only their
// own claims, a surveyor sees only assigned claims, staff see all.
export async function listClaims(params = {}) {
  const response = await apiClient.get("/claims", { params });
  return response.data;
}

export async function getClaimById(claimId) {
  const response = await apiClient.get(`/claims/${claimId}`);
  return response.data;
}
