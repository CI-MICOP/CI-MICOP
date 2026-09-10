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
import StatusBadge from "../../components/common/StatusBadge";
import ClaimTabs from "../../components/surveyor/ClaimTabs";
import { useFetch } from "../../hooks/useFetch";
import { getClaimById } from "../../services/claimService";
import { createRepairEstimate, getAssignedClaimDetail } from "../../services/surveyorService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatCurrency, formatDate } from "../../utils/format";
import { getStatusTone } from "../../utils/statusTone";

const EMPTY_FORM = {
  Garage_ID: "",
  Estimate_Date: new Date().toISOString().slice(0, 10),
  Repair_Estimate: "",
  Repair_Cost: "",
  Parts_Cost: "",
  Labour_Cost: "",
  Painting_Cost: "",
  Replacement_Parts_Count: "",
  Repaired_Parts_Count: "",
  Estimated_Repair_Days: "",
  Actual_Repair_Days: "",
};

const REQUIRED_NUMBER_FIELDS = [
  "Repair_Estimate",
  "Repair_Cost",
  "Parts_Cost",
  "Labour_Cost",
  "Painting_Cost",
  "Replacement_Parts_Count",
  "Repaired_Parts_Count",
  "Estimated_Repair_Days",
];

export default function RepairEstimatePage() {
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
    form.Garage_ID.trim().length > 0 &&
    Boolean(form.Estimate_Date) &&
    REQUIRED_NUMBER_FIELDS.every((field) => form[field] !== "" && Number(form[field]) >= 0);

  async function handleSaveEstimate() {
    if (!formValid) return;
    setSaveState({ status: "saving", message: "" });
    try {
      await createRepairEstimate({
        Claim_ID: claimId,
        Garage_ID: form.Garage_ID,
        Estimate_Date: form.Estimate_Date,
        Repair_Estimate: form.Repair_Estimate,
        Repair_Cost: form.Repair_Cost,
        Parts_Cost: form.Parts_Cost,
        Labour_Cost: form.Labour_Cost,
        Painting_Cost: form.Painting_Cost,
        Replacement_Parts_Count: Number(form.Replacement_Parts_Count),
        Repaired_Parts_Count: Number(form.Repaired_Parts_Count),
        Estimated_Repair_Days: Number(form.Estimated_Repair_Days),
        Actual_Repair_Days: form.Actual_Repair_Days === "" ? null : Number(form.Actual_Repair_Days),
      });
      setSaveState({ status: "success", message: "Repair estimate saved." });
      setForm(EMPTY_FORM);
      setShowForm(false);
      reload();
    } catch (err) {
      setSaveState({ status: "error", message: getApiErrorMessage(err) });
    }
  }

  if (isLoading) return <LoadingState label="Loading repair estimates..." />;
  if (error) {
    return (
      <div>
        <PageHeader title="Repair Estimate" />
        <ErrorState message={getApiErrorMessage(error)} onRetry={reload} />
      </div>
    );
  }

  const { claim, repair_estimates: estimates } = data;

  return (
    <div>
      <Breadcrumbs
        items={[
          { label: "Assigned Claims", to: "/surveyor/claims" },
          { label: claim.Claim_Number, to: `/surveyor/claims/${claim.Claim_ID}` },
          { label: "Repair Estimate" },
        ]}
      />
      <PageHeader
        title={`Repair Estimate — ${claim.Claim_Number}`}
        actions={
          !showForm && (
            <Button onClick={() => setShowForm(true)}>
              <Plus className="h-4 w-4" aria-hidden="true" />
              Add Estimate
            </Button>
          )
        }
      />
      <ClaimTabs claimId={claim.Claim_ID} />

      <Card className="mb-4">
        <h3 className="mb-3 text-sm font-semibold text-ink">Claim Summary</h3>
        <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
          <Detail label="Claim Number" value={claim.Claim_Number} />
          <Detail label="Claim Type" value={claim.Claim_Type} />
          <Detail label="Claim Amount" value={formatCurrency(claim.Claim_Amount)} />
          <Detail label="Claim Status">
            <StatusBadge label={claim.Claim_Status} tone={getStatusTone(claim.Claim_Status)} />
          </Detail>
        </dl>
      </Card>

      {showForm && (
        <Card className="mb-4">
          <h3 className="mb-4 text-sm font-semibold text-ink">Add Repair Estimate</h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Garage ID" required>
              <input
                className="input"
                maxLength={30}
                placeholder="e.g. GAR-0001"
                value={form.Garage_ID}
                onChange={(e) => update("Garage_ID", e.target.value)}
              />
            </Field>
            <Field label="Estimate Date" required>
              <input
                type="date"
                className="input"
                max={new Date().toISOString().slice(0, 10)}
                value={form.Estimate_Date}
                onChange={(e) => update("Estimate_Date", e.target.value)}
              />
            </Field>
            <Field label="Repair Estimate (INR)" required>
              <input
                type="number"
                min="0"
                step="1"
                className="input"
                value={form.Repair_Estimate}
                onChange={(e) => update("Repair_Estimate", e.target.value)}
              />
            </Field>
            <Field label="Repair Cost (INR)" required>
              <input
                type="number"
                min="0"
                step="1"
                className="input"
                value={form.Repair_Cost}
                onChange={(e) => update("Repair_Cost", e.target.value)}
              />
            </Field>
            <Field label="Parts Cost (INR)" required>
              <input
                type="number"
                min="0"
                step="1"
                className="input"
                value={form.Parts_Cost}
                onChange={(e) => update("Parts_Cost", e.target.value)}
              />
            </Field>
            <Field label="Labour Cost (INR)" required>
              <input
                type="number"
                min="0"
                step="1"
                className="input"
                value={form.Labour_Cost}
                onChange={(e) => update("Labour_Cost", e.target.value)}
              />
            </Field>
            <Field label="Painting Cost (INR)" required>
              <input
                type="number"
                min="0"
                step="1"
                className="input"
                value={form.Painting_Cost}
                onChange={(e) => update("Painting_Cost", e.target.value)}
              />
            </Field>
            <Field label="Replacement Parts Count" required>
              <input
                type="number"
                min="0"
                step="1"
                className="input"
                value={form.Replacement_Parts_Count}
                onChange={(e) => update("Replacement_Parts_Count", e.target.value)}
              />
            </Field>
            <Field label="Repaired Parts Count" required>
              <input
                type="number"
                min="0"
                step="1"
                className="input"
                value={form.Repaired_Parts_Count}
                onChange={(e) => update("Repaired_Parts_Count", e.target.value)}
              />
            </Field>
            <Field label="Estimated Repair Days" required>
              <input
                type="number"
                min="0"
                step="1"
                className="input"
                value={form.Estimated_Repair_Days}
                onChange={(e) => update("Estimated_Repair_Days", e.target.value)}
              />
            </Field>
            <Field label="Actual Repair Days">
              <input
                type="number"
                min="0"
                step="1"
                className="input"
                placeholder="Leave blank if not yet known"
                value={form.Actual_Repair_Days}
                onChange={(e) => update("Actual_Repair_Days", e.target.value)}
              />
            </Field>
          </div>

          <div className="mt-4 rounded-card border border-border bg-surface p-3">
            <p className="text-xs font-medium uppercase tracking-wide text-muted">Automated Analysis</p>
            <p className="mt-1 text-sm text-ink">AI repair-estimate analysis: Pending</p>
            <p className="mt-1 text-xs text-muted">
              The repair estimate will be analyzed later for unusual cost patterns and potential claim leakage.
            </p>
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
            <Button onClick={handleSaveEstimate} isLoading={saveState.status === "saving"} disabled={!formValid}>
              Save Repair Estimate
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

      {estimates.length === 0 ? (
        <Card>
          <EmptyState title="No repair estimate recorded for this claim" />
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {estimates.map((estimate) => (
            <Card key={estimate.Estimate_ID}>
              <h3 className="mb-3 text-sm font-semibold text-ink">{estimate.Garage_ID}</h3>
              <dl className="grid grid-cols-2 gap-3 text-sm">
                <Detail label="Estimate ID" value={estimate.Estimate_ID} />
                <Detail label="Estimate Date" value={formatDate(estimate.Estimate_Date)} />
                <Detail label="Repair Estimate" value={formatCurrency(estimate.Repair_Estimate)} />
                <Detail label="Repair Cost" value={formatCurrency(estimate.Repair_Cost)} />
                <Detail label="Parts Cost" value={formatCurrency(estimate.Parts_Cost)} />
                <Detail label="Labour Cost" value={formatCurrency(estimate.Labour_Cost)} />
                <Detail label="Painting Cost" value={formatCurrency(estimate.Painting_Cost)} />
                <Detail label="Replacement Parts" value={estimate.Replacement_Parts_Count} />
                <Detail label="Repaired Parts" value={estimate.Repaired_Parts_Count} />
                <Detail label="Estimated Days" value={estimate.Estimated_Repair_Days} />
                <Detail
                  label="Actual Days"
                  value={estimate.Actual_Repair_Days === 0 ? "Not yet available" : estimate.Actual_Repair_Days}
                />
              </dl>

              <p className="mb-2 mt-4 text-xs font-medium uppercase tracking-wide text-muted">Automated Analysis</p>
              <p className="text-sm text-muted">AI analysis pending - this estimate has not been analyzed yet.</p>
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

function Detail({ label, value, children }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-muted">{label}</dt>
      <dd className="text-ink">{children ?? value}</dd>
    </div>
  );
}
