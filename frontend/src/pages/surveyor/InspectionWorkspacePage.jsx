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
import { getAssignedClaimDetail, updateInspection } from "../../services/surveyorService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatDate } from "../../utils/format";
import { getStatusTone } from "../../utils/statusTone";

export default function InspectionWorkspacePage() {
  const { claimId } = useParams();
  const { user } = useAuth();
  const [form, setForm] = useState(null);
  const [saveState, setSaveState] = useState({ status: "idle", message: "" });

  const fetchDetail = useCallback(async () => {
    const [claim, assigned] = await Promise.all([getClaimById(claimId), getAssignedClaimDetail(claimId)]);
    return { claim, ...assigned };
  }, [claimId]);

  const { data, isLoading, error, reload } = useFetch(fetchDetail, [fetchDetail]);

  const inspection = data?.inspections.find((i) => i.Surveyor_ID === user?.Employee_ID) ?? data?.inspections[0];

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
        <EmptyState title="No inspection record exists for this claim" message="There is nothing to update here yet." />
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
                <Field label="Vehicle Condition">
                  <input className="input" value={form.Vehicle_Condition} onChange={(e) => update("Vehicle_Condition", e.target.value)} />
                </Field>
                <Field label="Damage Observed">
                  <select className="input" value={form.Damage_Observed} onChange={(e) => update("Damage_Observed", e.target.value)}>
                    <option value="Yes">Yes</option>
                    <option value="No">No</option>
                  </select>
                </Field>
                <Field label="Damage Severity">
                  <input className="input" value={form.Damage_Severity} onChange={(e) => update("Damage_Severity", e.target.value)} />
                </Field>
                <Field label="Parts Required">
                  <input type="number" min="0" className="input" value={form.Parts_Required} onChange={(e) => update("Parts_Required", e.target.value)} />
                </Field>
                <Field label="Repair Recommendation">
                  <input className="input" value={form.Repair_Recommendation} onChange={(e) => update("Repair_Recommendation", e.target.value)} />
                </Field>
                <Field label="Inspection Status">
                  <input className="input" value={form.Inspection_Status} onChange={(e) => update("Inspection_Status", e.target.value)} />
                </Field>
              </div>
              <div className="mt-4">
                <Field label="Surveyor Comments">
                  <textarea className="input resize-none" rows={3} value={form.Surveyor_Comments} onChange={(e) => update("Surveyor_Comments", e.target.value)} />
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
                <Button onClick={handleSave} isLoading={saveState.status === "saving"}>
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

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-ink">{label}</span>
      {children}
    </label>
  );
}
