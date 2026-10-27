import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import Card from "../../components/common/Card";
import DataTable from "../../components/common/DataTable";
import ErrorState from "../../components/common/ErrorState";
import PageHeader from "../../components/common/PageHeader";
import SearchInput from "../../components/common/SearchInput";
import StatusBadge from "../../components/common/StatusBadge";
import { useFetch } from "../../hooks/useFetch";
import { getActiveInspections } from "../../services/surveyorService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatCurrency, formatDate } from "../../utils/format";
import { getStatusTone } from "../../utils/statusTone";

/**
 * Active inspections only: the server lists the surveyor's inspections
 * whose report has not been submitted (GET /surveyor/active-inspections).
 * A submitted claim leaves this list for the Survey Reports history.
 */
export default function SurveyorClaimsListPage() {
  const [search, setSearch] = useState("");
  const { data, isLoading, error, reload } = useFetch(getActiveInspections, []);
  const rows = useMemo(() => (data ?? []).filter((row) => row.claim), [data]);

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return rows;
    return rows.filter(({ claim }) =>
      [claim.Claim_Number, claim.Claim_Type, claim.Customer_ID, claim.Vehicle_ID].some((value) =>
        value.toLowerCase().includes(term)
      )
    );
  }, [rows, search]);

  return (
    <div>
      <PageHeader title="Assigned Inspections" subtitle="Claims currently assigned to you for inspection." />

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
            rows={filtered.map((row) => ({ ...row, key: row.inspection.Inspection_ID }))}
            rowKey="key"
            emptyMessage={rows.length ? "No claims match your search." : "You have no active inspections."}
            columns={[
              { key: "number", align: "center", header: "Claim Number", render: (r) => r.claim.Claim_Number },
              { key: "customer", align: "center", header: "Customer ID", render: (r) => r.claim.Customer_ID },
              { key: "vehicle", align: "center", header: "Vehicle ID", render: (r) => r.claim.Vehicle_ID },
              { key: "type", align: "center", header: "Claim Type", render: (r) => r.claim.Claim_Type },
              { key: "amount", align: "center", header: "Claim Amount", render: (r) => formatCurrency(r.claim.Claim_Amount) },
              {
                key: "scheduled",
                align: "center",
                header: "Scheduled For",
                render: (r) => (
                  <span className="whitespace-nowrap">
                    {formatDate(r.inspection.Inspection_Date)}
                    {r.schedule && !r.schedule.reached && <span className="block text-xs text-amber-700">Not open yet</span>}
                  </span>
                ),
              },
              {
                key: "inspection",
                align: "center",
                header: "Inspection Status",
                render: (r) => <StatusBadge label={r.inspection.Inspection_Status} tone={getStatusTone(r.inspection.Inspection_Status)} />,
              },
              {
                key: "action",
                align: "center",
                header: "Action",
                render: (r) => (
                  // A link (it navigates) styled like the small primary Button.
                  <Link
                    to={`/surveyor/claims/${r.claim.Claim_ID}`}
                    className="inline-flex items-center justify-center whitespace-nowrap rounded-lg bg-brand-600 px-3
                      py-1.5 text-sm font-medium text-white transition-colors hover:bg-brand-700 focus-visible:outline
                      focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600"
                  >
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
