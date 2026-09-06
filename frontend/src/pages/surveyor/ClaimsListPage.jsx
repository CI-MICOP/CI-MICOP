import { useCallback, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import Card from "../../components/common/Card";
import DataTable from "../../components/common/DataTable";
import ErrorState from "../../components/common/ErrorState";
import PageHeader from "../../components/common/PageHeader";
import SearchInput from "../../components/common/SearchInput";
import StatusBadge from "../../components/common/StatusBadge";
import { useFetch } from "../../hooks/useFetch";
import { listClaims } from "../../services/claimService";
import { getMyInspections } from "../../services/surveyorService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatCurrency, formatDate } from "../../utils/format";
import { getStatusTone } from "../../utils/statusTone";

export default function SurveyorClaimsListPage() {
  const [search, setSearch] = useState("");

  const fetchData = useCallback(async () => {
    const [claims, inspections] = await Promise.all([listClaims({ limit: 200 }), getMyInspections()]);
    return { claims, inspections };
  }, []);
  const { data, isLoading, error, reload } = useFetch(fetchData, [fetchData]);

  const inspectionByClaim = useMemo(() => {
    const map = new Map();
    (data?.inspections ?? []).forEach((i) => map.set(i.Claim_ID, i));
    return map;
  }, [data]);

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return data?.claims ?? [];
    return (data?.claims ?? []).filter(
      (c) =>
        c.Claim_Number.toLowerCase().includes(term) ||
        c.Claim_Type.toLowerCase().includes(term) ||
        c.Customer_ID.toLowerCase().includes(term) ||
        c.Vehicle_ID.toLowerCase().includes(term)
    );
  }, [data, search]);

  return (
    <div>
      <PageHeader title="Assigned Claims" subtitle="Claims currently assigned to you for inspection." />

      {error ? (
        <ErrorState message={getApiErrorMessage(error)} onRetry={reload} />
      ) : (
        <Card>
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Search Claim Number / Type / Customer ID / Vehicle ID"
            className="mb-4 sm:max-w-md"
          />
          <DataTable
            isLoading={isLoading}
            rows={filtered}
            rowKey="Claim_ID"
            emptyMessage={data?.claims?.length ? "No claims match your search." : "You have no assigned claims yet."}
            columns={[
              { key: "number", header: "Claim Number", render: (c) => c.Claim_Number },
              { key: "customer", header: "Customer ID", render: (c) => c.Customer_ID },
              { key: "vehicle", header: "Vehicle ID", render: (c) => c.Vehicle_ID },
              { key: "date", header: "Claim Date", render: (c) => formatDate(c.Claim_Date) },
              { key: "type", header: "Claim Type", render: (c) => c.Claim_Type },
              { key: "amount", header: "Claim Amount", render: (c) => formatCurrency(c.Claim_Amount) },
              {
                key: "status",
                header: "Status",
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
                  <Link to={`/surveyor/claims/${c.Claim_ID}`} className="font-medium text-brand-600 hover:text-brand-700">
                    View Details
                  </Link>
                ),
              },
            ]}
          />
        </Card>
      )}
    </div>
  );
}
