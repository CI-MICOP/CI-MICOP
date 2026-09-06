// Single source of truth for where the JWT is persisted, so apiClient
// and AuthContext never disagree on the storage key.

const TOKEN_KEY = "ci_micop_access_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}
