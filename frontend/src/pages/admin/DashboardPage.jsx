import { BarChart3, FileText, History, KeyRound, UserCheck, UserX, Users } from "lucide-react";
import { useCallback } from "react";

import CountBars from "../../components/admin/CountBars";
import ErrorState from "../../components/common/ErrorState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import QuickActionCard from "../../components/common/QuickActionCard";
import StatCard from "../../components/common/StatCard";
import { useAuth } from "../../hooks/useAuth";
import { useFetch } from "../../hooks/useFetch";
import { listAllUsers } from "../../services/adminService";
import { listClaimsForProcessing } from "../../services/officerService";
import { countBy, countUsersByRole } from "../../utils/adminStats";
import { getApiErrorMessage } from "../../utils/errors";

/** System overview for Admin. Every figure is counted from the user and
 * claim lists the API returns - read-only, nothing is estimated. */
export default function AdminDashboardPage() {
  const { user } = useAuth();

  const fetchOverview = useCallback(async () => {
    const [users, claims] = await Promise.all([listAllUsers(), listClaimsForProcessing({ limit: 200 })]);
    return { users, claims };
  }, []);
  const { data, isLoading, error, reload } = useFetch(fetchOverview, [fetchOverview]);

  const title = `Welcome, ${user?.Username ?? "admin"}`;
  const subtitle = "System overview.";

  if (isLoading) {
    return (
      <div>
        <PageHeader title={title} subtitle={subtitle} />
        <LoadingState label="Loading system overview..." />
      </div>
    );
  }
  if (error) {
    return (
      <div>
        <PageHeader title={title} subtitle={subtitle} />
        <ErrorState message={getApiErrorMessage(error)} onRetry={reload} />
      </div>
    );
  }

  const { users, claims } = data;
  const activeUsers = users.filter((u) => u.Account_Status === "Active").length;

  return (
    <div>
      <PageHeader title={title} subtitle={subtitle} />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="User Accounts" value={users.length} icon={Users} actionLabel="View users" to="/admin/users" />
        <StatCard label="Active Accounts" value={activeUsers} icon={UserCheck} />
        <StatCard label="Not Active" value={users.length - activeUsers} icon={UserX} />
        <StatCard
          label="Claims"
          value={claims.length}
          icon={FileText}
          trend={claims.length === 200 ? "Most recent 200 (API limit)" : undefined}
          actionLabel="View reports"
          to="/admin/system-reports"
        />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <CountBars title="Users by Role" rows={countUsersByRole(users)} emptyMessage="No user accounts." />
        <CountBars title="Claims by Status" rows={countBy(claims, (c) => c.Claim_Status)} emptyMessage="No claims." />
      </div>

      <h2 className="mb-3 mt-8 text-sm font-semibold text-ink">Quick Actions</h2>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <QuickActionCard label="Users" description="Browse every account" icon={Users} to="/admin/users" />
        <QuickActionCard label="Roles & Permissions" description="What each role can do" icon={KeyRound} to="/admin/roles-permissions" />
        <QuickActionCard label="System Reports" description="Users and claims in numbers" icon={BarChart3} to="/admin/system-reports" />
        <QuickActionCard label="Audit Logs" description="Decision trail per claim" icon={History} to="/admin/audit-logs" />
      </div>
    </div>
  );
}
