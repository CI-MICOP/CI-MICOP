import { apiClient } from "./apiClient";

export async function listUsers(params = {}) {
  const response = await apiClient.get("/admin/users", { params });
  return response.data;
}

const USERS_PAGE_SIZE = 500; // the largest page GET /admin/users allows

/** Every user account. The endpoint returns no total count, so pages are
 * requested until one comes back short. */
export async function listAllUsers() {
  const users = [];
  for (;;) {
    const page = await listUsers({ skip: users.length, limit: USERS_PAGE_SIZE });
    users.push(...page);
    if (page.length < USERS_PAGE_SIZE) return users;
  }
}

export async function getUserById(userId) {
  const response = await apiClient.get(`/admin/users/${userId}`);
  return response.data;
}
