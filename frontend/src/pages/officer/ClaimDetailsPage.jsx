import { CheckCircle2 } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";

import BackButton from "../../components/common/BackButton";
import Breadcrumbs from "../../components/common/Breadcrumbs";
import Button from "../../components/common/Button";
import Card from "../../components/common/Card";
import EmptyState from "../../components/common/EmptyState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import StatusBadge from "../../components/common/StatusBadge";
import ClaimTabs from "../../components/officer/ClaimTabs";
import ClaimWorkspaceError from "../../components/officer/ClaimWorkspaceError";
import EvidenceThumbnail from "../../components/officer/EvidenceThumbnail";
import { locationStatusText, locationText } from "../../components/surveyor/captureDisplay";
import { useClaimWorkspace } from "../../hooks/useClaimWorkspace";
import { assignSurveyor, getSurveyors } from "../../services/officerService";
import { formatCurrency, formatDate, formatVehicleLabel } from "../../utils/format";
import { getStatusTone } from "../../utils/statusTone";

function getAssignSurveyorErrorMessage(error) {
  if (!error?.response) return "Unable to connect to the CI-MICOP server.";
  switch (error.response.status) {
    case 404:
      return "That claim or surveyor could not be found.";
    case 409:
      return error.response.data?.detail || "This claim already has an active surveyor assignment.";
    case 422:
      return error.response.data?.detail || "That account cannot be assigned as a surveyor.";
    default:
      return "Something went wrong while assigning the surveyor.";
  }
}

