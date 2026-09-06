import { FilePlus } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import Button from "../../components/common/Button";
import Card from "../../components/common/Card";
import DataTable from "../../components/common/DataTable";
import ErrorState from "../../components/common/ErrorState";
import PageHeader from "../../components/common/PageHeader";
import SearchInput from "../../components/common/SearchInput";
import StatusBadge from "../../components/common/StatusBadge";
import { useFetch } from "../../hooks/useFetch";
import { listClaims } from "../../services/claimService";
import { getMyVehicles } from "../../services/vehicleService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatCurrency, formatDate, formatVehicleLabel } from "../../utils/format";
import { getStatusTone } from "../../utils/statusTone";

const PAGE_SIZE = 10;

export default function ClaimsListPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [page, setPage] = useState(1);

  const fetchData = useCallback(async () => {
    const [claims, vehicles] = await Promise.all([
      listClaims({ limit: 200 }),
      getMyVehicles(),
    ]);
    return { claims, vehicles };
  }, []);

  const { data, isLoading, error, reload } = useFetch(fetchData, [fetchData]);

  const vehicleById = useMemo(() => {
    const map = new Map();
    (data?.vehicles ?? []).forEach((vehicle) => map.set(vehicle.Vehicle_ID, vehicle));
    return map;
  }, [data]);

  const statuses = useMemo(
    () => [...new Set((data?.claims ?? []).map((c) => c.Claim_Status))],
    [data]
  );

  const filteredClaims = useMemo(() => {
    const term = search.trim().toLowerCase();
    return (data?.claims ?? []).filter((claim) => {
      const matchesStatus = statusFilter === "all" || claim.Claim_Status === statusFilter;
      const matchesSearch =
        !term ||
        claim.Claim_Number.toLowerCase().includes(term) ||
        claim.Claim_Type.toLowerCase().includes(term) ||
        formatVehicleLabel(vehicleById.get(claim.Vehicle_ID)).toLowerCase().includes(term);
      return matchesStatus && matchesSearch;
    });
  }, [data, search, statusFilter, vehicleById]);

  const totalPages = Math.max(1, Math.ceil(filteredClaims.length / PAGE_SIZE));
  const pageClaims = filteredClaims.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  function handleSearchChange(value) {
    setSearch(value);
    setPage(1);
  }

  function handleStatusChange(value) {
    setStatusFilter(value);
    setPage(1);
  }

  return (
    <div>
      <PageHeader
        title="My Claims"
        subtitle="Track and manage all your motor insurance claims."
        actions={
          <Link to="/customer/claims/new">
            <Button>
              <FilePlus className="h-4 w-4" aria-hidden="true" />
              File a New Claim
            </Button>
          </Link>
        }
      />

      {error ? (
        <ErrorState message={getApiErrorMessage(error)} onRetry={reload} />
      ) : (
        <Card>
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <SearchInput
              value={search}
              onChange={handleSearchChange}
              placeholder="Search Claim ID / Vehicle / Type"
              className="sm:max-w-xs"
            />
            <select
              value={statusFilter}
              onChange={(event) => handleStatusChange(event.target.value)}
              aria-label="Filter by status"
              className="rounded-lg border border-border px-3 py-2 text-sm text-ink focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            >
              <option value="all">All statuses</option>
              {statuses.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
          </div>

          <DataTable
            isLoading={isLoading}
            emptyMessage={data?.claims?.length ? "No claims match your filters." : "You have no claims yet."}
            rows={pageClaims}
            rowKey="Claim_ID"
            columns={[
              { key: "number", header: "Claim Number", render: (c) => c.Claim_Number },
              { key: "date", header: "Date", render: (c) => formatDate(c.Claim_Date) },
              { key: "vehicle", header: "Vehicle", render: (c) => formatVehicleLabel(vehicleById.get(c.Vehicle_ID)) },
              { key: "type", header: "Type", render: (c) => c.Claim_Type },
              { key: "amount", header: "Claim Amount", render: (c) => formatCurrency(c.Claim_Amount) },
              {
                key: "status",
                header: "Status",
                render: (c) => <StatusBadge label={c.Claim_Status} tone={getStatusTone(c.Claim_Status)} />,
              },
              {
                key: "action",
                header: "Action",
                render: (c) => (
                  <Link to={`/customer/claims/${c.Claim_ID}`} className="font-medium text-brand-600 hover:text-brand-700">
                    View Details
                  </Link>
                ),
              },
            ]}
          />

          {!isLoading && filteredClaims.length > PAGE_SIZE && (
            <div className="mt-4 flex items-center justify-between text-sm text-muted">
              <span>
                Showing {(page - 1) * PAGE_SIZE + 1}-{Math.min(page * PAGE_SIZE, filteredClaims.length)} of{" "}
                {filteredClaims.length} claims
              </span>
              <div className="flex items-center gap-2">
                <Button variant="secondary" size="sm" disabled={page === 1} onClick={() => setPage((p) => p - 1)}>
                  Previous
                </Button>
                <span>
                  Page {page} of {totalPages}
                </span>
                <Button variant="secondary" size="sm" disabled={page === totalPages} onClick={() => setPage((p) => p + 1)}>
                  Next
                </Button>
              </div>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
