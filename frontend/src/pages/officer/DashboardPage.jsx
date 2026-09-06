import { LayoutDashboard } from "lucide-react";

import EmptyState from "../../components/common/EmptyState";
import PageHeader from "../../components/common/PageHeader";
import { useAuth } from "../../hooks/useAuth";

/** Placeholder only - the real claims officer dashboard (work queue,
 * risk panels) is built in a later Step 4 sub-step. */
export default function OfficerDashboardPage() {
  const { user } = useAuth();

  return (
    <div>
      <PageHeader
        title="Dashboard"
        subtitle={`Welcome, ${user?.Username ?? "officer"}`}
      />
      <EmptyState
        icon={LayoutDashboard}
        title="Claims officer dashboard coming soon"
        message="This will show your work queue and claim processing tools once implemented."
      />
    </div>
  );
}
