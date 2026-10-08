// Small counting helpers shared by the admin pages. They only count what
// the API returned - nothing here estimates or fills in missing values.

/** [[value, count], ...] sorted by count, largest first. */
export function countBy(rows, getValue) {
  const counts = new Map();
  (rows ?? []).forEach((row) => {
    const value = getValue(row) || "Not set";
    counts.set(value, (counts.get(value) ?? 0) + 1);
  });
  return [...counts.entries()].sort((a, b) => b[1] - a[1]);
}

/** The project's four roles, in the order the admin pages list them. */
export const ROLE_ORDER = ["Customer", "Surveyor", "Claims Officer", "Admin"];

export function countUsersByRole(users) {
  const counts = new Map(countBy(users, (user) => user.Role));
  const known = ROLE_ORDER.map((role) => [role, counts.get(role) ?? 0]);
  const other = [...counts.entries()].filter(([role]) => !ROLE_ORDER.includes(role));
  return [...known, ...other];
}
