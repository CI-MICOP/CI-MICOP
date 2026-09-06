import axios from "axios";

import { clearToken, getToken } from "../utils/storage";

// Never hard-code the backend URL - it always comes from the environment
// (see frontend/.env.example: VITE_API_BASE_URL).
const baseURL = import.meta.env.VITE_API_BASE_URL;

export const apiClient = axios.create({ baseURL });

apiClient.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// AuthContext registers a callback here so a 401 from any request (not
// just the initial /auth/me check) also clears its in-memory user state.
// Without this, clearing localStorage alone would leave isAuthenticated
// true until the next full reload.
let onUnauthorized = null;

export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler;
}

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token missing/expired/invalid - drop it and notify AuthContext so
      // route guards redirect to /login on the next render.
      clearToken();
      onUnauthorized?.();
    }
    return Promise.reject(error);
  }
);
