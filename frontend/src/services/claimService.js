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

// Customer_ID is never sent here - the backend always derives it from the
// authenticated JWT (see backend/app/services/claim_creation.py).
export async function createClaim(payload) {
  const response = await apiClient.post("/claims", payload);
  return response.data;
}
