import { FilePlus, FileText, FolderOpen, ShieldCheck } from "lucide-react";
import { useCallback, useMemo } from "react";
import { Link } from "react-router-dom";

import Button from "../../components/common/Button";
import Card from "../../components/common/Card";
import DataTable from "../../components/common/DataTable";
import ErrorState from "../../components/common/ErrorState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import StatCard from "../../components/common/StatCard";
import StatusBadge from "../../components/common/StatusBadge";
import { useAuth } from "../../hooks/useAuth";
import { useFetch } from "../../hooks/useFetch";
import { listClaims } from "../../services/claimService";
import { listMyDocuments } from "../../services/documentService";
import { getMyPolicies } from "../../services/policyService";
import { getMyVehicles } from "../../services/vehicleService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatDate, formatVehicleLabel } from "../../utils/format";
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

  const activePolicies = useMemo(
    () => (data?.policies ?? []).filter((policy) => policy.Policy_Status === "Active"),
    [data]
  );

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

  return (
    <div>
      <PageHeader
        title={`Good morning, ${user?.Username ?? ""}`}
        subtitle="Track your motor insurance claims with ease."
        actions={
          <Link to="/customer/claims/new">
            <Button>
              <FilePlus className="h-4 w-4" aria-hidden="true" />
              File a New Claim
            </Button>
          </Link>
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="Total Claims" value={data.claims.length} icon={FileText} to="/customer/claims" actionLabel={data.claims.length ? "View details" : undefined} />
        <StatCard label="Active Policies" value={activePolicies.length} icon={ShieldCheck} to="/customer/policies" actionLabel={activePolicies.length ? "View details" : undefined} />
        <StatCard label="Documents" value={data.documents.length} icon={FolderOpen} to="/customer/documents" actionLabel={data.documents.length ? "View details" : undefined} />
      </div>

      <div className="mt-6">
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
    </div>
  );
}
