import { ClipboardCheck, FileBarChart, ListChecks } from "lucide-react";
import { useCallback, useMemo } from "react";
import { Link } from "react-router-dom";

import Card from "../../components/common/Card";
import DataTable from "../../components/common/DataTable";
import EmptyState from "../../components/common/EmptyState";
import ErrorState from "../../components/common/ErrorState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import StatCard from "../../components/common/StatCard";
import StatusBadge from "../../components/common/StatusBadge";
import { useAuth } from "../../hooks/useAuth";
import { useFetch } from "../../hooks/useFetch";
import { listClaims } from "../../services/claimService";
import { getMyInspections } from "../../services/surveyorService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatDate } from "../../utils/format";
import { getStatusTone } from "../../utils/statusTone";

export default function SurveyorDashboardPage() {
  const { user } = useAuth();

  const fetchDashboard = useCallback(async () => {
    const [claims, inspections] = await Promise.all([listClaims({ limit: 200 }), getMyInspections()]);
    return { claims, inspections };
  }, []);

  const { data, isLoading, error, reload } = useFetch(fetchDashboard, [fetchDashboard]);

  const inspectionByClaim = useMemo(() => {
    const map = new Map();
    (data?.inspections ?? []).forEach((inspection) => map.set(inspection.Claim_ID, inspection));
    return map;
  }, [data]);

  const reportsSubmitted = useMemo(
    () => (data?.inspections ?? []).filter((i) => i.Survey_Report_Submitted).length,
    [data]
  );
  const reportsPending = (data?.inspections?.length ?? 0) - reportsSubmitted;

  const recentClaims = useMemo(
    () => [...(data?.claims ?? [])].sort((a, b) => new Date(b.Claim_Date) - new Date(a.Claim_Date)).slice(0, 5),
    [data]
  );

  const recentActivity = useMemo(() => {
    if (!data) return [];
    return [...data.inspections]
      .sort((a, b) => new Date(b.Inspection_Date) - new Date(a.Inspection_Date))
      .slice(0, 6)
      .map((i) => ({
        id: i.Inspection_ID,
        date: i.Inspection_Date,
        text: `Inspection ${i.Inspection_Status.toLowerCase()} for claim ${i.Claim_ID}${
          i.Survey_Report_Submitted ? " — report submitted" : ""
        }`,
      }));
  }, [data]);

  if (isLoading) {
    return (
      <div>
        <PageHeader title={`Welcome, ${user?.Username ?? ""}`} subtitle="Your assigned claims and inspection queue." />
        <LoadingState label="Loading your dashboard..." />
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <PageHeader title={`Welcome, ${user?.Username ?? ""}`} subtitle="Your assigned claims and inspection queue." />
        <ErrorState message={getApiErrorMessage(error)} onRetry={reload} />
      </div>
    );
  }

  return (
    <div>
      <PageHeader title={`Welcome, ${user?.Username ?? ""}`} subtitle="Your assigned claims and inspection queue." />

      <div className="space-y-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatCard label="Total Inspections" value={data.inspections.length} icon={ClipboardCheck} />
          <StatCard label="Reports Submitted" value={reportsSubmitted} icon={FileBarChart} />
          <StatCard label="Reports Pending" value={reportsPending} icon={ListChecks} />
        </div>

        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-ink">My Inspections</h3>
            <Link to="/surveyor/claims" className="text-sm font-medium text-brand-600 hover:text-brand-700">
              View all
            </Link>
          </div>
          <DataTable
            rows={recentClaims}
            rowKey="Claim_ID"
            emptyMessage="No inspections assigned yet."
            columns={[
              { key: "number", header: "Claim", render: (c) => c.Claim_Number },
              { key: "date", header: "Date", render: (c) => formatDate(c.Claim_Date) },
              { key: "type", header: "Type", render: (c) => c.Claim_Type },
              {
                key: "status",
                header: "Claim Status",
                render: (c) => <StatusBadge label={c.Claim_Status} tone={getStatusTone(c.Claim_Status)} />,
              },
              {
                key: "inspection",
                header: "Inspection Status",
                render: (c) => {
                  const inspection = inspectionByClaim.get(c.Claim_ID);
                  return inspection ? (
                    <StatusBadge label={inspection.Inspection_Status} tone={getStatusTone(inspection.Inspection_Status)} />
                  ) : (
                    <span className="text-muted">-</span>
                  );
                },
              },
              {
                key: "action",
                header: "Action",
                render: (c) => (
                  <Link to={`/surveyor/claims/${c.Claim_ID}`} className="text-brand-600 hover:text-brand-700">
                    View
                  </Link>
                ),
              },
            ]}
          />
        </Card>

        <Card>
          <h3 className="mb-4 text-sm font-semibold text-ink">Recent Activity</h3>
          {recentActivity.length === 0 ? (
            <EmptyState title="No recent activity" />
          ) : (
            <ul className="space-y-3">
              {recentActivity.map((event) => (
                <li key={event.id} className="text-sm">
                  <p className="text-ink">{event.text}</p>
                  <p className="text-xs text-muted">{formatDate(event.date)}</p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
