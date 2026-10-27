import { CheckCircle2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import Breadcrumbs from "../../components/common/Breadcrumbs";
import Button from "../../components/common/Button";
import Card from "../../components/common/Card";
import EmptyState from "../../components/common/EmptyState";
import ErrorState from "../../components/common/ErrorState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import StatusBadge from "../../components/common/StatusBadge";
import ClaimStepNav from "../../components/surveyor/ClaimStepNav";
import ClaimTabs from "../../components/surveyor/ClaimTabs";
import { useSurveyorClaim } from "../../components/surveyor/useSurveyorClaim";
import { CompletedStepBar, StepLockNotice } from "../../components/surveyor/WorkflowNotices";
import {
  DAMAGE_OBSERVED_VALUES,
  DAMAGE_SEVERITY_VALUES,
  INSPECTION_FIELD_LABELS,
  PENDING,
  REPAIR_RECOMMENDATION_VALUES,
  VEHICLE_CONDITION_VALUES,
  inspectionIssues,
  lockedReason,
  serverMessage,
} from "../../components/surveyor/workflowProgress";
import { closeCorrection, openCorrection, startInspection, updateInspection } from "../../services/surveyorService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatDate } from "../../utils/format";
import { getStatusTone } from "../../utils/statusTone";

// Allowed values (workflowProgress.js, mirroring backend/app/schemas/surveyor.py)
// plus "Pending" - the backend's own "not yet assessed" placeholder, which may
// be saved as a draft but never counts as complete.
const VEHICLE_CONDITION_OPTIONS = [PENDING, ...VEHICLE_CONDITION_VALUES];
const DAMAGE_OBSERVED_OPTIONS = [PENDING, ...DAMAGE_OBSERVED_VALUES];
const DAMAGE_SEVERITY_OPTIONS = [PENDING, ...DAMAGE_SEVERITY_VALUES];
const REPAIR_RECOMMENDATION_OPTIONS = [PENDING, ...REPAIR_RECOMMENDATION_VALUES];

// Inspection_Status is managed by the server ("In Progress" once findings are
// saved, "Completed" only on submission), so it is shown, not edited.
const FORM_FIELDS = [
  "Vehicle_Condition",
  "Damage_Observed",
  "Damage_Severity",
  "Parts_Required",
  "Repair_Recommendation",
  "Surveyor_Comments",
];

function formFrom(inspection) {
  const form = {};
  for (const field of FORM_FIELDS) form[field] = inspection[field] ?? "";
  form.Parts_Required = String(inspection.Parts_Required ?? "");
  return form;
}

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
  const [form, setForm] = useState(null);
  const [showErrors, setShowErrors] = useState(false);
  const [correctionState, setCorrectionState] = useState({ busy: false, error: "" });
  const [saveState, setSaveState] = useState({ status: "idle", message: "" });
  const [startState, setStartState] = useState({ status: "idle", message: "" });
  const savingRef = useRef(false);

  const { data, isLoading, error, reload, progress } = useSurveyorClaim(claimId);
  // Only ever the current surveyor's own inspection.
  const inspection = progress?.inspection;
  // Correction mode is the server's record (POST .../corrections), not a
  // browser flag - the server refuses changes to a locked step without it.
  const correcting = Boolean(progress?.corrections?.inspection);

  useEffect(() => {
    if (inspection) setForm(formFrom(inspection));
  }, [inspection]);

  // A completed step is read-only until the surveyor deliberately reopens
  // it; nothing is editable before the scheduled date or after submission.
  const editable = Boolean(progress?.canEdit) && (!progress.inspectionComplete || correcting);

  function update(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
    // A new edit makes an earlier "saved" message out of date.
    setSaveState((prev) => (prev.status === "success" ? { status: "idle", message: "" } : prev));
  }

  const issues = form ? inspectionIssues(form) : [];
  const errorFor = (field) => (showErrors ? issues.find((issue) => issue.field === field)?.message : undefined);
  const isDirty =
    editable && Boolean(form && inspection) && FORM_FIELDS.some((field) => String(form[field]) !== String(formFrom(inspection)[field]));

  // Saves the form (drafts with "Pending" values are allowed). Returns true
  // only when the server confirmed the save.
  async function save() {
    if (savingRef.current) return false;
    const invalid = issues.filter((issue) => issue.kind === "invalid");
    if (invalid.length) {
      setShowErrors(true);
      setSaveState({ status: "error", message: "Fix the highlighted fields before saving." });
      return false;
    }
    savingRef.current = true;
    setSaveState({ status: "saving", message: "" });
    try {
      await updateInspection(inspection.Inspection_ID, { ...form, Parts_Required: Number(form.Parts_Required) });
      setSaveState({ status: "success", message: "Inspection updated successfully." });
      reload(); // the server ends a correction once its change is saved
      return true;
    } catch (err) {
      setSaveState({ status: "error", message: serverMessage(err, getApiErrorMessage(err)) });
      return false;
    } finally {
      savingRef.current = false;
    }
  }

  async function handleNext() {
    if (!editable) return true; // read-only: already complete on the server
    setShowErrors(true);
    if (issues.length) {
      const fields = [...new Set(issues.map((issue) => INSPECTION_FIELD_LABELS[issue.field]))];
      return `Complete the required inspection details before continuing: ${fields.join(", ")}.`;
    }
    if (isDirty || !progress.inspectionComplete) {
      const saved = await save();
      if (!saved) return "The inspection could not be saved, so you cannot continue yet. Please try again.";
    }
    return true;
  }

  async function changeCorrection(open) {
    setCorrectionState({ busy: true, error: "" });
    try {
      if (open) await openCorrection(inspection.Inspection_ID, "inspection");
      else await closeCorrection(inspection.Inspection_ID, "inspection");
      setCorrectionState({ busy: false, error: "" });
      if (!open) {
        setForm(formFrom(inspection));
        setShowErrors(false);
      }
      reload();
    } catch (err) {
      setCorrectionState({ busy: false, error: serverMessage(err, getApiErrorMessage(err)) });
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

  let blockedReason = "";
  if (!inspection) blockedReason = "Start the inspection first.";
  else if (!progress.submitted && !progress.canEdit) blockedReason = lockedReason(progress);
  else if (editable && issues.length) {
    const fields = [...new Set(issues.map((issue) => INSPECTION_FIELD_LABELS[issue.field]))];
    blockedReason = `Complete the required fields to continue: ${fields.join(", ")}.`;
  }

  return (
    <div>
      <Breadcrumbs
        items={[
          { label: "Assigned Inspections", to: "/surveyor/claims" },
          { label: claim.Claim_Number, to: `/surveyor/claims/${claim.Claim_ID}` },
          { label: "Inspection" },
        ]}
      />
      <PageHeader title={`Inspection Workspace — ${claim.Claim_Number}`} />
      <ClaimTabs claimId={claim.Claim_ID} progress={progress} hasUnsavedChanges={isDirty} />

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

            {!progress.submitted && !progress.scheduleReached && <StepLockNotice progress={progress} claimId={claim.Claim_ID} />}

            <Card>
              <h3 className="mb-3 text-sm font-semibold text-ink">Inspection Details</h3>
              {(progress.submitted || (progress.canEdit && progress.inspectionComplete)) && (
                <CompletedStepBar
                  submitted={progress.submitted}
                  correcting={correcting}
                  onCorrect={() => changeCorrection(true)}
                  onFinishCorrecting={isDirty ? undefined : () => changeCorrection(false)}
                  busy={correctionState.busy}
                  error={correctionState.error}
                >
                  Inspection details are complete and saved.
                </CompletedStepBar>
              )}
              {editable && (
                <p className="mb-4 text-xs text-muted">
                  Fields marked <span className="text-danger">*</span> are required before you can continue to Vehicle
                  Damage. You can save a draft with &quot;Pending&quot; values at any time.
                </p>
              )}
              <fieldset disabled={!editable} className="min-w-0">
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <Field label="Inspection Date">
                    <p className="input flex items-center bg-surface text-muted">{formatDate(inspection.Inspection_Date)}</p>
                  </Field>
                  <Field label="Inspection Location">
                    <p className="input flex items-center bg-surface text-muted">{inspection.Inspection_Location}</p>
                  </Field>
                  <SelectField label="Vehicle Condition" required field="Vehicle_Condition" options={VEHICLE_CONDITION_OPTIONS} form={form} update={update} error={errorFor("Vehicle_Condition")} />
                  <SelectField label="Damage Observed" required field="Damage_Observed" options={DAMAGE_OBSERVED_OPTIONS} form={form} update={update} error={errorFor("Damage_Observed")} />
                  <SelectField
                    label="Damage Severity"
                    required={form.Damage_Observed === "Yes"}
                    field="Damage_Severity"
                    options={DAMAGE_SEVERITY_OPTIONS}
                    form={form}
                    update={update}
                    error={errorFor("Damage_Severity")}
                  />
                  <Field label="Parts Required" required error={errorFor("Parts_Required")}>
                    <input
                      type="number"
                      min="0"
                      step="1"
                      className="input"
                      aria-invalid={Boolean(errorFor("Parts_Required"))}
                      value={form.Parts_Required}
                      onChange={(e) => update("Parts_Required", e.target.value)}
                    />
                  </Field>
                  <SelectField label="Repair Recommendation" required field="Repair_Recommendation" options={REPAIR_RECOMMENDATION_OPTIONS} form={form} update={update} error={errorFor("Repair_Recommendation")} />
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
              </fieldset>

              {saveState.status === "success" && (
                <div className="mt-4 flex items-center gap-2 rounded-card border border-green-200 bg-green-50 p-3 text-sm text-success">
                  <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                  {saveState.message}
                </div>
              )}
              {saveState.status === "error" && (
                <p role="alert" className="mt-4 text-sm text-danger">{saveState.message}</p>
              )}

              {editable && (
                <div className="mt-4 flex justify-end border-t border-border pt-4">
                  <Button onClick={save} isLoading={saveState.status === "saving"}>
                    Save Inspection
                  </Button>
                </div>
              )}
            </Card>
          </div>

          <div className="space-y-6">
            <Card>
              <h3 className="mb-3 text-sm font-semibold text-ink">Inspection Status</h3>
              <StatusBadge label={inspection.Inspection_Status} tone={getStatusTone(inspection.Inspection_Status)} />
              {progress.schedule && (
                <p className="mt-3 text-xs text-muted">Scheduled for {formatDate(progress.schedule.scheduled_date)} (IST)</p>
              )}
            </Card>
          </div>
        </div>
      )}
      <ClaimStepNav
        claimId={claim.Claim_ID}
        current="inspection"
        onNext={handleNext}
        hasUnsavedChanges={isDirty}
        blockedReason={blockedReason}
      />
    </div>
  );
}

function Field({ label, required, error, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-ink">
        {label}
        {required && <span className="text-danger"> *</span>}
      </span>
      {children}
      {error && <span className="mt-1 block text-xs text-danger">{error}</span>}
    </label>
  );
}

// A stored value that is not one of the allowed options (for example older
// sample data) is shown as it is and marked invalid, not silently displayed
// as the first option.
function SelectField({ label, required, field, options, form, update, error }) {
  const value = form[field];
  const unknown = value !== "" && !options.includes(value);
  return (
    <Field label={label} required={required} error={error}>
      <select className="input" aria-invalid={Boolean(error)} value={value} onChange={(e) => update(field, e.target.value)}>
        {unknown && (
          <option value={value} disabled>
            {value} (not a valid option)
          </option>
        )}
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </Field>
  );
}
