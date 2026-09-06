import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "../hooks/useAuth";
import { getRoleHomePath } from "../utils/roles";

/** For routes like /login: an already-authenticated user is redirected
 * straight to their dashboard instead of seeing the login form again. */
export default function PublicRoute() {
  const { isAuthenticated, role } = useAuth();

  if (isAuthenticated) {
    return <Navigate to={getRoleHomePath(role)} replace />;
  }

  return <Outlet />;
}
