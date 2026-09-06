import { useMemo, useState } from "react";

import Card from "../../components/common/Card";
import DataTable from "../../components/common/DataTable";
import ErrorState from "../../components/common/ErrorState";
import Modal from "../../components/common/Modal";
import PageHeader from "../../components/common/PageHeader";
import StatusBadge from "../../components/common/StatusBadge";
import { useFetch } from "../../hooks/useFetch";
import { getMyPolicies } from "../../services/policyService";
import { getMyVehicles } from "../../services/vehicleService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatCurrency, formatDate, formatVehicleLabel } from "../../utils/format";
import { getStatusTone } from "../../utils/statusTone";

export default function PoliciesPage() {
  const [selectedPolicy, setSelectedPolicy] = useState(null);

  const fetchData = useMemo(
    () => async () => {
      const [policies, vehicles] = await Promise.all([getMyPolicies(), getMyVehicles()]);
      return { policies, vehicles };
    },
    []
  );
  const { data, isLoading, error, reload } = useFetch(fetchData, [fetchData]);

  const vehicleById = useMemo(() => {
    const map = new Map();
    (data?.vehicles ?? []).forEach((vehicle) => map.set(vehicle.Vehicle_ID, vehicle));
    return map;
  }, [data]);

  return (
    <div>
      <PageHeader title="My Policies" subtitle="View your motor insurance policy details." />

      {error ? (
        <ErrorState message={getApiErrorMessage(error)} onRetry={reload} />
      ) : (
        <Card>
          <DataTable
            isLoading={isLoading}
            rows={data?.policies ?? []}
            rowKey="Policy_ID"
            emptyMessage="No policies on file."
            columns={[
              { key: "number", header: "Policy Number", render: (p) => p.Policy_Number },
              { key: "type", header: "Type", render: (p) => p.Policy_Type },
              { key: "vehicle", header: "Vehicle", render: (p) => formatVehicleLabel(vehicleById.get(p.Vehicle_ID)) },
              { key: "coverage", header: "Coverage", render: (p) => p.Coverage_Type },
              { key: "from", header: "Valid From", render: (p) => formatDate(p.Policy_Start_Date) },
              { key: "to", header: "Valid To", render: (p) => formatDate(p.Policy_End_Date) },
              { key: "premium", header: "Premium", render: (p) => formatCurrency(p.Premium_Amount) },
              {
                key: "status",
                header: "Status",
                render: (p) => <StatusBadge label={p.Policy_Status} tone={getStatusTone(p.Policy_Status)} />,
              },
              {
                key: "action",
                header: "Action",
                render: (p) => (
                  <button
                    type="button"
                    onClick={() => setSelectedPolicy(p)}
                    className="font-medium text-brand-600 hover:text-brand-700"
                  >
                    View Details
                  </button>
                ),
              },
            ]}
          />
        </Card>
      )}

      <Modal isOpen={Boolean(selectedPolicy)} onClose={() => setSelectedPolicy(null)} title="Policy Details">
        {selectedPolicy && (
          <dl className="space-y-3 text-sm">
            <Row label="Policy Number" value={selectedPolicy.Policy_Number} />
            <Row label="Policy Type" value={selectedPolicy.Policy_Type} />
            <Row label="Coverage Type" value={selectedPolicy.Coverage_Type} />
            <Row label="Vehicle" value={formatVehicleLabel(vehicleById.get(selectedPolicy.Vehicle_ID))} />
            <Row label="Valid From" value={formatDate(selectedPolicy.Policy_Start_Date)} />
            <Row label="Valid To" value={formatDate(selectedPolicy.Policy_End_Date)} />
            <Row label="Premium" value={formatCurrency(selectedPolicy.Premium_Amount)} />
            <Row label="Sum Insured" value={formatCurrency(selectedPolicy.Sum_Insured)} />
            <Row label="IDV" value={formatCurrency(selectedPolicy.IDV)} />
            <Row label="Deductible" value={formatCurrency(selectedPolicy.Deductible_Amount)} />
            <Row label="No Claim Bonus" value={`${selectedPolicy.No_Claim_Bonus}%`} />
            <Row label="Status" value={selectedPolicy.Policy_Status} />
            <Row label="Renewal Status" value={selectedPolicy.Renewal_Status} />
          </dl>
        )}
      </Modal>
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-muted">{label}</dt>
      <dd className="text-right text-ink">{value}</dd>
    </div>
  );
}
