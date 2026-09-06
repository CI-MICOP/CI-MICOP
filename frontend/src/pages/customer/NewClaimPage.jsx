import { AlertTriangle, Check } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import Button from "../../components/common/Button";
import Card from "../../components/common/Card";
import EmptyState from "../../components/common/EmptyState";
import ErrorState from "../../components/common/ErrorState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import DocumentUploadGrid from "../../components/customer/DocumentUploadGrid";
import { DOCUMENT_CATEGORIES } from "../../components/customer/documentCategories";
import { useFetch } from "../../hooks/useFetch";
import { getMyPolicies } from "../../services/policyService";
import { getMyVehicles } from "../../services/vehicleService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatVehicleLabel } from "../../utils/format";

const STEPS = ["Incident Details", "Vehicle & Policy", "Upload Documents", "Review & Submit"];

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
                {isComplete ? <Check className="h-4 w-4" aria-hidden="true" /> : stepNumber}
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
  description: "",
  policeStation: "",
  thirdPartyInvolved: "no",
  injuryReported: "no",
};

export default function NewClaimPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [incident, setIncident] = useState(EMPTY_INCIDENT);
  const [vehicleId, setVehicleId] = useState("");
  const [policyId, setPolicyId] = useState("");
  const [files, setFiles] = useState({});
  const [submitAttempted, setSubmitAttempted] = useState(false);

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

  function updateIncident(field, value) {
    setIncident((prev) => ({ ...prev, [field]: value }));
  }

  const incidentValid =
    incident.incidentDate && incident.placeOfAccident.trim() && incident.description.trim();
  const vehicleValid = Boolean(vehicleId && policyId);

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
            <Field label="Place of Accident" required>
              <input
                type="text"
                value={incident.placeOfAccident}
                onChange={(e) => updateIncident("placeOfAccident", e.target.value)}
                className="input"
                placeholder="e.g. Anna Nagar, Chennai"
              />
            </Field>
            <Field label="Description of Accident" required>
              <textarea
                value={incident.description}
                onChange={(e) => updateIncident("description", e.target.value)}
                rows={3}
                className="input resize-none"
                placeholder="Describe what happened"
              />
            </Field>
            <Field label="Police Station">
              <input
                type="text"
                value={incident.policeStation}
                onChange={(e) => updateIncident("policeStation", e.target.value)}
                className="input"
              />
            </Field>
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
              Select the documents you have available. Required documents vary by claim type.
            </p>
            <DocumentUploadGrid files={files} onFileChange={(key, file) => setFiles((prev) => ({ ...prev, [key]: file }))} />
          </div>
        )}

        {step === 4 && (
          <div className="space-y-6">
            <ReviewSection title="Incident Details">
              <ReviewRow label="Date of Incident" value={incident.incidentDate} />
              <ReviewRow label="Time of Incident" value={incident.incidentTime || "-"} />
              <ReviewRow label="Place of Accident" value={incident.placeOfAccident} />
              <ReviewRow label="Description" value={incident.description} />
              <ReviewRow label="Police Station" value={incident.policeStation || "-"} />
              <ReviewRow label="Third Party Involved" value={incident.thirdPartyInvolved === "yes" ? "Yes" : "No"} />
              <ReviewRow label="Injury Reported" value={incident.injuryReported === "yes" ? "Yes" : "No"} />
            </ReviewSection>
            <ReviewSection title="Vehicle & Policy">
              <ReviewRow label="Vehicle" value={formatVehicleLabel(selectedVehicle)} />
              <ReviewRow label="Policy" value={selectedPolicy ? `${selectedPolicy.Policy_Number} (${selectedPolicy.Policy_Type})` : "-"} />
            </ReviewSection>
            <ReviewSection title="Documents">
              {DOCUMENT_CATEGORIES.filter((c) => files[c.key]).length === 0 ? (
                <p className="text-sm text-muted">No documents selected.</p>
              ) : (
                DOCUMENT_CATEGORIES.filter((c) => files[c.key]).map((c) => (
                  <ReviewRow key={c.key} label={c.label} value={files[c.key].name} />
                ))
              )}
            </ReviewSection>

            {submitAttempted && (
              <div className="flex gap-3 rounded-card border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                <AlertTriangle className="h-5 w-5 shrink-0 text-warning" aria-hidden="true" />
                <div>
                  <p className="font-medium">Claim submission is not yet connected to the backend</p>
                  <p className="mt-1 text-amber-800">
                    The CI-MICOP API does not currently expose a claim-creation endpoint (only claim
                    retrieval). Your information above has not been saved anywhere. This will be wired
                    up once that backend endpoint is available.
                  </p>
                </div>
              </div>
            )}
          </div>
        )}

        <div className="mt-6 flex items-center justify-between border-t border-border pt-4">
          <Button
            variant="secondary"
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
            <Button onClick={() => setSubmitAttempted(true)}>Submit Claim</Button>
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
