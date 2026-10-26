import { AlertTriangle, CheckCircle2, Loader2, RotateCcw } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import Button from "../../components/common/Button";
import Card from "../../components/common/Card";
import EmptyState from "../../components/common/EmptyState";
import ErrorState from "../../components/common/ErrorState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import StatusBadge from "../../components/common/StatusBadge";
import DocumentUploadGrid from "../../components/customer/DocumentUploadGrid";
import { missingRequiredCopies, selectedUploadItems } from "../../components/customer/documentCategories";
import { useFetch } from "../../hooks/useFetch";
import { createClaim } from "../../services/claimService";
import { uploadDocument } from "../../services/documentService";
import { getMyPolicies } from "../../services/policyService";
import { getMyVehicles } from "../../services/vehicleService";
import { getApiErrorMessage, getUploadErrorMessage } from "../../utils/errors";
import { formatVehicleLabel } from "../../utils/format";
import { getStatusTone } from "../../utils/statusTone";

const STEPS = ["Incident Details", "Vehicle & Policy", "Upload Documents", "Review & Submit"];

const CLAIM_TYPES = ["Own Damage", "Third Party", "Theft"];

function StepIndicator({ currentStep }) {
  return (
    <ol className="mb-6 flex items-center">
      {STEPS.map((label, index) => {
        const stepNumber = index + 1;
        const isComplete = stepNumber < currentStep;
        const isCurrent = stepNumber === currentStep;
        return (
          <li key={label} className="flex flex-1 items-center last:flex-none">
            <div className="flex flex-col items-center gap-1.5 text-center">
              <span
                className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold ${
                  isComplete
                    ? "bg-brand-600 text-white"
                    : isCurrent
                      ? "bg-brand-100 text-brand-700 ring-2 ring-brand-500"
                      : "bg-surface text-muted"
                }`}
              >
                {isComplete ? <CheckCircle2 className="h-4 w-4" aria-hidden="true" /> : stepNumber}
              </span>
              <span className={`w-24 text-xs ${isCurrent ? "font-medium text-ink" : "text-muted"}`}>{label}</span>
            </div>
            {stepNumber < STEPS.length && <div className="mx-2 h-px flex-1 bg-border" />}
          </li>
        );
      })}
    </ol>
  );
}

const EMPTY_INCIDENT = {
  incidentDate: "",
  incidentTime: "",
  placeOfAccident: "",
  accidentPincode: "",
  description: "",
  policeStation: "",
  firNumber: "",
  thirdPartyInvolved: "no",
  injuryReported: "no",
  claimType: "",
  claimAmount: "",
};

function getSubmitErrorMessage(error) {
  if (!error?.response) {
    return "Unable to connect to the CI-MICOP server. Please try again.";
  }
  switch (error.response.status) {
    case 400:
      return "The selected vehicle does not match the selected policy. Please go back and re-check your selection.";
    case 403:
      return "You do not have permission to file a claim against this vehicle or policy.";
    case 422:
      return "Some information is missing or invalid. Please review your entries and try again.";
    default:
      return "Something went wrong while submitting your claim. Please try again.";
  }
}

function formatFileSize(bytes) {
  if (typeof bytes !== "number") return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function NewClaimPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [incident, setIncident] = useState(EMPTY_INCIDENT);
  const [vehicleId, setVehicleId] = useState("");
  const [policyId, setPolicyId] = useState("");
  const [files, setFiles] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [submittedClaim, setSubmittedClaim] = useState(null);
  // { [uploadItemId]: { status: "uploading" | "uploaded" | "failed", error? } }
  const [documentUploads, setDocumentUploads] = useState({});

  const fetchOptions = useMemo(
    () => async () => {
      const [vehicles, policies] = await Promise.all([getMyVehicles(), getMyPolicies()]);
      return { vehicles, policies };
    },
    []
  );
  const { data, isLoading, error, reload } = useFetch(fetchOptions, [fetchOptions]);

  const availablePolicies = useMemo(
    () => (data?.policies ?? []).filter((policy) => !vehicleId || policy.Vehicle_ID === vehicleId),
    [data, vehicleId]
  );

  const selectedVehicle = data?.vehicles.find((v) => v.Vehicle_ID === vehicleId);
  const selectedPolicy = data?.policies.find((p) => p.Policy_ID === policyId);
  const uploadItems = selectedUploadItems(files);
  const missingCopies = missingRequiredCopies(files);

  function updateIncident(field, value) {
    setIncident((prev) => ({ ...prev, [field]: value }));
  }

  const incidentValid =
    incident.incidentDate &&
    incident.placeOfAccident.trim() &&
    incident.accidentPincode.trim() &&
    incident.description.trim() &&
    incident.claimType &&
    Number(incident.claimAmount) > 0;
  const vehicleValid = Boolean(vehicleId && policyId);

  async function uploadOneDocument(claimId, item) {
    setDocumentUploads((prev) => ({ ...prev, [item.id]: { status: "uploading" } }));
    try {
      await uploadDocument(claimId, item.category.key, item.file);
      setDocumentUploads((prev) => ({ ...prev, [item.id]: { status: "uploaded" } }));
    } catch (err) {
      setDocumentUploads((prev) => ({ ...prev, [item.id]: { status: "failed", error: getUploadErrorMessage(err) } }));
    }
  }

  async function uploadAllDocuments(claimId) {
    // Sequential, not Promise.all: keeps the per-file progress list
    // predictable and avoids surprising the (already-created) claim with
    // a burst of concurrent uploads.
    for (const item of uploadItems) {
      await uploadOneDocument(claimId, item);
    }
  }

  async function handleSubmit() {
    if (isSubmitting) return;
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const payload = {
        Policy_ID: policyId,
        Vehicle_ID: vehicleId,
        Claim_Date: incident.incidentDate,
        Claim_Type: incident.claimType,
        Claim_Amount: incident.claimAmount,
        Claim_Description: incident.description,
        Place_of_Accident: incident.placeOfAccident,
        Accident_Pincode: incident.accidentPincode,
        Accident_Time: incident.incidentTime || null,
        Third_Party_Involved: incident.thirdPartyInvolved === "yes",
        Injury_Reported: incident.injuryReported === "yes",
        Police_Report_Available: Boolean(incident.policeStation.trim() || incident.firNumber.trim()),
        // Optional - stored in accidents.FIR_Number so the officer's
        // accident-detail check can compare it with the uploaded FIR copy.
        FIR_Number: incident.firNumber.trim() || null,
      };
      // The claim must exist before any document can be linked to it, so
      // document upload only ever starts after createClaim() succeeds.
      const claim = await createClaim(payload);
      setSubmittedClaim(claim);
      if (uploadItems.length > 0) {
        await uploadAllDocuments(claim.Claim_ID);
      }
    } catch (err) {
      setSubmitError(getSubmitErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isLoading) return <LoadingState label="Loading your vehicles and policies..." />;
  if (error) return <ErrorState message={getApiErrorMessage(error)} onRetry={reload} />;

  if (!data.vehicles.length || !data.policies.length) {
    return (
      <div>
        <PageHeader title="New Claim" subtitle="File a new motor insurance claim." />
        <EmptyState
          title="No vehicle or policy on file"
          message="A claim needs at least one registered vehicle and an active policy. Please contact support if you believe this is incorrect."
        />
      </div>
    );
  }

  if (submittedClaim) {
    const totalSelected = uploadItems.length;
    const uploadedCount = uploadItems.filter((item) => documentUploads[item.id]?.status === "uploaded").length;
    const failedCount = uploadItems.filter((item) => documentUploads[item.id]?.status === "failed").length;
    const stillUploading = uploadItems.some((item) => (documentUploads[item.id]?.status ?? "uploading") === "uploading");

    let documentSummary = null;
    if (totalSelected > 0 && !stillUploading) {
      documentSummary =
        failedCount === 0
          ? `All ${totalSelected} document${totalSelected === 1 ? "" : "s"} uploaded.`
          : `${uploadedCount} of ${totalSelected} document${totalSelected === 1 ? "" : "s"} uploaded. ${failedCount} document${failedCount === 1 ? "" : "s"} failed and need${failedCount === 1 ? "s" : ""} retry.`;
    }

    return (
      <div>
        <PageHeader title="New Claim (FNOL)" subtitle="File a new motor insurance claim in a few steps." />
        <Card>
          <div className="flex flex-col items-center gap-4 py-8 text-center">
            <CheckCircle2 className="h-12 w-12 text-success" aria-hidden="true" />
            <div>
              <h2 className="text-lg font-semibold text-ink">Claim submitted successfully</h2>
              <p className="mt-1 text-sm text-muted">
                Your claim has been recorded and is now waiting for a Claims Officer to review it.
              </p>
            </div>
            <div className="w-full max-w-sm space-y-3 rounded-card border border-border bg-surface p-4 text-left text-sm">
              <div className="flex justify-between">
                <span className="text-muted">Claim Number</span>
                <span className="font-semibold text-ink">{submittedClaim.Claim_Number}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">Status</span>
                <StatusBadge label={submittedClaim.Claim_Status} tone={getStatusTone(submittedClaim.Claim_Status)} />
              </div>
              {totalSelected > 0 && (
                <div className="flex justify-between">
                  <span className="text-muted">Documents Uploaded</span>
                  <span className="font-semibold text-ink">
                    {uploadedCount} / {totalSelected}
                  </span>
                </div>
              )}
            </div>

            {totalSelected > 0 && (
              <div className="w-full max-w-sm space-y-2 text-left">
                {uploadItems.map((item) => {
                  const state = documentUploads[item.id] ?? { status: "uploading" };
                  const file = item.file;
                  return (
                    <div
                      key={item.id}
                      className="flex items-center justify-between gap-3 rounded-card border border-border bg-surface p-3 text-sm"
                    >
                      <div className="min-w-0">
                        <p className="truncate font-medium text-ink">{item.label}</p>
                        <p className="truncate text-xs text-muted">
                          {file.name} &middot; {formatFileSize(file.size)}
                        </p>
                        {state.status === "failed" && <p className="mt-0.5 text-xs text-danger">{state.error}</p>}
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        {state.status === "uploading" && (
                          <Loader2 className="h-4 w-4 animate-spin text-brand-600" aria-hidden="true" />
                        )}
                        {state.status === "uploaded" && <StatusBadge label="Uploaded" tone="success" />}
                        {state.status === "failed" && (
                          <>
                            <StatusBadge label="Failed" tone="danger" />
                            <Button
                              size="sm"
                              variant="secondary"
                              onClick={() => uploadOneDocument(submittedClaim.Claim_ID, item)}
                            >
                              <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
                              Retry
                            </Button>
                          </>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {documentSummary && (
              <div
                className={`flex max-w-sm gap-3 rounded-card border p-4 text-left text-sm ${
                  failedCount === 0
                    ? "border-green-200 bg-green-50 text-green-900"
                    : "border-amber-200 bg-amber-50 text-amber-900"
                }`}
              >
                {failedCount === 0 ? (
                  <CheckCircle2 className="h-5 w-5 shrink-0 text-success" aria-hidden="true" />
                ) : (
                  <AlertTriangle className="h-5 w-5 shrink-0 text-warning" aria-hidden="true" />
                )}
                <p>{documentSummary}</p>
              </div>
            )}

            <div className="flex gap-3 pt-2">
              <Button variant="secondary" onClick={() => navigate("/customer/claims")}>
                Back to My Claims
              </Button>
              <Button onClick={() => navigate(`/customer/claims/${submittedClaim.Claim_ID}`)}>View Claim</Button>
            </div>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="New Claim (FNOL)" subtitle="File a new motor insurance claim in a few steps." />
      <Card>
        <StepIndicator currentStep={step} />

        {step === 1 && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Date of Incident" required>
                <input
                  type="date"
                  value={incident.incidentDate}
                  max={new Date().toISOString().slice(0, 10)}
                  onChange={(e) => updateIncident("incidentDate", e.target.value)}
                  className="input"
                />
              </Field>
              <Field label="Time of Incident">
                <input
                  type="time"
                  value={incident.incidentTime}
                  onChange={(e) => updateIncident("incidentTime", e.target.value)}
                  className="input"
                />
              </Field>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Claim Type" required>
                <select
                  value={incident.claimType}
                  onChange={(e) => updateIncident("claimType", e.target.value)}
                  className="input"
                >
                  <option value="">Select a claim type</option>
                  {CLAIM_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {type}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Estimated Claim Amount (INR)" required>
                <input
                  type="number"
                  min="1"
                  step="1"
                  value={incident.claimAmount}
                  onChange={(e) => updateIncident("claimAmount", e.target.value)}
                  className="input"
                  placeholder="e.g. 45000"
                />
              </Field>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Place of Accident" required>
                <input
                  type="text"
                  value={incident.placeOfAccident}
                  onChange={(e) => updateIncident("placeOfAccident", e.target.value)}
                  className="input"
                  placeholder="e.g. Anna Nagar, Chennai"
                />
              </Field>
              <Field label="Accident Pincode" required>
                <input
                  type="text"
                  value={incident.accidentPincode}
                  onChange={(e) => updateIncident("accidentPincode", e.target.value)}
                  className="input"
                  placeholder="e.g. 600040"
                  maxLength={10}
                />
              </Field>
            </div>
            <Field label="Description of Accident" required>
              <textarea
                value={incident.description}
                onChange={(e) => updateIncident("description", e.target.value)}
                rows={3}
                className="input resize-none"
                placeholder="Describe what happened"
              />
            </Field>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Police Station">
                <input
                  type="text"
                  value={incident.policeStation}
                  onChange={(e) => updateIncident("policeStation", e.target.value)}
                  className="input"
                />
              </Field>
              <Field label="FIR Number">
                <input
                  type="text"
                  value={incident.firNumber}
                  onChange={(e) => updateIncident("firNumber", e.target.value)}
                  maxLength={30}
                  className="input"
                  placeholder="If a police report was filed, e.g. 123/2026"
                />
              </Field>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Third Party Involved">
                <select
                  value={incident.thirdPartyInvolved}
                  onChange={(e) => updateIncident("thirdPartyInvolved", e.target.value)}
                  className="input"
                >
                  <option value="no">No</option>
                  <option value="yes">Yes</option>
                </select>
              </Field>
              <Field label="Injury Reported">
                <select
                  value={incident.injuryReported}
                  onChange={(e) => updateIncident("injuryReported", e.target.value)}
                  className="input"
                >
                  <option value="no">No</option>
                  <option value="yes">Yes</option>
                </select>
              </Field>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <Field label="Vehicle" required>
              <select
                value={vehicleId}
                onChange={(e) => {
                  setVehicleId(e.target.value);
                  setPolicyId("");
                }}
                className="input"
              >
                <option value="">Select a vehicle</option>
                {data.vehicles.map((vehicle) => (
                  <option key={vehicle.Vehicle_ID} value={vehicle.Vehicle_ID}>
                    {formatVehicleLabel(vehicle)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Policy" required>
              <select
                value={policyId}
                onChange={(e) => setPolicyId(e.target.value)}
                disabled={!vehicleId}
                className="input"
              >
                <option value="">Select a policy</option>
                {availablePolicies.map((policy) => (
                  <option key={policy.Policy_ID} value={policy.Policy_ID}>
                    {policy.Policy_Number} &middot; {policy.Policy_Type}
                  </option>
                ))}
              </select>
              {vehicleId && availablePolicies.length === 0 && (
                <p className="mt-1 text-xs text-danger">No policy on file for this vehicle.</p>
              )}
            </Field>
          </div>
        )}

        {step === 3 && (
          <div>
            <p className="mb-4 text-sm text-muted">
              Upload copies of the driving licence, RC and insurance policy, take accident photos with your camera, and
              add the FIR and repair estimate if they apply to this claim.
            </p>
            <DocumentUploadGrid files={files} onFileChange={(key, file) => setFiles((prev) => ({ ...prev, [key]: file }))} />
          </div>
        )}

        {step === 4 && (
          <div className="space-y-6">
            <ReviewSection title="Incident Details">
              <ReviewRow label="Date of Incident" value={incident.incidentDate} />
              <ReviewRow label="Time of Incident" value={incident.incidentTime || "-"} />
              <ReviewRow label="Claim Type" value={incident.claimType || "-"} />
              <ReviewRow label="Estimated Claim Amount" value={incident.claimAmount ? `₹${incident.claimAmount}` : "-"} />
              <ReviewRow label="Place of Accident" value={incident.placeOfAccident} />
              <ReviewRow label="Accident Pincode" value={incident.accidentPincode} />
              <ReviewRow label="Description" value={incident.description} />
              <ReviewRow label="Police Station" value={incident.policeStation || "-"} />
              <ReviewRow label="FIR Number" value={incident.firNumber || "-"} />
              <ReviewRow label="Third Party Involved" value={incident.thirdPartyInvolved === "yes" ? "Yes" : "No"} />
              <ReviewRow label="Injury Reported" value={incident.injuryReported === "yes" ? "Yes" : "No"} />
            </ReviewSection>
            <ReviewSection title="Vehicle & Policy">
              <ReviewRow label="Vehicle" value={formatVehicleLabel(selectedVehicle)} />
              <ReviewRow label="Policy" value={selectedPolicy ? `${selectedPolicy.Policy_Number} (${selectedPolicy.Policy_Type})` : "-"} />
            </ReviewSection>
            <ReviewSection title="Documents">
              {uploadItems.length === 0 ? (
                <p className="text-sm text-muted">No documents selected.</p>
              ) : (
                uploadItems.map((item) => <ReviewRow key={item.id} label={item.label} value={item.file.name} />)
              )}
            </ReviewSection>

            {missingCopies.length > 0 && (
              <div className="flex gap-3 rounded-card border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                <AlertTriangle className="h-5 w-5 shrink-0 text-warning" aria-hidden="true" />
                <p>
                  Not added yet: {missingCopies.map((c) => c.label).join(", ")}. These copies are required with every
                  claim. You can add them later from Docs &gt; Upload Documents, but the claim can't be fully checked
                  until they are provided.
                </p>
              </div>
            )}

            {submitError && (
              <div className="flex gap-3 rounded-card border border-red-200 bg-red-50 p-4 text-sm text-red-900">
                <AlertTriangle className="h-5 w-5 shrink-0 text-danger" aria-hidden="true" />
                <p>{submitError}</p>
              </div>
            )}
          </div>
        )}

        <div className="mt-6 flex items-center justify-between border-t border-border pt-4">
          <Button
            variant="secondary"
            disabled={isSubmitting}
            onClick={() => (step === 1 ? navigate("/customer/claims") : setStep((s) => s - 1))}
          >
            {step === 1 ? "Cancel" : "Back"}
          </Button>
          {step < STEPS.length ? (
            <Button
              onClick={() => setStep((s) => s + 1)}
              disabled={(step === 1 && !incidentValid) || (step === 2 && !vehicleValid)}
            >
              Next
            </Button>
          ) : (
            <Button onClick={handleSubmit} isLoading={isSubmitting} disabled={isSubmitting}>
              {isSubmitting ? "Submitting..." : "Submit Claim"}
            </Button>
          )}
        </div>
      </Card>
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

function ReviewSection({ title, children }) {
  return (
    <div>
      <h3 className="mb-2 text-sm font-semibold text-ink">{title}</h3>
      <div className="space-y-1 rounded-card border border-border bg-surface p-4">{children}</div>
    </div>
  );
}

function ReviewRow({ label, value }) {
  return (
    <div className="flex justify-between gap-4 text-sm">
      <span className="text-muted">{label}</span>
      <span className="text-right text-ink">{value}</span>
    </div>
  );
}
