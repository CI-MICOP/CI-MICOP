import { Info } from "lucide-react";
import { useCallback } from "react";
import { Link, useParams } from "react-router-dom";

import Breadcrumbs from "../../components/common/Breadcrumbs";
import Card from "../../components/common/Card";
import EmptyState from "../../components/common/EmptyState";
import ErrorState from "../../components/common/ErrorState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import StatusBadge from "../../components/common/StatusBadge";
import ClaimTabs from "../../components/surveyor/ClaimTabs";
import { useFetch } from "../../hooks/useFetch";
import { getClaimById } from "../../services/claimService";
import { listDocumentsByClaim } from "../../services/documentService";
import { getAssignedClaimDetail } from "../../services/surveyorService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatCurrency, formatDate } from "../../utils/format";
import { getStatusTone } from "../../utils/statusTone";

export default function SurveyorClaimDetailsPage() {
  const { claimId } = useParams();

  const fetchDetail = useCallback(async () => {
    const [claim, assigned, documents] = await Promise.all([
      getClaimById(claimId),
      getAssignedClaimDetail(claimId),
      listDocumentsByClaim(claimId),
    ]);
    return { claim, ...assigned, documents };
  }, [claimId]);

  const { data, isLoading, error, reload } = useFetch(fetchDetail, [fetchDetail]);

  if (isLoading) return <LoadingState label="Loading claim details..." />;
  if (error) {
    return (
      <div>
        <PageHeader title="Claim Details" />
        <ErrorState
          title={error.response?.status === 403 ? "Not assigned to you" : error.response?.status === 404 ? "Claim not found" : "Unable to load this claim"}
          message={getApiErrorMessage(error)}
          onRetry={reload}
        />
      </div>
    );
  }

  const { claim, accidents, evidence, repair_estimates, inspections, documents } = data;
  const accident = accidents[0];

  return (
    <div>
      <Breadcrumbs items={[{ label: "Assigned Claims", to: "/surveyor/claims" }, { label: claim.Claim_Number }]} />
      <PageHeader title={`Claim ${claim.Claim_Number}`} subtitle={`Filed on ${formatDate(claim.Claim_Date)}`} />
      <ClaimTabs claimId={claim.Claim_ID} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <h3 className="mb-4 text-sm font-semibold text-ink">Claim Information</h3>
            <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Detail label="Claim Status">
                <StatusBadge label={claim.Claim_Status} tone={getStatusTone(claim.Claim_Status)} />
              </Detail>
              <Detail label="Claim Type" value={claim.Claim_Type} />
              <Detail label="Claim Amount" value={formatCurrency(claim.Claim_Amount)} />
              <Detail label="Customer ID" value={claim.Customer_ID} />
              <Detail label="Vehicle ID" value={claim.Vehicle_ID} />
              <Detail label="Policy ID" value={claim.Policy_ID} />
            </dl>
            <p className="mt-4 flex items-start gap-2 rounded-card bg-surface p-3 text-xs text-muted">
              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              Full customer, vehicle, and policy profile details are not available to the Surveyor role
              through the current API - only these identifiers are shown.
            </p>
          </Card>

          <Card>
            <h3 className="mb-4 text-sm font-semibold text-ink">Accident Information</h3>
            {!accident ? (
              <EmptyState title="No accident record found for this claim" />
            ) : (
              <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Detail label="Accident Date" value={formatDate(accident.Accident_Date)} />
                <Detail label="Accident Time" value={accident.Accident_Time} />
                <Detail label="Location" value={accident.Accident_Location} />
                <Detail label="City / State" value={`${accident.Accident_City}, ${accident.Accident_State}`} />
                <Detail label="Accident Type" value={accident.Accident_Type} />
                <Detail label="Weather Condition" value={accident.Weather_Condition} />
                <Detail label="Road Condition" value={accident.Road_Condition} />
                <Detail label="Police Report Available" value={accident.Police_Report_Available ? "Yes" : "No"} />
                <Detail label="FIR Number" value={accident.FIR_Number || "-"} />
                <Detail label="Third Party Involved" value={accident.Third_Party_Involved ? "Yes" : "No"} />
                <Detail label="Injury Reported" value={accident.Injury_Reported ? "Yes" : "No"} />
                <Detail label="Witness Available" value={accident.Witness_Available ? "Yes" : "No"} />
                <div className="sm:col-span-2">
                  <dt className="text-xs font-medium uppercase tracking-wide text-muted">Description</dt>
                  <dd className="mt-0.5 text-sm text-ink">{accident.Accident_Description}</dd>
                </div>
              </dl>
            )}
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

        </div>

        <div className="space-y-6">
          <Card>
            <h3 className="mb-3 text-sm font-semibold text-ink">Inspection</h3>
            {inspections.length === 0 ? (
              <EmptyState title="No inspection recorded yet" />
            ) : (
              <div className="space-y-2 text-sm">
                <StatusBadge label={inspections[0].Inspection_Status} tone={getStatusTone(inspections[0].Inspection_Status)} />
                <p className="text-muted">{formatDate(inspections[0].Inspection_Date)}</p>
              </div>
            )}
            <Link to={`/surveyor/claims/${claim.Claim_ID}/inspection`} className="mt-3 inline-block text-sm font-medium text-brand-600 hover:text-brand-700">
              Open Inspection Workspace
            </Link>
          </Card>

          <Card>
            <h3 className="mb-3 text-sm font-semibold text-ink">Vehicle Damage</h3>
            <p className="text-sm text-muted">View recorded damage assessment for this vehicle.</p>
            <Link to={`/surveyor/claims/${claim.Claim_ID}/damage`} className="mt-3 inline-block text-sm font-medium text-brand-600 hover:text-brand-700">
              View Damage Assessment
            </Link>
          </Card>

          <Card>
            <h3 className="mb-3 text-sm font-semibold text-ink">Evidence</h3>
            <p className="text-sm text-muted">{evidence.length} evidence item{evidence.length === 1 ? "" : "s"} on file.</p>
            <Link to={`/surveyor/claims/${claim.Claim_ID}/evidence`} className="mt-3 inline-block text-sm font-medium text-brand-600 hover:text-brand-700">
              View Evidence
            </Link>
          </Card>

          <Card>
            <h3 className="mb-3 text-sm font-semibold text-ink">Repair Estimate</h3>
            <p className="text-sm text-muted">
              {repair_estimates.length} repair estimate{repair_estimates.length === 1 ? "" : "s"} on file.
            </p>
            <Link to={`/surveyor/claims/${claim.Claim_ID}/repair-estimate`} className="mt-3 inline-block text-sm font-medium text-brand-600 hover:text-brand-700">
              View Repair Estimate
            </Link>
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
