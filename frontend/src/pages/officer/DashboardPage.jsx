import { AlertTriangle, CheckCircle2, Clock, FileText, ShieldAlert, Timer } from "lucide-react";
import { useCallback, useMemo } from "react";
import { Link } from "react-router-dom";

import AreaTrendChart from "../../components/common/AreaTrendChart";
import Card from "../../components/common/Card";
import DataTable from "../../components/common/DataTable";
import DonutChart from "../../components/common/DonutChart";
import EmptyState from "../../components/common/EmptyState";
import ErrorState from "../../components/common/ErrorState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import StatCard from "../../components/common/StatCard";
import StatusBadge from "../../components/common/StatusBadge";
import { useAuth } from "../../hooks/useAuth";
import { useFetch } from "../../hooks/useFetch";
import TwoColumnLayout from "../../layouts/TwoColumnLayout";
import { getAiSummaryStats } from "../../services/aiRiskService";
import { getClaimProcessingDetail, listClaimsForProcessing } from "../../services/officerService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatDate } from "../../utils/format";
import { getStatusTone } from "../../utils/statusTone";

const today = () => new Date().toISOString().slice(0, 10);

export default function OfficerDashboardPage() {
  const { user } = useAuth();

  const fetchDashboard = useCallback(async () => {
    const summaries = await listClaimsForProcessing({ limit: 200 });
    const details = await Promise.all(summaries.map((s) => getClaimProcessingDetail(s.Claim_ID)));
    return { summaries, details };
  }, []);

  const { data, isLoading, error, reload } = useFetch(fetchDashboard, [fetchDashboard]);

  const kpis = useMemo(() => {
    if (!data) return null;
    const { details } = data;
    const decisionsRecorded = details.filter((d) => d.claim.Final_Decision).length;
    const decisionsToday = details.filter(
      (d) => d.claim.Final_Decision && String(d.claim.Decision_Date).slice(0, 10) === today()
    ).length;
    const tatValues = details.map((d) => d.claim.Claim_Processing_Days);
    const averageTat = tatValues.length ? Math.round(tatValues.reduce((a, b) => a + b, 0) / tatValues.length) : null;
    const fraudAlerts = details.filter((d) => d.fraud_risk_analysis[0]?.Fraud_Label === 1).length;
    return { decisionsRecorded, decisionsToday, averageTat, fraudAlerts };
  }, [data]);

  const claimsByStatus = useMemo(() => {
    if (!data) return [];
    const counts = new Map();
    data.summaries.forEach((c) => counts.set(c.Claim_Status, (counts.get(c.Claim_Status) ?? 0) + 1));
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [data]);

  const fraudByCategory = useMemo(() => {
    if (!data) return [];
    const counts = new Map();
    data.details.forEach((d) => {
      const category = d.fraud_risk_analysis[0]?.Risk_Category;
      if (category) counts.set(category, (counts.get(category) ?? 0) + 1);
    });
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [data]);

  const claimsPerMonth = useMemo(() => {
    if (!data) return [];
    const months = [];
    const now = new Date();
    for (let i = 5; i >= 0; i -= 1) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
      months.push({ key: `${d.getFullYear()}-${d.getMonth()}`, label: d.toLocaleDateString("en-IN", { month: "short" }), count: 0 });
    }
    const byKey = new Map(months.map((m) => [m.key, m]));
    data.summaries.forEach((c) => {
      const d = new Date(c.Claim_Date);
      const key = `${d.getFullYear()}-${d.getMonth()}`;
      if (byKey.has(key)) byKey.get(key).count += 1;
    });
    return months;
  }, [data]);

  const workQueuePreview = useMemo(
    () =>
      (data?.summaries ?? [])
        .filter((c) => !c.Final_Decision)
        .sort((a, b) => new Date(a.Claim_Date) - new Date(b.Claim_Date))
        .slice(0, 5),
    [data]
  );

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

  const aiSummary = getAiSummaryStats();
  const totalFraudCount = Math.max(1, fraudByCategory.reduce((sum, [, count]) => sum + count, 0));

  return (
    <div>
      <PageHeader title={`Welcome, ${user?.Username ?? ""}`} subtitle="Claims processing command center." />

      <TwoColumnLayout
        main={
          <>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
              <StatCard label="Pending Claims" value={workQueuePreview.length ? data.summaries.filter((c) => !c.Final_Decision).length : 0} icon={FileText} to="/officer/queue" actionLabel="View queue" />
              <StatCard label="Overdue Claims" value="N/A" icon={Clock} trend="SLA target not configured" />
              <StatCard label="Decisions Today" value={kpis.decisionsToday} icon={CheckCircle2} />
              <StatCard label="Average TAT" value={kpis.averageTat !== null ? `${kpis.averageTat} days` : "N/A"} icon={Timer} />
              <StatCard label="Fraud Alerts" value={kpis.fraudAlerts} icon={ShieldAlert} />
              <StatCard label="RFI Pending" value="N/A" icon={AlertTriangle} trend="No RFI data source yet" />
            </div>

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

            <Card>
              <h3 className="mb-4 text-sm font-semibold text-ink">Claims Trend (last 6 months)</h3>
              {data.summaries.length === 0 ? (
                <EmptyState title="No claims to chart yet" />
              ) : (
                <AreaTrendChart points={claimsPerMonth} />
              )}
            </Card>
          </>
        }
        aside={
          <>
            <Card>
              <h3 className="mb-4 text-sm font-semibold text-ink">Fraud Risk Distribution</h3>
              {fraudByCategory.length === 0 ? (
                <EmptyState
                  icon={ShieldAlert}
                  title="AI fraud analysis will appear here when the AI service is connected."
                />
              ) : (
                <ul className="space-y-3">
                  {fraudByCategory.map(([category, count]) => (
                    <li key={category}>
                      <div className="mb-1 flex items-center justify-between text-sm">
                        <span className="text-ink">{category}</span>
                        <span className="text-muted">{count}</span>
                      </div>
                      <div className="h-2 w-full overflow-hidden rounded-full bg-surface">
                        <div className="h-full rounded-full bg-danger" style={{ width: `${(count / totalFraudCount) * 100}%` }} />
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </Card>

            <Card>
              <div className="mb-4 flex flex-col gap-1">
                <h3 className="text-sm font-semibold text-ink">AI Risk Insights Summary</h3>
                <span className="text-xs text-muted">Research prototype (Step 5.4/5.5) — synthetic dataset, read-only</span>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <AiSummaryStat label="High Review Priority" value={aiSummary.highReviewPriority} />
                <AiSummaryStat label="Low AI Confidence" value={aiSummary.lowConfidence} />
                <AiSummaryStat label="Multiple Warning Signals" value={aiSummary.multipleWarningSignals} />
                <AiSummaryStat label="Insufficient Evidence" value={aiSummary.insufficientEvidence} />
              </div>
              <p className="mt-4 text-xs text-muted">
                Counts are computed from the Step 5.4 risk-fusion export across {aiSummary.totalClaimsAssessed} claims.
                AI output is advisory only; the Claims Officer makes every final decision.
              </p>
            </Card>

            <Card>
              <h3 className="mb-4 text-sm font-semibold text-ink">Claim Status Overview</h3>
              {claimsByStatus.length === 0 ? (
                <EmptyState title="No claims yet" />
              ) : (
                <DonutChart rows={claimsByStatus} />
              )}
            </Card>
          </>
        }
      />
    </div>
  );
}

function AiSummaryStat({ label, value }) {
  return (
    <div className="rounded-card border border-border p-3 text-center">
      <p className="text-2xl font-semibold text-ink">{value}</p>
      <p className="mt-1 text-xs text-muted">{label}</p>
    </div>
  );
}
