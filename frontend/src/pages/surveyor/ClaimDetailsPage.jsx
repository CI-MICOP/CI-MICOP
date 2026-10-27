import { CalendarClock, Info } from "lucide-react";
import { useParams } from "react-router-dom";

import Breadcrumbs from "../../components/common/Breadcrumbs";
import Card from "../../components/common/Card";
import EmptyState from "../../components/common/EmptyState";
import ErrorState from "../../components/common/ErrorState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import StatusBadge from "../../components/common/StatusBadge";
import ClaimDocumentsPanel from "../../components/surveyor/ClaimDocumentsPanel";
import ClaimStepNav from "../../components/surveyor/ClaimStepNav";
import ClaimTabs from "../../components/surveyor/ClaimTabs";
import { useSurveyorClaim } from "../../components/surveyor/useSurveyorClaim";
import { lockedReason } from "../../components/surveyor/workflowProgress";
import { getApiErrorMessage } from "../../utils/errors";
import { formatCurrency, formatDate } from "../../utils/format";
import { getStatusTone } from "../../utils/statusTone";

export default function SurveyorClaimDetailsPage() {
  const { claimId } = useParams();
  // Read-only for the surveyor: nothing on this page can be edited.
  const { data, isLoading, error, reload, progress } = useSurveyorClaim(claimId);

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

  const { claim, accidents } = data;
  const accident = accidents[0];

  return (
    <div>
      <Breadcrumbs items={[{ label: "Assigned Inspections", to: "/surveyor/claims" }, { label: claim.Claim_Number }]} />
      <PageHeader title={`Claim ${claim.Claim_Number}`} subtitle={`Filed on ${formatDate(claim.Claim_Date)}`} />
      <ClaimTabs claimId={claim.Claim_ID} progress={progress} />

      {progress.workflow && !progress.submitted && (
        <p
          className={`mb-4 flex items-start gap-2 rounded-card border p-3 text-sm ${
            progress.scheduleReached ? "border-brand-100 bg-brand-50 text-brand-800" : "border-amber-200 bg-amber-50 text-amber-900"
          }`}
        >
          <CalendarClock className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          {progress.scheduleReached
            ? `Inspection scheduled for ${formatDate(progress.schedule.scheduled_date)} - you can record the inspection now.`
            : progress.schedule.message}
        </p>
      )}

      <div className="space-y-6">
        <Card>
          <h3 className="mb-4 text-sm font-semibold text-ink">Claim Information</h3>
          <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
            <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
              <div className="sm:col-span-2 lg:col-span-3">
                <dt className="text-xs font-medium uppercase tracking-wide text-muted">Description</dt>
                <dd className="mt-0.5 text-sm text-ink">{accident.Accident_Description}</dd>
              </div>
            </dl>
          )}
        </Card>

        {/* Locked until the scheduled inspection date - the server enforces the same rule. */}
        <ClaimDocumentsPanel claimId={claim.Claim_ID} progress={progress} />
      </div>
      <ClaimStepNav
        claimId={claim.Claim_ID}
        current="details"
        blockedReason={progress.unlocked.has("inspection") ? "" : lockedReason(progress)}
      />
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
