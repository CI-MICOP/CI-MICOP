import { Info, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import BackButton from "../../components/common/BackButton";
import Button from "../../components/common/Button";
import Card from "../../components/common/Card";
import DataTable from "../../components/common/DataTable";
import ErrorState from "../../components/common/ErrorState";
import PageHeader from "../../components/common/PageHeader";
import StatusBadge from "../../components/common/StatusBadge";
import { useFetch } from "../../hooks/useFetch";
import { listClaimsForProcessing } from "../../services/officerService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatCurrency, formatDate } from "../../utils/format";
import { getStatusTone } from "../../utils/statusTone";

const EMPTY_FIELDS = { claimNumber: "", customerId: "", vehicleId: "", policyId: "" };

export default function ClaimSearchPage() {
  const [fields, setFields] = useState(EMPTY_FIELDS);
  const [submitted, setSubmitted] = useState(null);

  const { data: claims, isLoading, error, reload } = useFetch(() => listClaimsForProcessing({ limit: 200 }), []);

  const results = useMemo(() => {
    if (!submitted || !claims) return null;
    return claims.filter((c) => {
      if (submitted.claimNumber && !c.Claim_Number.toLowerCase().includes(submitted.claimNumber.toLowerCase())) return false;
      if (submitted.customerId && !c.Customer_ID.toLowerCase().includes(submitted.customerId.toLowerCase())) return false;
      if (submitted.vehicleId && !c.Vehicle_ID.toLowerCase().includes(submitted.vehicleId.toLowerCase())) return false;
      if (submitted.policyId && !c.Policy_ID.toLowerCase().includes(submitted.policyId.toLowerCase())) return false;
      return true;
    });
  }, [claims, submitted]);

  function update(field, value) {
    setFields((prev) => ({ ...prev, [field]: value }));
  }

  function handleSubmit(event) {
    event.preventDefault();
    setSubmitted(fields);
  }

  return (
    <div>
      <PageHeader title="Claim Search" subtitle="Search claims by claim, customer, vehicle, or policy identifier." />
      <BackButton fallback="/officer" />

      {error ? (
        <ErrorState message={getApiErrorMessage(error)} onRetry={reload} />
      ) : (
        <>
          <Card className="mb-6">
            <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-ink">Claim Number</span>
                <input className="input" value={fields.claimNumber} onChange={(e) => update("claimNumber", e.target.value)} />
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-ink">Customer ID</span>
                <input className="input" value={fields.customerId} onChange={(e) => update("customerId", e.target.value)} />
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-ink">Vehicle ID</span>
                <input className="input" value={fields.vehicleId} onChange={(e) => update("vehicleId", e.target.value)} />
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-ink">Policy ID</span>
                <input className="input" value={fields.policyId} onChange={(e) => update("policyId", e.target.value)} />
              </label>
              <div className="sm:col-span-2 lg:col-span-4 flex items-center justify-between gap-3 border-t border-border pt-4">
                <p className="flex items-center gap-2 text-xs text-muted">
                  <Info className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  Searches within the claims already retrieved from the API - the backend does not provide a
                  dedicated server-side search endpoint yet.
                </p>
                <Button type="submit">
                  <Search className="h-4 w-4" aria-hidden="true" />
                  Search
                </Button>
              </div>
            </form>
          </Card>

          {results !== null && (
            <Card>
              <DataTable
                isLoading={isLoading}
                rows={results}
                rowKey="Claim_ID"
                emptyMessage="No claims match your search criteria."
                columns={[
                  { key: "number", header: "Claim Number", render: (c) => c.Claim_Number },
                  { key: "customer", header: "Customer ID", render: (c) => c.Customer_ID },
                  { key: "vehicle", header: "Vehicle ID", render: (c) => c.Vehicle_ID },
                  { key: "policy", header: "Policy ID", render: (c) => c.Policy_ID },
                  { key: "date", header: "Claim Date", render: (c) => formatDate(c.Claim_Date) },
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
                      <Link to={`/officer/claims/${c.Claim_ID}`} className="font-medium text-brand-600 hover:text-brand-700">
                        View Details
                      </Link>
                    ),
                  },
                ]}
              />
            </Card>
          )}
        </>
      )}
    </div>
  );
}
