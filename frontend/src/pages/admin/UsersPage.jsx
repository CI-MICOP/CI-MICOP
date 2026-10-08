import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import Button from "../../components/common/Button";
import Card from "../../components/common/Card";
import DataTable from "../../components/common/DataTable";
import ErrorState from "../../components/common/ErrorState";
import PageHeader from "../../components/common/PageHeader";
import SearchInput from "../../components/common/SearchInput";
import StatusBadge from "../../components/common/StatusBadge";
import { useFetch } from "../../hooks/useFetch";
import { listAllUsers } from "../../services/adminService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatDate } from "../../utils/format";
import { getStatusTone } from "../../utils/statusTone";

const PAGE_SIZE = 25;
const ALL_ROLES = "All roles";

/** Read-only list of every account. The backend has no endpoint to
 * create, edit or disable a user, so this page offers none. */
export default function UsersPage() {
  const [search, setSearch] = useState("");
  const [role, setRole] = useState(ALL_ROLES);
  const [page, setPage] = useState(0);

  const { data: users, isLoading, error, reload } = useFetch(listAllUsers, []);

  const roles = useMemo(() => [...new Set((users ?? []).map((u) => u.Role))].sort(), [users]);

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return (users ?? []).filter(
      (u) =>
        (role === ALL_ROLES || u.Role === role) &&
        (!term ||
          [u.Username, u.User_ID, u.Email, u.Customer_ID, u.Employee_ID].some((value) =>
            (value ?? "").toLowerCase().includes(term)
          ))
    );
  }, [users, search, role]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount - 1);
  const visible = filtered.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE);

  return (
    <div>
      <PageHeader title="Users" subtitle="Every account in the system. Read-only." />

      {error ? (
        <ErrorState message={getApiErrorMessage(error)} onRetry={reload} />
      ) : (
        <Card>
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
            <SearchInput
              value={search}
              onChange={(value) => {
                setSearch(value);
                setPage(0);
              }}
              placeholder="Search username / user ID / email / customer or employee ID"
              className="sm:w-96"
            />
            <label>
              <span className="sr-only">Role</span>
              <select
                className="input"
                value={role}
                onChange={(event) => {
                  setRole(event.target.value);
                  setPage(0);
                }}
              >
                <option>{ALL_ROLES}</option>
                {roles.map((r) => (
                  <option key={r}>{r}</option>
                ))}
              </select>
            </label>
          </div>

          <DataTable
            isLoading={isLoading}
            rows={visible}
            rowKey="User_ID"
            emptyMessage={users?.length ? "No users match your search." : "No users found."}
            columns={[
              { key: "username", header: "Username", render: (u) => u.Username },
              { key: "role", header: "Role", render: (u) => u.Role },
              { key: "linked", header: "Customer / Employee ID", render: (u) => u.Customer_ID || u.Employee_ID || "-" },
              { key: "email", header: "Email", render: (u) => u.Email },
              {
                key: "status",
                header: "Account Status",
                render: (u) => <StatusBadge label={u.Account_Status} tone={getStatusTone(u.Account_Status)} />,
              },
              { key: "lastLogin", header: "Last Login", render: (u) => formatDate(u.Last_Login) },
              {
                key: "action",
                header: "Action",
                render: (u) => (
                  <Link to={`/admin/users/${u.User_ID}`} className="font-medium text-brand-600 hover:text-brand-700">
                    View Details
                  </Link>
                ),
              },
            ]}
          />

          {!isLoading && filtered.length > 0 && (
            <div className="mt-4 flex items-center justify-between text-sm text-muted">
              <span>
                Showing {currentPage * PAGE_SIZE + 1}-{currentPage * PAGE_SIZE + visible.length} of {filtered.length}
              </span>
              <span className="flex items-center gap-2">
                <Button variant="secondary" onClick={() => setPage(currentPage - 1)} disabled={currentPage === 0}>
                  Previous
                </Button>
                <Button variant="secondary" onClick={() => setPage(currentPage + 1)} disabled={currentPage >= pageCount - 1}>
                  Next
                </Button>
              </span>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
