import { CheckCircle2, Plus } from "lucide-react";
import { useRef, useState } from "react";
import { useParams } from "react-router-dom";

import Breadcrumbs from "../../components/common/Breadcrumbs";
import Button from "../../components/common/Button";
import Card from "../../components/common/Card";
import DataTable from "../../components/common/DataTable";
import ErrorState from "../../components/common/ErrorState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import ClaimStepNav from "../../components/surveyor/ClaimStepNav";
import ClaimTabs from "../../components/surveyor/ClaimTabs";
import { useSurveyorClaim } from "../../components/surveyor/useSurveyorClaim";
import { CompletedStepBar, StepLockNotice } from "../../components/surveyor/WorkflowNotices";
import { damageIssues, lockedReason, serverMessage } from "../../components/surveyor/workflowProgress";
import { closeCorrection, createVehicleDamage, openCorrection } from "../../services/surveyorService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatCurrency } from "../../utils/format";

// Real values from the approved dataset (see
// docs/project_documentation/SURVEYOR_DAMAGE_AND_EVIDENCE_WORKFLOW.md).
// Kept in sync with backend/app/schemas/surveyor.py.
const DAMAGE_TYPE_OPTIONS = [
  "Side Damage",
  "Rear Damage",
  "Multiple Damage",
  "Front Damage",
  "Glass Damage",
  "Engine Damage",
  "Total Loss",
];
const DAMAGE_SEVERITY_OPTIONS = ["Minor", "Moderate", "Severe"];
const DAMAGE_LOCATION_OPTIONS = ["Left", "Right", "Front", "Rear", "Multiple"];
const REPAIR_OR_REPLACE_OPTIONS = ["Repair", "Replace"];

const EMPTY_FORM = {
  Damage_Type: DAMAGE_TYPE_OPTIONS[0],
  Damaged_Part: "",
  Damage_Severity: DAMAGE_SEVERITY_OPTIONS[0],
  Damage_Location: DAMAGE_LOCATION_OPTIONS[0],
  Estimated_Damage_Cost: "",
  Repair_or_Replace: REPAIR_OR_REPLACE_OPTIONS[0],
  Photo_Evidence_Available: false,
  Damage_Description: "",
};

