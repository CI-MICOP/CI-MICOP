import { CheckCircle2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import Breadcrumbs from "../../components/common/Breadcrumbs";
import Button from "../../components/common/Button";
import Card from "../../components/common/Card";
import EmptyState from "../../components/common/EmptyState";
import ErrorState from "../../components/common/ErrorState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import StatusBadge from "../../components/common/StatusBadge";
import ClaimTabs from "../../components/surveyor/ClaimTabs";
import { useAuth } from "../../hooks/useAuth";
import { useFetch } from "../../hooks/useFetch";
import { getClaimById } from "../../services/claimService";
import { getAssignedClaimDetail, startInspection, updateInspection } from "../../services/surveyorService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatDate } from "../../utils/format";
import { getStatusTone } from "../../utils/statusTone";

// Real values from the approved dataset (see
// docs/project_documentation/SURVEYOR_INSPECTION_WORKFLOW.md) plus
// "Pending" - the backend's own sentinel for "not yet assessed" on a
// freshly started inspection. Kept in sync with backend/app/schemas/surveyor.py.
const VEHICLE_CONDITION_OPTIONS = ["Pending", "Good", "Fair", "Poor"];
const DAMAGE_OBSERVED_OPTIONS = ["Pending", "Yes", "No"];
const DAMAGE_SEVERITY_OPTIONS = ["Pending", "Minor", "Moderate", "Severe"];
const REPAIR_RECOMMENDATION_OPTIONS = ["Pending", "Repair", "Replace", "Total Loss"];
const INSPECTION_STATUS_OPTIONS = ["Assigned", "Scheduled", "In Progress", "Completed"];

function getStartInspectionErrorMessage(error) {
  if (!error?.response) return "Unable to connect to the CI-MICOP server.";
  switch (error.response.status) {
    case 403:
      return "You are not assigned to this claim, so an inspection cannot be started.";
    case 409:
      return "An active inspection already exists for this claim.";
    default:
      return "Something went wrong while starting the inspection.";
  }
}

export default function InspectionWorkspacePage() {
  const { claimId } = useParams();
  const { user } = useAuth();
  const [form, setForm] = useState(null);
  const [saveState, setSaveState] = useState({ status: "idle", message: "" });
  const [startState, setStartState] = useState({ status: "idle", message: "" });

  const fetchDetail = useCallback(async () => {
    const [claim, assigned] = await Promise.all([getClaimById(claimId), getAssignedClaimDetail(claimId)]);
    return { claim, ...assigned };
  }, [claimId]);

  const { data, isLoading, error, reload } = useFetch(fetchDetail, [fetchDetail]);

  // Only ever the current surveyor's own inspection - never fall back to
  // showing another surveyor's inspection findings.
  const inspection = data?.inspections.find((i) => i.Surveyor_ID === user?.Employee_ID);

  useEffect(() => {
    if (inspection) {
      setForm({
        Vehicle_Condition: inspection.Vehicle_Condition,
        Damage_Observed: inspection.Damage_Observed,
        Damage_Severity: inspection.Damage_Severity,
        Parts_Required: inspection.Parts_Required,
        Repair_Recommendation: inspection.Repair_Recommendation,
        Inspection_Status: inspection.Inspection_Status,
        Surveyor_Comments: inspection.Surveyor_Comments,
      });
    }
  }, [inspection]);

  function update(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  const formValid = form && form.Vehicle_Condition && form.Damage_Observed && Number(form.Parts_Required) >= 0;

  async function handleSave() {
    setSaveState({ status: "saving", message: "" });
    try {
      const payload = { ...form, Parts_Required: Number(form.Parts_Required) };
      await updateInspection(inspection.Inspection_ID, payload);
      setSaveState({ status: "success", message: "Inspection updated successfully." });
      reload();
    } catch (err) {
      setSaveState({ status: "error", message: getApiErrorMessage(err) });
    }
  }

  async function handleStartInspection() {
    setStartState({ status: "starting", message: "" });
    try {
      await startInspection(claimId);
      setStartState({ status: "idle", message: "" });
      reload();
    } catch (err) {
      setStartState({ status: "error", message: getStartInspectionErrorMessage(err) });
    }
  }

  if (isLoading) return <LoadingState label="Loading inspection..." />;
  if (error) {
    return (
      <div>
        <PageHeader title="Inspection Workspace" />
        <ErrorState message={getApiErrorMessage(error)} onRetry={reload} />
      </div>
    );
  }

  const { claim, accidents } = data;
  const accident = accidents[0];

  return (
    <div>
      <Breadcrumbs
        items={[
          { label: "Assigned Claims", to: "/surveyor/claims" },
          { label: claim.Claim_Number, to: `/surveyor/claims/${claim.Claim_ID}` },
          { label: "Inspection" },
        ]}
      />
      <PageHeader title={`Inspection Workspace — ${claim.Claim_Number}`} />
      <ClaimTabs claimId={claim.Claim_ID} />

      {!inspection || !form ? (
        <EmptyState
          title="Inspection has not been started yet."
          message="Once you start an inspection, you can record your findings and save your progress here."
          action={
            <div className="flex flex-col items-center gap-2">
              <Button onClick={handleStartInspection} isLoading={startState.status === "starting"}>
                Start Inspection
              </Button>
              {startState.status === "error" && <p className="text-sm text-danger">{startState.message}</p>}
            </div>
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <Card>
              <h3 className="mb-3 text-sm font-semibold text-ink">Claim Summary</h3>
              <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2 text-sm">
                <div>
                  <dt className="text-xs uppercase tracking-wide text-muted">Claim Type</dt>
                  <dd className="text-ink">{claim.Claim_Type}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-muted">Claim Status</dt>
                  <dd><StatusBadge label={claim.Claim_Status} tone={getStatusTone(claim.Claim_Status)} /></dd>
                </div>
              </dl>
            </Card>

            <Card>
              <h3 className="mb-3 text-sm font-semibold text-ink">Accident Details</h3>
              {accident ? (
                <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2 text-sm">
                  <div>
                    <dt className="text-xs uppercase tracking-wide text-muted">Location</dt>
                    <dd className="text-ink">{accident.Accident_Location}</dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase tracking-wide text-muted">Date</dt>
                    <dd className="text-ink">{formatDate(accident.Accident_Date)}</dd>
                  </div>
                </dl>
              ) : (
                <p className="text-sm text-muted">No accident record found.</p>
              )}
            </Card>

            <Card>
              <h3 className="mb-4 text-sm font-semibold text-ink">Inspection Details</h3>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field label="Inspection Date">
                  <p className="input flex items-center bg-surface text-muted">{formatDate(inspection.Inspection_Date)}</p>
                </Field>
                <Field label="Inspection Location">
                  <p className="input flex items-center bg-surface text-muted">{inspection.Inspection_Location}</p>
                </Field>
                <Field label="Vehicle Condition" required>
                  <select className="input" value={form.Vehicle_Condition} onChange={(e) => update("Vehicle_Condition", e.target.value)}>
                    {VEHICLE_CONDITION_OPTIONS.map((option) => (
                      <option key={option} value={option}>{option}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Damage Observed" required>
                  <select className="input" value={form.Damage_Observed} onChange={(e) => update("Damage_Observed", e.target.value)}>
                    {DAMAGE_OBSERVED_OPTIONS.map((option) => (
                      <option key={option} value={option}>{option}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Damage Severity">
                  <select className="input" value={form.Damage_Severity} onChange={(e) => update("Damage_Severity", e.target.value)}>
                    {DAMAGE_SEVERITY_OPTIONS.map((option) => (
                      <option key={option} value={option}>{option}</option>
                    ))}
                  </select>
                  {form.Damage_Observed === "Yes" && form.Damage_Severity === "Pending" && (
                    <p className="mt-1 text-xs text-warning">Required before the survey report can be submitted.</p>
                  )}
                </Field>
                <Field label="Parts Required" required>
                  <input type="number" min="0" className="input" value={form.Parts_Required} onChange={(e) => update("Parts_Required", e.target.value)} />
                </Field>
                <Field label="Repair Recommendation">
                  <select className="input" value={form.Repair_Recommendation} onChange={(e) => update("Repair_Recommendation", e.target.value)}>
                    {REPAIR_RECOMMENDATION_OPTIONS.map((option) => (
                      <option key={option} value={option}>{option}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Inspection Status">
                  <select className="input" value={form.Inspection_Status} onChange={(e) => update("Inspection_Status", e.target.value)}>
                    {INSPECTION_STATUS_OPTIONS.map((option) => (
                      <option key={option} value={option}>{option}</option>
                    ))}
                  </select>
                </Field>
              </div>
              <div className="mt-4">
                <Field label="Surveyor Comments">
                  <textarea
                    className="input resize-none"
                    rows={3}
                    maxLength={2000}
                    value={form.Surveyor_Comments}
                    onChange={(e) => update("Surveyor_Comments", e.target.value)}
                  />
                </Field>
              </div>

              {saveState.status === "success" && (
                <div className="mt-4 flex items-center gap-2 rounded-card border border-green-200 bg-green-50 p-3 text-sm text-success">
                  <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                  {saveState.message}
                </div>
              )}
              {saveState.status === "error" && (
                <p className="mt-4 text-sm text-danger">{saveState.message}</p>
              )}

              <div className="mt-4 flex justify-end border-t border-border pt-4">
                <Button onClick={handleSave} isLoading={saveState.status === "saving"} disabled={!formValid}>
                  Save Inspection
                </Button>
              </div>
            </Card>
          </div>

          <div className="space-y-6">
            <Card>
              <h3 className="mb-3 text-sm font-semibold text-ink">Inspection Status</h3>
              <StatusBadge label={inspection.Inspection_Status} tone={getStatusTone(inspection.Inspection_Status)} />
            </Card>
            <Card>
              <h3 className="mb-3 text-sm font-semibold text-ink">Survey Report Status</h3>
              <StatusBadge
                label={inspection.Survey_Report_Submitted ? "Submitted" : "Not Submitted"}
                tone={inspection.Survey_Report_Submitted ? "success" : "warning"}
              />
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, required, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-ink">
        {label}
        {required && <span className="text-danger"> *</span>}
      </span>
      {children}
    </label>
  );
}
