import {
  Bell,
  Car,
  FilePlus,
  FileText,
  FolderOpen,
  LayoutDashboard,
  LifeBuoy,
  ShieldCheck,
  UploadCloud,
} from "lucide-react";
import { useCallback, useMemo } from "react";
import { Link } from "react-router-dom";

import Card from "../../components/common/Card";
import DataTable from "../../components/common/DataTable";
import EmptyState from "../../components/common/EmptyState";
import ErrorState from "../../components/common/ErrorState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import QuickActionCard from "../../components/common/QuickActionCard";
import StatCard from "../../components/common/StatCard";
import StatusBadge from "../../components/common/StatusBadge";
import { useAuth } from "../../hooks/useAuth";
import { useFetch } from "../../hooks/useFetch";
import { listClaims } from "../../services/claimService";
import { listMyDocuments } from "../../services/documentService";
import { getMyPolicies } from "../../services/policyService";
import { getMyVehicles } from "../../services/vehicleService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatCurrency, formatDate, formatVehicleLabel } from "../../utils/format";
import { getStatusTone } from "../../utils/statusTone";

function SectionCard({ title, action, children }) {
  return (
    <Card>
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-ink">{title}</h3>
        {action}
      </div>
      {children}
    </Card>
  );
}

export default function CustomerDashboardPage() {
  const { user } = useAuth();

  const fetchDashboard = useCallback(async () => {
    const [claims, vehicles, policies, documents] = await Promise.all([
      listClaims({ limit: 200 }),
      getMyVehicles(),
      getMyPolicies(),
      listMyDocuments(),
    ]);
    return { claims, vehicles, policies, documents };
  }, []);

  const { data, isLoading, error, reload } = useFetch(fetchDashboard, [fetchDashboard]);

  const vehicleById = useMemo(() => {
    const map = new Map();
    (data?.vehicles ?? []).forEach((vehicle) => map.set(vehicle.Vehicle_ID, vehicle));
    return map;
  }, [data]);

  const recentClaims = useMemo(
    () =>
      [...(data?.claims ?? [])]
        .sort((a, b) => new Date(b.Claim_Date) - new Date(a.Claim_Date))
        .slice(0, 5),
    [data]
  );

  const claimsByStatus = useMemo(() => {
    const counts = new Map();
    (data?.claims ?? []).forEach((claim) => {
      counts.set(claim.Claim_Status, (counts.get(claim.Claim_Status) ?? 0) + 1);
    });
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [data]);

  const claimsPerMonth = useMemo(() => {
    const months = [];
    const now = new Date();
    for (let i = 5; i >= 0; i -= 1) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
      months.push({ key: `${d.getFullYear()}-${d.getMonth()}`, label: d.toLocaleDateString("en-IN", { month: "short" }), count: 0 });
    }
    const byKey = new Map(months.map((m) => [m.key, m]));
    (data?.claims ?? []).forEach((claim) => {
      const d = new Date(claim.Claim_Date);
      const key = `${d.getFullYear()}-${d.getMonth()}`;
      if (byKey.has(key)) byKey.get(key).count += 1;
    });
    return months;
  }, [data]);

  const recentDocuments = useMemo(
    () =>
      [...(data?.documents ?? [])]
        .sort((a, b) => new Date(b.Document_Submitted_Date) - new Date(a.Document_Submitted_Date))
        .slice(0, 5),
    [data]
  );

  const activePolicies = useMemo(
    () => (data?.policies ?? []).filter((policy) => policy.Policy_Status === "Active"),
    [data]
  );

  const latestActivity = useMemo(() => {
    const events = [];
    (data?.claims ?? []).forEach((claim) => {
      events.push({
        id: `claim-${claim.Claim_ID}`,
        date: claim.Claim_Date,
        text: `Claim ${claim.Claim_Number} submitted (${claim.Claim_Type})`,
      });
    });
    (data?.documents ?? []).forEach((doc) => {
      events.push({
        id: `doc-${doc.Document_ID}`,
        date: doc.Document_Submitted_Date,
        text: `${doc.Document_Type} uploaded for claim ${doc.Claim_Number}`,
      });
    });
    return events.sort((a, b) => new Date(b.date) - new Date(a.date)).slice(0, 6);
  }, [data]);

  if (isLoading) {
    return (
      <div>
        <PageHeader title={`Good morning, ${user?.Username ?? ""}`} subtitle="Track your motor insurance claims with ease." />
        <LoadingState label="Loading your dashboard..." />
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <PageHeader title={`Good morning, ${user?.Username ?? ""}`} subtitle="Track your motor insurance claims with ease." />
        <ErrorState message={getApiErrorMessage(error)} onRetry={reload} />
      </div>
    );
  }

  const maxMonthCount = Math.max(1, ...claimsPerMonth.map((m) => m.count));
  const totalStatusCount = Math.max(1, claimsByStatus.reduce((sum, [, count]) => sum + count, 0));

  return (
    <div>
      <PageHeader
        title={`Good morning, ${user?.Username ?? ""}`}
        subtitle="Track your motor insurance claims with ease."
      />

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard label="Total Claims" value={data.claims.length} icon={FileText} to="/customer/claims" actionLabel={data.claims.length ? "View details" : undefined} />
        <StatCard label="Vehicles" value={data.vehicles.length} icon={Car} />
        <StatCard label="Active Policies" value={activePolicies.length} icon={ShieldCheck} to="/customer/policies" actionLabel={activePolicies.length ? "View details" : undefined} />
        <StatCard label="Documents" value={data.documents.length} icon={FolderOpen} to="/customer/documents" actionLabel={data.documents.length ? "View details" : undefined} />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <SectionCard
            title="Recent Claims"
            action={
              <Link to="/customer/claims" className="text-sm font-medium text-brand-600 hover:text-brand-700">
                View all
              </Link>
            }
          >
            <DataTable
              columns={[
                { key: "number", header: "Claim", render: (c) => c.Claim_Number },
                { key: "date", header: "Date", render: (c) => formatDate(c.Claim_Date) },
                { key: "vehicle", header: "Vehicle", render: (c) => formatVehicleLabel(vehicleById.get(c.Vehicle_ID)) },
                { key: "type", header: "Type", render: (c) => c.Claim_Type },
                {
                  key: "status",
                  header: "Status",
                  render: (c) => <StatusBadge label={c.Claim_Status} tone={getStatusTone(c.Claim_Status)} />,
                },
                {
                  key: "action",
                  header: "Action",
                  render: (c) => (
                    <Link to={`/customer/claims/${c.Claim_ID}`} className="text-brand-600 hover:text-brand-700">
                      View
                    </Link>
                  ),
                },
              ]}
              rows={recentClaims}
              rowKey="Claim_ID"
              emptyMessage="No claims yet."
            />
          </SectionCard>
        </div>

        <SectionCard title="Quick Actions">
          <div className="grid grid-cols-1 gap-3">
            <QuickActionCard label="File a New Claim" description="Start a new claim in a few steps" icon={FilePlus} to="/customer/claims/new" />
            <QuickActionCard label="View My Claims" description="Track your claim progress" icon={FileText} to="/customer/claims" />
            <QuickActionCard label="Upload Documents" description="Upload pending documents" icon={UploadCloud} to="/customer/documents/upload" />
            <QuickActionCard label="View Policies" description="See your active policies" icon={ShieldCheck} to="/customer/policies" />
            <QuickActionCard label="Contact Support" description="Get help from our team" icon={LifeBuoy} to="/customer/support" />
          </div>
        </SectionCard>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <SectionCard title="Claim Status Overview">
          {claimsByStatus.length === 0 ? (
            <EmptyState icon={LayoutDashboard} title="No claim status data yet" />
          ) : (
            <ul className="space-y-3">
              {claimsByStatus.map(([status, count]) => (
                <li key={status}>
                  <div className="mb-1 flex items-center justify-between text-sm">
                    <span className="text-ink">{status}</span>
                    <span className="text-muted">{count}</span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-surface">
                    <div
                      className="h-full rounded-full bg-brand-500"
                      style={{ width: `${(count / totalStatusCount) * 100}%` }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </SectionCard>

        <SectionCard title="Claims Trend (last 6 months)">
          {data.claims.length === 0 ? (
            <EmptyState icon={FileText} title="No claims to chart yet" />
          ) : (
            <div className="flex h-32 items-end gap-3">
              {claimsPerMonth.map((month) => (
                <div key={month.key} className="flex flex-1 flex-col items-center gap-1.5">
                  <div
                    className="w-full rounded-t bg-brand-500"
                    style={{ height: `${(month.count / maxMonthCount) * 100}%`, minHeight: month.count ? 4 : 0 }}
                  />
                  <span className="text-xs text-muted">{month.label}</span>
                </div>
              ))}
            </div>
          )}
        </SectionCard>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <SectionCard
          title="My Policy Details"
          action={
            <Link to="/customer/policies" className="text-sm font-medium text-brand-600 hover:text-brand-700">
              View all
            </Link>
          }
        >
          {data.policies.length === 0 ? (
            <EmptyState icon={ShieldCheck} title="No policies on file" />
          ) : (
            <div className="space-y-1.5 text-sm">
              <p className="font-medium text-ink">{data.policies[0].Policy_Number}</p>
              <p className="text-muted">{data.policies[0].Policy_Type} &middot; {formatVehicleLabel(vehicleById.get(data.policies[0].Vehicle_ID))}</p>
              <p className="text-muted">
                {formatDate(data.policies[0].Policy_Start_Date)} - {formatDate(data.policies[0].Policy_End_Date)}
              </p>
              <p className="text-muted">IDV: {formatCurrency(data.policies[0].IDV)}</p>
              <StatusBadge label={data.policies[0].Policy_Status} tone={getStatusTone(data.policies[0].Policy_Status)} />
            </div>
          )}
        </SectionCard>

        <SectionCard title="My Vehicle">
          {data.vehicles.length === 0 ? (
            <EmptyState icon={Car} title="No vehicles on file" />
          ) : (
            <div className="space-y-1.5 text-sm">
              <p className="font-medium text-ink">{formatVehicleLabel(data.vehicles[0])}</p>
              <p className="text-muted">{data.vehicles[0].Fuel_Type} &middot; {data.vehicles[0].Manufacturing_Year}</p>
              <p className="text-muted">Chassis: {data.vehicles[0].Chassis_Number}</p>
            </div>
          )}
        </SectionCard>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <SectionCard
          title="Recent Documents"
          action={
            <Link to="/customer/documents" className="text-sm font-medium text-brand-600 hover:text-brand-700">
              View all
            </Link>
          }
        >
          {recentDocuments.length === 0 ? (
            <EmptyState icon={FolderOpen} title="No documents uploaded yet" />
          ) : (
            <ul className="divide-y divide-border">
              {recentDocuments.map((doc) => (
                <li key={doc.Document_ID} className="flex items-center justify-between py-2.5 text-sm">
                  <div>
                    <p className="text-ink">{doc.Document_Type}</p>
                    <p className="text-xs text-muted">{formatDate(doc.Document_Submitted_Date)}</p>
                  </div>
                  <StatusBadge label={doc.Document_Status} tone={getStatusTone(doc.Document_Status)} />
                </li>
              ))}
            </ul>
          )}
        </SectionCard>

        <SectionCard title="Recent Notifications">
          <EmptyState icon={Bell} title="You're all caught up" message="Notification history isn't available yet." />
        </SectionCard>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <SectionCard title="Latest Activity">
          {latestActivity.length === 0 ? (
            <EmptyState icon={LayoutDashboard} title="No recent activity" />
          ) : (
            <ul className="space-y-3">
              {latestActivity.map((event) => (
                <li key={event.id} className="text-sm">
                  <p className="text-ink">{event.text}</p>
                  <p className="text-xs text-muted">{formatDate(event.date)}</p>
                </li>
              ))}
            </ul>
          )}
        </SectionCard>

        <SectionCard title="Need Help?">
          <p className="mb-3 text-sm text-muted">Our support team is here to help.</p>
          <QuickActionCard label="Raise a Request" description="Log an issue or support request" icon={LifeBuoy} to="/customer/support" />
        </SectionCard>
      </div>
    </div>
  );
}