export default function VehicleDamagePage() {
  const { claimId } = useParams();
  // "Add another" form the surveyor opened themselves (the first required
  // record's form opens on its own).
  const [formRequested, setFormRequested] = useState(false);
  // Adding further records stays available right after a save on this
  // visit; after leaving, the completed step is reopened via "Correct".
  const [justSaved, setJustSaved] = useState(false);
  const [correctionState, setCorrectionState] = useState({ busy: false, error: "" });
  const [form, setForm] = useState(EMPTY_FORM);
  const [showErrors, setShowErrors] = useState(false);
  const [saveState, setSaveState] = useState({ status: "idle", message: "" });
  const savingRef = useRef(false);

  const { data, isLoading, error, reload, progress } = useSurveyorClaim(claimId);
  // Correction mode is the server's record, not a browser flag.
  const correcting = Boolean(progress?.corrections?.damage);
  const damages = data?.vehicle_damage ?? [];
  const usable = Boolean(progress?.unlocked.has("damage")) && Boolean(progress?.canEdit);
  const formRequired = usable && progress.damageRequired && progress.damageCount === 0;
  const showForm = usable && (formRequired || formRequested);
  const canAddMore = usable && !formRequired && (justSaved || correcting || !progress.damageComplete);

  function update(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  const issues = damageIssues(form);
  const errorFor = (field) => (showErrors ? issues.find((issue) => issue.field === field)?.message : undefined);
  const isDirty = showForm && Object.keys(EMPTY_FORM).some((key) => form[key] !== EMPTY_FORM[key]);

  function openForm() {
    setFormRequested(true);
    setShowErrors(false);
    setSaveState({ status: "idle", message: "" });
  }

  function closeForm() {
    setFormRequested(false);
    setForm(EMPTY_FORM);
    setShowErrors(false);
    setSaveState({ status: "idle", message: "" });
  }

  async function handleAddDamage() {
    if (savingRef.current) return;
    setShowErrors(true);
    if (issues.length) return;
    savingRef.current = true;
    setSaveState({ status: "saving", message: "" });
    try {
      await createVehicleDamage({ Claim_ID: claimId, ...form, Estimated_Damage_Cost: form.Estimated_Damage_Cost });
      setSaveState({ status: "success", message: "Damage record saved." });
      setForm(EMPTY_FORM);
      setFormRequested(false);
      setJustSaved(true);
      setShowErrors(false);
      reload();
    } catch (err) {
      // The form stays open with its input, so the surveyor can retry.
      setSaveState({ status: "error", message: serverMessage(err, getApiErrorMessage(err)) });
    } finally {
      savingRef.current = false;
    }
  }

  if (isLoading) return <LoadingState label="Loading damage assessment..." />;
  if (error) {
    return (
      <div>
        <PageHeader title="Vehicle Damage Assessment" />
        <ErrorState message={getApiErrorMessage(error)} onRetry={reload} />
      </div>
    );
  }

  const { claim } = data;
  const locked = !progress.unlocked.has("damage");

  async function changeCorrection(open) {
    setCorrectionState({ busy: true, error: "" });
    try {
      const inspectionId = progress.inspection.Inspection_ID;
      if (open) await openCorrection(inspectionId, "damage");
      else await closeCorrection(inspectionId, "damage");
      setCorrectionState({ busy: false, error: "" });
      if (!open) closeForm();
      reload();
    } catch (err) {
      setCorrectionState({ busy: false, error: serverMessage(err, getApiErrorMessage(err)) });
    }
  }

  async function handleNext() {
    if (isDirty) return "Save the damage record you are adding before continuing.";
    if (formRequested) closeForm();
    if (correcting) {
      // Moving on ends the correction (the server re-checks later steps).
      try {
        await closeCorrection(progress.inspection.Inspection_ID, "damage");
      } catch (err) {
        return serverMessage(err, "The correction could not be closed. Please try again.");
      }
    }
    return true;
  }

  let blockedReason = "";
  if (locked) blockedReason = lockedReason(progress);
  else if (!progress.submitted && isDirty) blockedReason = "Save the damage record you are adding before continuing.";
  else if (!progress.submitted && !progress.damageComplete) {
    blockedReason = "Damage was observed during the inspection - save at least one damage record to continue.";
  }

  return (
    <div>
      <Breadcrumbs
        items={[
          { label: "Assigned Inspections", to: "/surveyor/claims" },
          { label: claim.Claim_Number, to: `/surveyor/claims/${claim.Claim_ID}` },
          { label: "Vehicle Damage" },
        ]}
      />
      <PageHeader title={`Vehicle Damage Assessment — ${claim.Claim_Number}`} />
      <ClaimTabs claimId={claim.Claim_ID} progress={progress} hasUnsavedChanges={isDirty} />

      {locked ? (
        <StepLockNotice progress={progress} claimId={claim.Claim_ID} />
      ) : (
        <>
          {(progress.submitted || (progress.damageComplete && !justSaved)) && (
            <CompletedStepBar
              submitted={progress.submitted}
              correcting={correcting}
              onCorrect={() => changeCorrection(true)}
              onFinishCorrecting={isDirty ? undefined : () => changeCorrection(false)}
              busy={correctionState.busy}
              error={correctionState.error}
            >
              {progress.damageRequired
                ? "Vehicle damage is recorded."
                : "No damage was observed during the inspection, so a damage record is not required."}
            </CompletedStepBar>
          )}

          {saveState.status === "success" && !showForm && (
            <div className="mb-4 flex items-center gap-2 rounded-card border border-green-200 bg-green-50 p-3 text-sm text-success">
              <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
              {saveState.message}
            </div>
          )}

          {damages.length > 0 && (
            <Card className="mb-4">
              <h3 className="mb-4 text-sm font-semibold text-ink">Saved Damage Records</h3>
              <DataTable
                rows={damages}
                rowKey="Damage_ID"
                columns={[
                  { key: "part", header: "Damaged Part", render: (d) => d.Damaged_Part },
                  { key: "type", header: "Type", render: (d) => d.Damage_Type },
                  { key: "severity", header: "Severity", render: (d) => d.Damage_Severity },
                  { key: "location", header: "Location", render: (d) => d.Damage_Location },
                  { key: "action", header: "Repair / Replace", render: (d) => d.Repair_or_Replace },
                  { key: "cost", header: "Estimated Cost", render: (d) => formatCurrency(d.Estimated_Damage_Cost) },
                  { key: "photo", header: "Photo", render: (d) => (d.Photo_Evidence_Available ? "Yes" : "No") },
                  { key: "description", header: "Description", render: (d) => d.Damage_Description },
                ]}
              />
            </Card>
          )}

          {showForm && (
            <Card className="mb-4">
              <h3 className="mb-1 text-sm font-semibold text-ink">
                {damages.length > 0 ? "Add Another Damage Record" : "Add Damage Record"}
              </h3>
              <p className="mb-4 text-xs text-muted">
                {formRequired && "Damage was observed during the inspection - save at least one damage record to continue. "}
                All fields marked <span className="text-danger">*</span> are required.
              </p>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field label="Damage Type" required>
                  <select className="input" value={form.Damage_Type} onChange={(e) => update("Damage_Type", e.target.value)}>
                    {DAMAGE_TYPE_OPTIONS.map((option) => (
                      <option key={option} value={option}>{option}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Damaged Part" required error={errorFor("Damaged_Part")}>
                  <input
                    className="input"
                    maxLength={50}
                    placeholder="e.g. Front Bumper"
                    aria-invalid={Boolean(errorFor("Damaged_Part"))}
                    value={form.Damaged_Part}
                    onChange={(e) => update("Damaged_Part", e.target.value)}
                  />
                </Field>
                <Field label="Damage Severity" required>
                  <select className="input" value={form.Damage_Severity} onChange={(e) => update("Damage_Severity", e.target.value)}>
                    {DAMAGE_SEVERITY_OPTIONS.map((option) => (
                      <option key={option} value={option}>{option}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Damage Location" required>
                  <select className="input" value={form.Damage_Location} onChange={(e) => update("Damage_Location", e.target.value)}>
                    {DAMAGE_LOCATION_OPTIONS.map((option) => (
                      <option key={option} value={option}>{option}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Estimated Damage Cost (INR)" required error={errorFor("Estimated_Damage_Cost")}>
                  <input
                    type="number"
                    min="0"
                    step="1"
                    className="input"
                    placeholder="e.g. 15000"
                    aria-invalid={Boolean(errorFor("Estimated_Damage_Cost"))}
                    value={form.Estimated_Damage_Cost}
                    onChange={(e) => update("Estimated_Damage_Cost", e.target.value)}
                  />
                </Field>
                <Field label="Repair or Replace" required>
                  <select className="input" value={form.Repair_or_Replace} onChange={(e) => update("Repair_or_Replace", e.target.value)}>
                    {REPAIR_OR_REPLACE_OPTIONS.map((option) => (
                      <option key={option} value={option}>{option}</option>
                    ))}
                  </select>
                </Field>
              </div>
              <div className="mt-4">
                <label className="flex items-center gap-2 text-sm text-ink">
                  <input
                    type="checkbox"
                    checked={form.Photo_Evidence_Available}
                    onChange={(e) => update("Photo_Evidence_Available", e.target.checked)}
                  />
                  Photo evidence available
                </label>
              </div>
              <div className="mt-4">
                <Field label="Damage Description" required error={errorFor("Damage_Description")}>
                  <textarea
                    className="input resize-none"
                    rows={3}
                    maxLength={1000}
                    placeholder="Describe the damage observed"
                    aria-invalid={Boolean(errorFor("Damage_Description"))}
                    value={form.Damage_Description}
                    onChange={(e) => update("Damage_Description", e.target.value)}
                  />
                </Field>
              </div>

              {saveState.status === "error" && <p role="alert" className="mt-4 text-sm text-danger">{saveState.message}</p>}

              <div className="mt-4 flex justify-end gap-3 border-t border-border pt-4">
                {formRequested && !formRequired && (
                  <Button variant="secondary" onClick={closeForm} disabled={saveState.status === "saving"}>
                    Cancel
                  </Button>
                )}
                <Button onClick={handleAddDamage} isLoading={saveState.status === "saving"}>
                  Save Damage Record
                </Button>
              </div>
            </Card>
          )}

          {!showForm && canAddMore && (
            <Button variant="secondary" onClick={openForm}>
              <Plus className="h-4 w-4" aria-hidden="true" />
              {damages.length > 0 ? "Add another damage record" : "Add a damage record (optional)"}
            </Button>
          )}
        </>
      )}
      <ClaimStepNav
        claimId={claim.Claim_ID}
        current="damage"
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
