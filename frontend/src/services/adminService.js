import { apiClient } from "./apiClient";

export async function listUsers(params = {}) {
  const response = await apiClient.get("/admin/users", { params });
  return response.data;
}

export async function getUserById(userId) {
  const response = await apiClient.get(`/admin/users/${userId}`);
  return response.data;
}
