import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "../hooks/useAuth";
import { getRoleHomePath } from "../utils/roles";

/**
 * Requires the current user's role to be one of `allowedRoles`.
 * A logged-in user of the wrong role is sent to their own dashboard,
 * never to another role's pages.
 */
export default function RoleProtectedRoute({ allowedRoles }) {
  const { role } = useAuth();

  if (!allowedRoles.includes(role)) {
    return <Navigate to={getRoleHomePath(role)} replace />;
  }

  return <Outlet />;
}
