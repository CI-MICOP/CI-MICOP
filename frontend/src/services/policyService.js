import { apiClient } from "./apiClient";

export async function getMyPolicies() {
  const response = await apiClient.get("/policies/me");
  return response.data;
}

export async function getPolicyById(policyId) {
  const response = await apiClient.get(`/policies/${policyId}`);
  return response.data;
}
