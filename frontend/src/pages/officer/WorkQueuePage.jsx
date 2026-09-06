import { useCallback, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import Card from "../../components/common/Card";
import DataTable from "../../components/common/DataTable";
import ErrorState from "../../components/common/ErrorState";
import PageHeader from "../../components/common/PageHeader";
import SearchInput from "../../components/common/SearchInput";
import StatusBadge from "../../components/common/StatusBadge";
import { getCustomerById } from "../../services/customerService";
import { useFetch } from "../../hooks/useFetch";
import { getClaimById } from "../../services/claimService";
import { listClaimsForProcessing } from "../../services/officerService";
import { getVehicleById } from "../../services/vehicleService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatCurrency, formatDate, formatVehicleLabel } from "../../utils/format";
import { getStatusTone } from "../../utils/statusTone";

async function dedupedFetch(ids, fetcher) {
  const unique = [...new Set(ids)];
  const entries = await Promise.all(
    unique.map((id) => fetcher(id).then((value) => [id, value]).catch(() => [id, null]))
  );
  return new Map(entries);
}

export default function WorkQueuePage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const fetchQueue = useCallback(async () => {
    const summaries = await listClaimsForProcessing({ limit: 200 });
    const pending = summaries.filter((c) => !c.Final_Decision);
    const [details, customerMap, vehicleMap] = await Promise.all([
      Promise.all(pending.map((c) => getClaimById(c.Claim_ID))),
      dedupedFetch(pending.map((c) => c.Customer_ID), getCustomerById),
      dedupedFetch(pending.map((c) => c.Vehicle_ID), getVehicleById),
    ]);
    const detailByClaim = new Map(details.map((d) => [d.Claim_ID, d]));
    return { pending, detailByClaim, customerMap, vehicleMap };
  }, []);

  const { data, isLoading, error, reload } = useFetch(fetchQueue, [fetchQueue]);

  const statuses = useMemo(() => [...new Set((data?.pending ?? []).map((c) => c.Claim_Status))], [data]);

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return (data?.pending ?? []).filter((c) => {
      const matchesStatus = statusFilter === "all" || c.Claim_Status === statusFilter;
      if (!term) return matchesStatus;
      const customerName = data.customerMap.get(c.Customer_ID)?.Customer_Name ?? "";
      const matchesSearch =
        c.Claim_Number.toLowerCase().includes(term) ||
        c.Claim_Type.toLowerCase().includes(term) ||
        customerName.toLowerCase().includes(term);
      return matchesStatus && matchesSearch;
    });
  }, [data, search, statusFilter]);

  return (
    <div>
      <PageHeader title="My Work Queue" subtitle="Claims awaiting a final decision." />

      {error ? (
        <ErrorState message={getApiErrorMessage(error)} onRetry={reload} />
      ) : (
        <Card>
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <SearchInput value={search} onChange={setSearch} placeholder="Search Claim Number / Type / Customer" className="sm:max-w-sm" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              aria-label="Filter by status"
              className="input sm:max-w-xs"
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
            rows={filtered}
            rowKey="Claim_ID"
            emptyMessage={data?.pending?.length ? "No claims match your filters." : "Your work queue is empty."}
            columns={[
              { key: "number", header: "Claim Number", render: (c) => c.Claim_Number },
              { key: "customer", header: "Insured / Customer", render: (c) => data.customerMap.get(c.Customer_ID)?.Customer_Name ?? c.Customer_ID },
              { key: "vehicle", header: "Vehicle", render: (c) => formatVehicleLabel(data.vehicleMap.get(c.Vehicle_ID)) },
              { key: "type", header: "Claim Type", render: (c) => c.Claim_Type },
              { key: "amount", header: "Claim Amount", render: (c) => formatCurrency(c.Claim_Amount) },
              { key: "date", header: "Claim Date", render: (c) => formatDate(c.Claim_Date) },
              {
                key: "status",
                header: "Status",
                render: (c) => <StatusBadge label={c.Claim_Status} tone={getStatusTone(c.Claim_Status)} />,
              },
              {
                key: "processing",
                header: "Processing Days",
                render: (c) => data.detailByClaim.get(c.Claim_ID)?.Claim_Processing_Days ?? "-",
              },
              {
                key: "decision",
                header: "Decision Status",
                render: () => <StatusBadge label="Pending Decision" tone="warning" />,
              },
              {
                key: "action",
                header: "Action",
                render: (c) => (
                  <Link to={`/officer/claims/${c.Claim_ID}`} className="font-medium text-brand-600 hover:text-brand-700">
                    Review
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
