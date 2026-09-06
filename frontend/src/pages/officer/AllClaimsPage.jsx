import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import Card from "../../components/common/Card";
import DataTable from "../../components/common/DataTable";
import ErrorState from "../../components/common/ErrorState";
import PageHeader from "../../components/common/PageHeader";
import SearchInput from "../../components/common/SearchInput";
import StatusBadge from "../../components/common/StatusBadge";
import { useFetch } from "../../hooks/useFetch";
import { listClaimsForProcessing } from "../../services/officerService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatCurrency, formatDate } from "../../utils/format";
import { getStatusTone } from "../../utils/statusTone";

export default function AllClaimsPage() {
  const [search, setSearch] = useState("");

  const { data: claims, isLoading, error, reload } = useFetch(() => listClaimsForProcessing({ limit: 200 }), []);

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return claims ?? [];
    return (claims ?? []).filter(
      (c) =>
        c.Claim_Number.toLowerCase().includes(term) ||
        c.Customer_ID.toLowerCase().includes(term) ||
        c.Vehicle_ID.toLowerCase().includes(term) ||
        c.Policy_ID.toLowerCase().includes(term)
    );
  }, [claims, search]);

  return (
    <div>
      <PageHeader title="All Claims" subtitle="Every claim visible to Claims Officer / Admin." />

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
            emptyMessage={claims?.length ? "No claims match your search." : "No claims found."}
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
