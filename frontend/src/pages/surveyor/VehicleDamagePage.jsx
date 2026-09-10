import { CheckCircle2, Plus } from "lucide-react";
import { useCallback, useState } from "react";
import { useParams } from "react-router-dom";

import Breadcrumbs from "../../components/common/Breadcrumbs";
import Button from "../../components/common/Button";
import Card from "../../components/common/Card";
import EmptyState from "../../components/common/EmptyState";
import ErrorState from "../../components/common/ErrorState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import ClaimTabs from "../../components/surveyor/ClaimTabs";
import { useFetch } from "../../hooks/useFetch";
import { getClaimById } from "../../services/claimService";
import { createVehicleDamage, getAssignedClaimDetail } from "../../services/surveyorService";
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
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saveState, setSaveState] = useState({ status: "idle", message: "" });

  const fetchDetail = useCallback(async () => {
    const [claim, assigned] = await Promise.all([getClaimById(claimId), getAssignedClaimDetail(claimId)]);
    return { claim, ...assigned };
  }, [claimId]);

  const { data, isLoading, error, reload } = useFetch(fetchDetail, [fetchDetail]);

  function update(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  const formValid =
    form.Damaged_Part.trim().length > 0 &&
    form.Damage_Description.trim().length > 0 &&
    Number(form.Estimated_Damage_Cost) >= 0 &&
    form.Estimated_Damage_Cost !== "";

  async function handleAddDamage() {
    if (!formValid) return;
    setSaveState({ status: "saving", message: "" });
    try {
      await createVehicleDamage({ Claim_ID: claimId, ...form, Estimated_Damage_Cost: form.Estimated_Damage_Cost });
      setSaveState({ status: "success", message: "Damage record saved." });
      setForm(EMPTY_FORM);
      setShowForm(false);
      reload();
    } catch (err) {
      setSaveState({ status: "error", message: getApiErrorMessage(err) });
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

  const { claim, vehicle_damage: damages } = data;

  return (
    <div>
      <Breadcrumbs
        items={[
          { label: "Assigned Claims", to: "/surveyor/claims" },
          { label: claim.Claim_Number, to: `/surveyor/claims/${claim.Claim_ID}` },
          { label: "Vehicle Damage" },
        ]}
      />
      <PageHeader
        title={`Vehicle Damage Assessment — ${claim.Claim_Number}`}
        actions={
          !showForm && (
            <Button onClick={() => setShowForm(true)}>
              <Plus className="h-4 w-4" aria-hidden="true" />
              Add Damage
            </Button>
          )
        }
      />
      <ClaimTabs claimId={claim.Claim_ID} />

      {showForm && (
        <Card className="mb-4">
          <h3 className="mb-4 text-sm font-semibold text-ink">Add Damage Record</h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Damage Type" required>
              <select className="input" value={form.Damage_Type} onChange={(e) => update("Damage_Type", e.target.value)}>
                {DAMAGE_TYPE_OPTIONS.map((option) => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            </Field>
            <Field label="Damaged Part" required>
              <input
                className="input"
                maxLength={50}
                placeholder="e.g. Front Bumper"
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
            <Field label="Estimated Damage Cost (INR)" required>
              <input
                type="number"
                min="0"
                step="1"
                className="input"
                placeholder="e.g. 15000"
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
            <Field label="Damage Description" required>
              <textarea
                className="input resize-none"
                rows={3}
                maxLength={1000}
                placeholder="Describe the damage observed"
                value={form.Damage_Description}
                onChange={(e) => update("Damage_Description", e.target.value)}
              />
            </Field>
          </div>

          {saveState.status === "error" && <p className="mt-4 text-sm text-danger">{saveState.message}</p>}

          <div className="mt-4 flex justify-end gap-3 border-t border-border pt-4">
            <Button
              variant="secondary"
              onClick={() => {
                setShowForm(false);
                setForm(EMPTY_FORM);
                setSaveState({ status: "idle", message: "" });
              }}
            >
              Cancel
            </Button>
            <Button onClick={handleAddDamage} isLoading={saveState.status === "saving"} disabled={!formValid}>
              Save Damage Record
            </Button>
          </div>
        </Card>
      )}

      {saveState.status === "success" && !showForm && (
        <div className="mb-4 flex items-center gap-2 rounded-card border border-green-200 bg-green-50 p-3 text-sm text-success">
          <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
          {saveState.message}
        </div>
      )}

      {damages.length === 0 ? (
        <Card>
          <EmptyState title="No damage assessment recorded for this vehicle" />
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {damages.map((damage) => (
            <Card key={damage.Damage_ID}>
              <h3 className="mb-3 text-sm font-semibold text-ink">{damage.Damaged_Part}</h3>
              <dl className="grid grid-cols-2 gap-3 text-sm">
                <Detail label="Damage Type" value={damage.Damage_Type} />
                <Detail label="Severity" value={damage.Damage_Severity} />
                <Detail label="Location" value={damage.Damage_Location} />
                <Detail label="Repair or Replace" value={damage.Repair_or_Replace} />
                <Detail label="Estimated Cost" value={formatCurrency(damage.Estimated_Damage_Cost)} />
                <Detail label="Photo Evidence" value={damage.Photo_Evidence_Available ? "Available" : "Not available"} />
              </dl>
              <div className="mt-3">
                <p className="text-xs font-medium uppercase tracking-wide text-muted">Description</p>
                <p className="mt-0.5 text-sm text-ink">{damage.Damage_Description}</p>
              </div>
            </Card>
          ))}
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

function Detail({ label, value }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-muted">{label}</dt>
      <dd className="text-ink">{value}</dd>
    </div>
  );
}
