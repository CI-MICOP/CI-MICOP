// Maps each backend Role value (see backend/app/db_models/authentication_user.py)
// to its frontend route namespace. Centralized so routing, navigation
// config, and post-login redirects never drift apart.

export const ROLE_HOME_PATH = {
  Customer: "/customer",
  Surveyor: "/surveyor",
  "Claims Officer": "/officer",
  Admin: "/admin",
};

export function getRoleHomePath(role) {
  return ROLE_HOME_PATH[role] ?? "/login";
}
