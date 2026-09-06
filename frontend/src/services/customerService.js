import { apiClient } from "./apiClient";

export async function getMyProfile() {
  const response = await apiClient.get("/customers/me");
  return response.data;
}

export async function getCustomerById(customerId) {
  const response = await apiClient.get(`/customers/${customerId}`);
  return response.data;
}
