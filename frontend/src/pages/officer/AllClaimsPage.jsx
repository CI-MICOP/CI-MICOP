import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import BackButton from "../../components/common/BackButton";
import Card from "../../components/common/Card";
import DataTable from "../../components/common/DataTable";
import ErrorState from "../../components/common/ErrorState";
import PageHeader from "../../components/common/PageHeader";
import SearchInput from "../../components/common/SearchInput";
import StatusBadge from "../../components/common/StatusBadge";
import { useFetch } from "../../hooks/useFetch";
import { listClaimsForProcessing } from "../../services/officerService";
import { COMPLETED_STATUS, isCompleted } from "../../utils/claimWorkflow";
import { getApiErrorMessage } from "../../utils/errors";
import { formatCurrency, formatDate } from "../../utils/format";
import { getStatusTone } from "../../utils/statusTone";

export default function AllClaimsPage() {
  const [search, setSearch] = useState("");

  // Server-side filtered by the claim's persisted status (crud/claim.py's
  // list_all), then narrowed client-side with the same check the Queue
  // page uses - a claim still Under Review belongs there, not here (see
  // utils/claimWorkflow.js).
  const { data: claims, isLoading, error, reload } = useFetch(
    () => listClaimsForProcessing({ limit: 200, claim_status: COMPLETED_STATUS }),
    []
  );
  const completed = useMemo(() => (claims ?? []).filter(isCompleted), [claims]);

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return completed;
    return completed.filter(
      (c) =>
        c.Claim_Number.toLowerCase().includes(term) ||
        c.Customer_ID.toLowerCase().includes(term) ||
        c.Vehicle_ID.toLowerCase().includes(term) ||
        c.Policy_ID.toLowerCase().includes(term)
    );
  }, [completed, search]);

  return (
    <div>
      <PageHeader title="All Claims" subtitle="Claims that have completed officer review." />
      <BackButton fallback="/officer" />

      {error ? (
        <ErrorState message={getApiErrorMessage(error)} onRetry={reload} />
      ) : (
        <Card>
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Search Claim Number / Customer ID / Vehicle ID / Policy ID"
            className="mb-4 sm:max-w-md"
          />
          <DataTable
            isLoading={isLoading}
            rows={filtered}
            rowKey="Claim_ID"
            emptyMessage={completed.length ? "No claims match your search." : "No completed claims yet."}
            columns={[
              { key: "number", header: "Claim Number", render: (c) => c.Claim_Number },
              { key: "customer", header: "Customer ID", render: (c) => c.Customer_ID },
              { key: "vehicle", header: "Vehicle ID", render: (c) => c.Vehicle_ID },
              { key: "policy", header: "Policy ID", render: (c) => c.Policy_ID },
              { key: "type", header: "Claim Type", render: (c) => c.Claim_Type },
              { key: "amount", header: "Claim Amount", render: (c) => formatCurrency(c.Claim_Amount) },
              { key: "date", header: "Claim Date", render: (c) => formatDate(c.Claim_Date) },
              {
                key: "status",
                header: "Status",
                render: (c) => <StatusBadge label={c.Claim_Status} tone={getStatusTone(c.Claim_Status)} />,
              },
              { key: "decision", header: "Final Decision", render: (c) => c.Final_Decision || "-" },
              {
                key: "action",
                header: "Action",
                render: (c) => (
                  <Link to={`/officer/claims/${c.Claim_ID}`} className="font-medium text-brand-600 hover:text-brand-700">
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
