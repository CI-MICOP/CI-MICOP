import { Navigate, Outlet, useLocation } from "react-router-dom";

import LoadingState from "../components/common/LoadingState";
import { useAuth } from "../hooks/useAuth";

/** Requires a logged-in user of any role; otherwise redirects to /login. */
export default function ProtectedRoute() {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <LoadingState label="Checking your session..." />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <Outlet />;
}
