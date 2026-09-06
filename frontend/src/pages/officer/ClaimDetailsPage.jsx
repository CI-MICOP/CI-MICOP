import { Info } from "lucide-react";
import { useParams } from "react-router-dom";

import Breadcrumbs from "../../components/common/Breadcrumbs";
import Card from "../../components/common/Card";
import EmptyState from "../../components/common/EmptyState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import StatusBadge from "../../components/common/StatusBadge";
import ClaimTabs from "../../components/officer/ClaimTabs";
import ClaimWorkspaceError from "../../components/officer/ClaimWorkspaceError";
import { useClaimWorkspace } from "../../hooks/useClaimWorkspace";
import { formatCurrency, formatDate, formatVehicleLabel } from "../../utils/format";
import { getStatusTone } from "../../utils/statusTone";

export default function OfficerClaimDetailsPage() {
  const { claimId } = useParams();
  const { data, isLoading, error, reload } = useClaimWorkspace(claimId);

  if (isLoading) return <LoadingState label="Loading claim details..." />;
  if (error) {
    return (
      <div>
        <PageHeader title="Claim Details" />
        <ClaimWorkspaceError error={error} onRetry={reload} />
      </div>
    );
  }

  const { claim, customer, vehicle, policy, documents, surveyor_inspections: inspections, repair_estimates: estimates } = data;

  return (
    <div>
      <Breadcrumbs items={[{ label: "All Claims", to: "/officer/claims" }, { label: claim.Claim_Number }]} />
      <PageHeader title={`Claim ${claim.Claim_Number}`} subtitle={`Filed on ${formatDate(claim.Claim_Date)}`} />
      <ClaimTabs claimId={claim.Claim_ID} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <h3 className="mb-4 text-sm font-semibold text-ink">Claim Summary</h3>
            <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Detail label="Claim Type" value={claim.Claim_Type} />
              <Detail label="Claim Amount" value={formatCurrency(claim.Claim_Amount)} />
              <Detail label="Approved Amount" value={formatCurrency(claim.Approved_Amount)} />
              <Detail label="Claim Status"><StatusBadge label={claim.Claim_Status} tone={getStatusTone(claim.Claim_Status)} /></Detail>
              <Detail label="Final Decision" value={claim.Final_Decision || "Pending"} />
              <Detail label="Decision Reason" value={claim.Decision_Reason || "-"} />
              <Detail label="Processing Days" value={claim.Claim_Processing_Days} />
              <Detail label="Repair Duration (Days)" value={claim.Repair_Duration_Days} />
            </dl>
            <div className="mt-4">
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted">Description</p>
              <p className="text-sm text-ink">{claim.Claim_Description}</p>
            </div>
          </Card>

          <Card>
            <h3 className="mb-4 text-sm font-semibold text-ink">Accident Information</h3>
            <p className="flex items-start gap-2 text-sm text-muted">
              <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              Detailed accident records are only exposed through the Surveyor/Admin inspection API
              (/surveyor/claims/{"{id}"}), which the Claims Officer role does not have access to. Only the
              claim-level accident fields below are available here.
            </p>
            <dl className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Detail label="Place of Accident" value={claim.Place_of_Accident} />
              <Detail label="Accident Pincode" value={claim.Accident_Pincode} />
            </dl>
          </Card>

          <Card>
            <h3 className="mb-4 text-sm font-semibold text-ink">Documents</h3>
            {documents.length === 0 ? (
              <EmptyState title="No documents uploaded for this claim" />
            ) : (
              <ul className="divide-y divide-border">
                {documents.map((doc) => (
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
          </Card>

          <Card>
            <h3 className="mb-4 text-sm font-semibold text-ink">Evidence</h3>
            <p className="flex items-start gap-2 text-sm text-muted">
              <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              Evidence records are only exposed through the Surveyor/Admin inspection API, which the Claims
              Officer role does not have access to through any existing endpoint.
            </p>
          </Card>

          <Card>
            <h3 className="mb-4 text-sm font-semibold text-ink">Repair Estimate</h3>
            {estimates.length === 0 ? (
              <EmptyState title="No repair estimate on file for this claim" />
            ) : (
              <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Detail label="Repair Estimate" value={formatCurrency(estimates[0].Repair_Estimate)} />
                <Detail label="Repair Cost" value={formatCurrency(estimates[0].Repair_Cost)} />
                <Detail label="Parts Cost" value={formatCurrency(estimates[0].Parts_Cost)} />
                <Detail label="Labour Cost" value={formatCurrency(estimates[0].Labour_Cost)} />
              </dl>
            )}
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <h3 className="mb-3 text-sm font-semibold text-ink">Policy</h3>
            {policy ? (
              <div className="space-y-1 text-sm">
                <p className="font-medium text-ink">{policy.Policy_Number}</p>
                <p className="text-muted">{policy.Policy_Type} &middot; {policy.Coverage_Type}</p>
                <p className="text-muted">{formatDate(policy.Policy_Start_Date)} - {formatDate(policy.Policy_End_Date)}</p>
                <StatusBadge label={policy.Policy_Status} tone={getStatusTone(policy.Policy_Status)} />
              </div>
            ) : (
              <p className="text-sm text-muted">Policy ID: {claim.Policy_ID}</p>
            )}
          </Card>

          <Card>
            <h3 className="mb-3 text-sm font-semibold text-ink">Customer</h3>
            {customer ? (
              <div className="space-y-1 text-sm">
                <p className="font-medium text-ink">{customer.Customer_Name}</p>
                <p className="text-muted">{customer.Email}</p>
                <p className="text-muted">{customer.Phone}</p>
                <p className="text-muted">{customer.City}, {customer.State}</p>
              </div>
            ) : (
              <p className="text-sm text-muted">Customer ID: {claim.Customer_ID}</p>
            )}
          </Card>

          <Card>
            <h3 className="mb-3 text-sm font-semibold text-ink">Vehicle</h3>
            {vehicle ? (
              <div className="space-y-1 text-sm">
                <p className="font-medium text-ink">{formatVehicleLabel(vehicle)}</p>
                <p className="text-muted">{vehicle.Fuel_Type} &middot; {vehicle.Manufacturing_Year}</p>
              </div>
            ) : (
              <p className="text-sm text-muted">Vehicle ID: {claim.Vehicle_ID}</p>
            )}
          </Card>

          <Card>
            <h3 className="mb-3 text-sm font-semibold text-ink">Surveyor Inspection</h3>
            {inspections.length === 0 ? (
              <EmptyState title="No inspection recorded yet" />
            ) : (
              <div className="space-y-2 text-sm">
                <StatusBadge label={inspections[0].Inspection_Status} tone={getStatusTone(inspections[0].Inspection_Status)} />
                <p className="text-muted">{formatDate(inspections[0].Inspection_Date)}</p>
                <p className="text-muted">{inspections[0].Repair_Recommendation}</p>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}

function Detail({ label, value, children }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-muted">{label}</dt>
      <dd className="mt-0.5 text-sm text-ink">{children ?? value}</dd>
    </div>
  );
}
