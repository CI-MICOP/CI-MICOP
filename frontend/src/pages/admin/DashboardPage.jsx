import { LayoutDashboard } from "lucide-react";

import EmptyState from "../../components/common/EmptyState";
import PageHeader from "../../components/common/PageHeader";
import { useAuth } from "../../hooks/useAuth";

/** Placeholder only - the real admin dashboard (users, system reports)
 * is built in a later Step 4 sub-step. */
export default function AdminDashboardPage() {
  const { user } = useAuth();

  return (
    <div>
      <PageHeader
        title="Dashboard"
        subtitle={`Welcome, ${user?.Username ?? "admin"}`}
      />
      <EmptyState
        icon={LayoutDashboard}
        title="Admin dashboard coming soon"
        message="This will show system-wide reports and user administration once implemented."
      />
    </div>
  );
}