export default function OfficerClaimDetailsPage() {
  const { claimId } = useParams();
  const { data, isLoading, error, reload } = useClaimWorkspace(claimId);
  const [showAssignForm, setShowAssignForm] = useState(false);
  const [surveyors, setSurveyors] = useState(null);
  const [selectedSurveyorId, setSelectedSurveyorId] = useState("");
  const [assignState, setAssignState] = useState({ status: "idle", message: "" });

  async function openAssignForm() {
    setShowAssignForm(true);
    setAssignState({ status: "idle", message: "" });
    if (surveyors === null) {
      try {
        const list = await getSurveyors();
        setSurveyors(list);
      } catch (err) {
        setSurveyors([]);
        setAssignState({ status: "error", message: getAssignSurveyorErrorMessage(err) });
      }
    }
  }

  async function handleConfirmAssignment() {
    if (!selectedSurveyorId) return;
    setAssignState({ status: "saving", message: "" });
    try {
      await assignSurveyor(claimId, selectedSurveyorId);
      setAssignState({ status: "success", message: "Surveyor assigned successfully." });
      setShowAssignForm(false);
      setSelectedSurveyorId("");
      reload();
    } catch (err) {
      setAssignState({ status: "error", message: getAssignSurveyorErrorMessage(err) });
    }
  }

  if (isLoading) return <LoadingState label="Loading claim details..." />;
  if (error) {
    return (
      <div>
        <PageHeader title="Claim Details" />
        <BackButton fallback="/officer/claims" />
        <ClaimWorkspaceError error={error} onRetry={reload} />
      </div>
    );
  }

  const {
    claim,
    customer,
    vehicle,
    policy,
    documents,
    surveyor_inspections: inspections,
    repair_estimates: estimates,
    accidents,
    evidence,
  } = data;

  return (
    <div>
      <Breadcrumbs items={[{ label: "All Claims", to: "/officer/claims" }, { label: claim.Claim_Number }]} />
      <PageHeader title={`Claim ${claim.Claim_Number}`} subtitle={`Filed on ${formatDate(claim.Claim_Date)}`} />
      <ClaimTabs claimId={claim.Claim_ID} />
      <BackButton fallback="/officer/claims" />

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
              <Detail label="Approved Amount" value={formatCurrency(claim.Approved_Amount)} />
              <Detail label="Decision Date" value={claim.Final_Decision && claim.Final_Decision !== "Pending" ? formatDate(claim.Decision_Date) : "-"} />
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
            {accidents.length === 0 ? (
              <EmptyState title="No detailed accident information has been recorded for this claim" />
            ) : (
              accidents.map((accident) => (
                <div key={accident.Accident_ID} className={accidents.length > 1 ? "mb-6 border-b border-border pb-6 last:mb-0 last:border-0 last:pb-0" : ""}>
                  <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <Detail label="Accident Date" value={formatDate(accident.Accident_Date)} />
                    <Detail label="Accident Time" value={accident.Accident_Time?.slice(0, 5) || "-"} />
                    <Detail label="Location" value={accident.Accident_Location} />
                    <Detail label="City" value={accident.Accident_City} />
                    <Detail label="State" value={accident.Accident_State} />
                    <Detail label="Pincode" value={accident.Accident_Pincode} />
                    <Detail label="Accident Type" value={accident.Accident_Type} />
                    <Detail label="Road Type" value={accident.Road_Type_Code} />
                    <Detail label="Weather Condition" value={accident.Weather_Condition} />
                    <Detail label="Road Condition" value={accident.Road_Condition} />
                    <Detail label="Police Report Available">
                      <StatusBadge
                        label={accident.Police_Report_Available ? "Yes" : "No"}
                        tone={accident.Police_Report_Available ? "success" : "neutral"}
                      />
                    </Detail>
                    <Detail label="FIR Number" value={accident.FIR_Number || "-"} />
                    <Detail label="Third Party Involved">
                      <StatusBadge
                        label={accident.Third_Party_Involved ? "Yes" : "No"}
                        tone={accident.Third_Party_Involved ? "warning" : "neutral"}
                      />
                    </Detail>
                    <Detail label="Injury Reported">
                      <StatusBadge
                        label={accident.Injury_Reported ? "Yes" : "No"}
                        tone={accident.Injury_Reported ? "danger" : "neutral"}
                      />
                    </Detail>
                    <Detail label="Witness Available">
                      <StatusBadge
                        label={accident.Witness_Available ? "Yes" : "No"}
                        tone={accident.Witness_Available ? "success" : "neutral"}
                      />
                    </Detail>
                  </dl>
                  <div className="mt-4">
                    <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted">Description</p>
                    <p className="text-sm text-ink">{accident.Accident_Description}</p>
                  </div>
                </div>
              ))
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

          <Card>
            <h3 className="mb-4 text-sm font-semibold text-ink">Evidence</h3>
            {evidence.length === 0 ? (
              <EmptyState title="No evidence has been uploaded for this claim" />
            ) : (
              <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2" aria-label="Evidence images">
                {evidence.map((item) => (
                  <li key={item.Evidence_ID} className="overflow-hidden rounded-card border border-border bg-card" aria-label={`Evidence ${item.File_Name}`}>
                    <EvidenceThumbnail claimId={claim.Claim_ID} evidenceId={item.Evidence_ID} alt={`Evidence image ${item.File_Name}`} />
                    <dl className="space-y-1 p-3 text-xs">
                      <div className="flex flex-wrap items-center gap-2">
                        <StatusBadge label={item.Evidence_Type} tone="neutral" />
                        <StatusBadge label={item.Verification_Status} tone={getStatusTone(item.Verification_Status)} />
                      </div>
                      <div>
                        <dt className="inline font-medium text-muted">Source: </dt>
                        <dd className="inline text-ink">{item.Evidence_Source}</dd>
                      </div>
                      <div>
                        <dt className="inline font-medium text-muted">Date: </dt>
                        <dd className="inline text-ink">{formatDate(item.Evidence_Date)}</dd>
                      </div>
                      {item.capture && (
                        <div>
                          <dt className="inline font-medium text-muted">Location: </dt>
                          <dd className="inline text-ink">
                            {locationText(item.capture)} &middot; {locationStatusText(item.capture)}
                          </dd>
                        </div>
                      )}
                    </dl>
                  </li>
                ))}
              </ul>
            )}
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

          <Card>
            <h3 className="mb-3 text-sm font-semibold text-ink">Surveyor Assignment</h3>

            {inspections.length === 0 ? (
              <>
                <StatusBadge label="Not Assigned" tone="warning" />

                {!showAssignForm ? (
                  <div className="mt-3">
                    <Button size="sm" onClick={openAssignForm}>
                      Assign Surveyor
                    </Button>
                  </div>
                ) : (
                  <div className="mt-3 space-y-3">
                    <label className="block">
                      <span className="mb-1 block text-sm font-medium text-ink">Select Surveyor</span>
                      {surveyors === null ? (
                        <p className="text-sm text-muted">Loading surveyors...</p>
                      ) : surveyors.length === 0 ? (
                        <p className="text-sm text-muted">No active surveyors are available.</p>
                      ) : (
                        <select
                          className="input"
                          value={selectedSurveyorId}
                          onChange={(e) => setSelectedSurveyorId(e.target.value)}
                        >
                          <option value="">Choose a surveyor...</option>
                          {surveyors.map((s) => (
                            <option key={s.Employee_ID} value={s.Employee_ID}>
                              {s.Username} ({s.Employee_ID})
                            </option>
                          ))}
                        </select>
                      )}
                    </label>

                    {selectedSurveyorId && (
                      <p className="text-sm text-ink">
                        Assign this claim to{" "}
                        <span className="font-medium">
                          {surveyors.find((s) => s.Employee_ID === selectedSurveyorId)?.Username}
                        </span>
                        ?
                      </p>
                    )}

                    {assignState.status === "error" && <p className="text-sm text-danger">{assignState.message}</p>}

                    <div className="flex justify-end gap-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => {
                          setShowAssignForm(false);
                          setSelectedSurveyorId("");
                          setAssignState({ status: "idle", message: "" });
                        }}
                      >
                        Cancel
                      </Button>
                      <Button
                        size="sm"
                        onClick={handleConfirmAssignment}
                        isLoading={assignState.status === "saving"}
                        disabled={!selectedSurveyorId}
                      >
                        Confirm Assignment
                      </Button>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="space-y-1 text-sm">
                <p className="text-xs font-medium uppercase tracking-wide text-muted">Assigned Surveyor</p>
                <p className="text-muted">Employee ID: {inspections[0].Surveyor_ID}</p>
                <StatusBadge label={inspections[0].Inspection_Status} tone={getStatusTone(inspections[0].Inspection_Status)} />
              </div>
            )}

            {assignState.status === "success" && (
              <div className="mt-3 flex items-center gap-2 rounded-card border border-green-200 bg-green-50 p-3 text-sm text-success">
                <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                {assignState.message}
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
