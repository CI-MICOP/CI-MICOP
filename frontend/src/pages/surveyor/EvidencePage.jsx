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
import { createEvidence, getAssignedClaimDetail } from "../../services/surveyorService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatDate } from "../../utils/format";
import { getStatusTone } from "../../utils/statusTone";

// Real values from the approved dataset (see
// docs/project_documentation/SURVEYOR_DAMAGE_AND_EVIDENCE_WORKFLOW.md).
// Kept in sync with backend/app/services/evidence_upload.py.
const EVIDENCE_TYPE_OPTIONS = ["Survey Photo", "Damage Photo", "Accident Photo"];
const EVIDENCE_SOURCE_OPTIONS = ["Surveyor", "Customer"];

function emptyForm() {
  return {
    Evidence_Type: EVIDENCE_TYPE_OPTIONS[0],
    Evidence_Date: new Date().toISOString().slice(0, 10),
    Evidence_Source: EVIDENCE_SOURCE_OPTIONS[0],
    file: null,
  };
}

export default function EvidencePage() {
  const { claimId } = useParams();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm());
  const [saveState, setSaveState] = useState({ status: "idle", message: "" });

  const fetchDetail = useCallback(async () => {
    const [claim, assigned] = await Promise.all([getClaimById(claimId), getAssignedClaimDetail(claimId)]);
    return { claim, ...assigned };
  }, [claimId]);

  const { data, isLoading, error, reload } = useFetch(fetchDetail, [fetchDetail]);

  function update(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  const formValid = Boolean(form.Evidence_Date && form.file);

  async function handleUpload() {
    if (!formValid) return;
    setSaveState({ status: "saving", message: "" });
    try {
      await createEvidence(claimId, {
        evidenceType: form.Evidence_Type,
        evidenceDate: form.Evidence_Date,
        evidenceSource: form.Evidence_Source,
        file: form.file,
      });
      setSaveState({ status: "success", message: "Evidence uploaded successfully." });
      setForm(emptyForm());
      setShowForm(false);
      reload();
    } catch (err) {
      setSaveState({ status: "error", message: getApiErrorMessage(err) });
    }
  }

  if (isLoading) return <LoadingState label="Loading evidence..." />;
  if (error) {
    return (
      <div>
        <PageHeader title="Evidence" />
        <ErrorState message={getApiErrorMessage(error)} onRetry={reload} />
      </div>
    );
  }

  const { claim, evidence } = data;

  return (
    <div>
      <Breadcrumbs
        items={[
          { label: "Assigned Claims", to: "/surveyor/claims" },
          { label: claim.Claim_Number, to: `/surveyor/claims/${claim.Claim_ID}` },
          { label: "Evidence" },
        ]}
      />
      <PageHeader
        title={`Evidence — ${claim.Claim_Number}`}
        actions={
          !showForm && (
            <Button onClick={() => setShowForm(true)}>
              <Plus className="h-4 w-4" aria-hidden="true" />
              Add Evidence
            </Button>
          )
        }
      />
      <ClaimTabs claimId={claim.Claim_ID} />

      {showForm && (
        <Card className="mb-4">
          <h3 className="mb-4 text-sm font-semibold text-ink">Add Evidence</h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Evidence Type" required>
              <select className="input" value={form.Evidence_Type} onChange={(e) => update("Evidence_Type", e.target.value)}>
                {EVIDENCE_TYPE_OPTIONS.map((option) => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            </Field>
            <Field label="Evidence Date" required>
              <input
                type="date"
                className="input"
                max={new Date().toISOString().slice(0, 10)}
                value={form.Evidence_Date}
                onChange={(e) => update("Evidence_Date", e.target.value)}
              />
            </Field>
            <Field label="Evidence Source" required>
              <select className="input" value={form.Evidence_Source} onChange={(e) => update("Evidence_Source", e.target.value)}>
                {EVIDENCE_SOURCE_OPTIONS.map((option) => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            </Field>
            <Field label="File (JPG or PNG)" required>
              <input
                type="file"
                accept=".jpg,.jpeg,.png,image/jpeg,image/png"
                className="input"
                onChange={(e) => update("file", e.target.files?.[0] ?? null)}
              />
            </Field>
          </div>

          {saveState.status === "error" && <p className="mt-4 text-sm text-danger">{saveState.message}</p>}

          <div className="mt-4 flex justify-end gap-3 border-t border-border pt-4">
            <Button
              variant="secondary"
              onClick={() => {
                setShowForm(false);
                setForm(emptyForm());
                setSaveState({ status: "idle", message: "" });
              }}
            >
              Cancel
            </Button>
            <Button onClick={handleUpload} isLoading={saveState.status === "saving"} disabled={!formValid}>
              Upload Evidence
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

      {evidence.length === 0 ? (
        <Card>
          <EmptyState title="No evidence on file for this claim" />
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {evidence.map((item) => (
            <Card key={item.Evidence_ID}>
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-ink">{item.Evidence_Type}</h3>
                <StatusBadge label={item.Verification_Status} tone={getStatusTone(item.Verification_Status)} />
              </div>
              <p className="mb-3 text-xs font-medium uppercase tracking-wide text-muted">Human-Entered</p>
              <dl className="grid grid-cols-2 gap-3 text-sm">
                <Detail label="File Name" value={item.File_Name} />
                <Detail label="Date" value={formatDate(item.Evidence_Date)} />
                <Detail label="Source" value={item.Evidence_Source} />
              </dl>

              <p className="mb-3 mt-4 text-xs font-medium uppercase tracking-wide text-muted">Automated Analysis</p>
              {item.Verification_Status === "Pending" ? (
                <p className="text-sm text-muted">AI analysis pending - this file has not been analyzed yet.</p>
              ) : (
                <dl className="grid grid-cols-2 gap-3 text-sm">
                  <Detail label="Image Quality" value={item.Image_Quality} />
                  <Detail label="Vehicle Damage Detected" value={item.Vehicle_Damage_Detected ? "Yes" : "No"} />
                  <Detail label="Damage Severity" value={item.Damage_Severity} />
                  <Detail label="Location Match" value={item.Location_Match ? "Yes" : "No"} />
                  <Detail label="Duplicate Evidence" value={item.Duplicate_Evidence_Indicator ? "Yes" : "No"} />
                  <Detail label="Confidence Score" value={item.Evidence_Confidence_Score} />
                </dl>
              )}
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
