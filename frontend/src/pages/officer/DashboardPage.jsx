import { ArrowRight, Clock, FileText } from "lucide-react";
import { useCallback, useMemo } from "react";
import { Link } from "react-router-dom";

import Card from "../../components/common/Card";
import DataTable from "../../components/common/DataTable";
import ErrorState from "../../components/common/ErrorState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import StatCard from "../../components/common/StatCard";
import StatusBadge from "../../components/common/StatusBadge";
import { useAuth } from "../../hooks/useAuth";
import { useFetch } from "../../hooks/useFetch";
import { listClaimsForProcessing } from "../../services/officerService";
import { isAwaitingReview, isCompleted } from "../../utils/claimWorkflow";
import { getApiErrorMessage } from "../../utils/errors";
import { formatDate } from "../../utils/format";
import { getStatusTone } from "../../utils/statusTone";

const trackLinkClass = "mt-2 inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:text-brand-700";

export default function OfficerDashboardPage() {
  const { user } = useAuth();

  const fetchDashboard = useCallback(() => listClaimsForProcessing({ limit: 200 }), []);

  const { data, isLoading, error, reload } = useFetch(fetchDashboard, [fetchDashboard]);

  const workQueuePreview = useMemo(
    () =>
      (data ?? [])
        .filter(isAwaitingReview)
        .sort((a, b) => new Date(a.Claim_Date) - new Date(b.Claim_Date))
        .slice(0, 5),
    [data]
  );

  const underReviewCount = useMemo(() => (data ?? []).filter(isAwaitingReview).length, [data]);
  const completedCount = useMemo(() => (data ?? []).filter(isCompleted).length, [data]);

  if (isLoading) {
    return (
      <div>
        <PageHeader title={`Welcome, ${user?.Username ?? ""}`} subtitle="Claims processing command center." />
        <LoadingState label="Loading claims..." />
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <PageHeader title={`Welcome, ${user?.Username ?? ""}`} subtitle="Claims processing command center." />
        <ErrorState message={getApiErrorMessage(error)} onRetry={reload} />
      </div>
    );
  }

  return (
    <div>
      <PageHeader title={`Welcome, ${user?.Username ?? ""}`} subtitle="Claims processing command center." />

      <div className="grid grid-cols-2 gap-4">
        <StatCard
          label="Pending Claims"
          value={underReviewCount}
          icon={FileText}
          to="/officer/queue"
          actionLabel="View queue"
        />
        <StatCard label="Overdue Claims" value="N/A" icon={Clock} trend="SLA target not configured" />
      </div>

      <div className="mt-6">
        <Card>
          <h3 className="mb-4 text-sm font-semibold text-ink">Track Claims</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-muted">Under Review</p>
              <p className="mt-1 text-2xl font-semibold text-ink">{underReviewCount}</p>
              <Link to="/officer/queue" className={trackLinkClass}>
                View Queue
                <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
              </Link>
            </div>
            <div>
              <p className="text-sm text-muted">Completed</p>
              <p className="mt-1 text-2xl font-semibold text-ink">{completedCount}</p>
              <Link to="/officer/claims" className={trackLinkClass}>
                View Claims
                <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
              </Link>
            </div>
          </div>
        </Card>
      </div>

      <div className="mt-6">
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-ink">My Work Queue</h3>
            <Link to="/officer/queue" className="text-sm font-medium text-brand-600 hover:text-brand-700">
              View all
            </Link>
          </div>
          <DataTable
            rows={workQueuePreview}
            rowKey="Claim_ID"
            emptyMessage="No pending claims in the queue."
            columns={[
              { key: "number", header: "Claim", render: (c) => c.Claim_Number },
              { key: "customer", header: "Customer ID", render: (c) => c.Customer_ID },
              { key: "type", header: "Type", render: (c) => c.Claim_Type },
              { key: "date", header: "Date", render: (c) => formatDate(c.Claim_Date) },
              {
                key: "status",
                header: "Status",
                render: (c) => <StatusBadge label={c.Claim_Status} tone={getStatusTone(c.Claim_Status)} />,
              },
              {
                key: "action",
                header: "Action",
                render: (c) => (
                  <Link to={`/officer/claims/${c.Claim_ID}`} className="text-brand-600 hover:text-brand-700">
                    Review
                  </Link>
                ),
              },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
