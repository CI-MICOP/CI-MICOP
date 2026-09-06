import { apiClient } from "./apiClient";

// Backend expects OAuth2 form-encoded fields (see
// backend/app/api/v1/routers/auth.py), not JSON.
export async function login(username, password) {
  const body = new URLSearchParams({ username, password });
  const response = await apiClient.post("/auth/login", body, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return response.data; // { access_token, token_type }
}

export async function getCurrentUser() {
  const response = await apiClient.get("/auth/me");
  return response.data;
}
