import { createContext, useCallback, useEffect, useMemo, useState } from "react";

import { setUnauthorizedHandler } from "../services/apiClient";
import * as authService from "../services/authService";
import { clearToken, getToken, setToken } from "../utils/storage";

export const AuthContext = createContext(undefined);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  // On first load, if a token is already stored, validate it against the
  // backend (GET /auth/me) rather than trusting it blindly.
  useEffect(() => {
    const token = getToken();
    if (!token) {
      setIsLoading(false);
      return;
    }

    authService
      .getCurrentUser()
      .then(setUser)
      .catch(() => {
        clearToken();
        setUser(null);
      })
      .finally(() => setIsLoading(false));
  }, []);

  // A 401 on any later request (expired/invalid token) must also clear
  // this in-memory state, not just localStorage, so route guards see
  // isAuthenticated flip to false and redirect to /login.
  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null));
    return () => setUnauthorizedHandler(null);
  }, []);

  const login = useCallback(async (username, password) => {
    const { access_token: accessToken } = await authService.login(username, password);
    setToken(accessToken);
    const currentUser = await authService.getCurrentUser();
    setUser(currentUser);
    return currentUser;
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({
      user,
      role: user?.Role ?? null,
      isAuthenticated: Boolean(user),
      isLoading,
      login,
      logout,
    }),
    [user, isLoading, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
