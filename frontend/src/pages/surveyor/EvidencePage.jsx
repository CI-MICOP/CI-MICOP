import { Camera, CheckCircle2, MapPin, RefreshCw, RotateCcw, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import CameraView from "../../components/camera/CameraView";
import { getLocation, locationMessage, todayIst } from "../../components/camera/cameraSupport";
import Breadcrumbs from "../../components/common/Breadcrumbs";
import Button from "../../components/common/Button";
import Card from "../../components/common/Card";
import ErrorState from "../../components/common/ErrorState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import StatusBadge from "../../components/common/StatusBadge";
import { locationStatusText, locationText } from "../../components/surveyor/captureDisplay";
import ClaimStepNav from "../../components/surveyor/ClaimStepNav";
import ClaimTabs from "../../components/surveyor/ClaimTabs";
import EvidenceThumbnail from "../../components/surveyor/EvidenceThumbnail";
import { useSurveyorClaim } from "../../components/surveyor/useSurveyorClaim";
import { CompletedStepBar, StepLockNotice, SubmissionReviewNotice } from "../../components/surveyor/WorkflowNotices";
import { lockedReason, serverMessage } from "../../components/surveyor/workflowProgress";
import { createEvidenceCapture } from "../../services/surveyorService";
import { getApiErrorMessage, getUploadErrorMessage } from "../../utils/errors";
import { formatDate } from "../../utils/format";

// Kept in sync with SURVEYOR_CAPTURE_TYPES in backend/app/services/evidence_upload.py.
const EVIDENCE_TYPES = [
  "Vehicle Damage Close-up",
  "Overall Vehicle Condition",
  "Damage Location and Extent",
  "Accident Scene / Surroundings",
];

let nextId = 1;

function dateProblem(value, min, max) {
  if (!value) return "Choose the evidence date.";
  if (value > max) return "The evidence date cannot be in the future.";
  if (min && value < min) return "The evidence date cannot be before the scheduled inspection date.";
  return "";
}

export default function EvidencePage() {
  const { claimId } = useParams();
  const [evidenceType, setEvidenceType] = useState(EVIDENCE_TYPES[0]);
  const [evidenceDate, setEvidenceDate] = useState(todayIst);
  const [cameraOpen, setCameraOpen] = useState(false);
  // Captured but not yet saved photos, each with its own type, date and location.
  const [pending, setPending] = useState([]);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);
  const savingRef = useRef(false);
  const retakeRef = useRef(null);
  const pendingRef = useRef(pending);
  useEffect(() => {
    pendingRef.current = pending;
  }, [pending]);

  const { data, isLoading, error, reload, progress } = useSurveyorClaim(claimId);

  // Release preview images when the page goes away.
  useEffect(() => () => pendingRef.current.forEach((item) => URL.revokeObjectURL(item.url)), []);

  function updateItem(id, patch) {
    setPending((items) => items.map((item) => (item.id === id ? { ...item, ...patch } : item)));
  }

  function locate(id) {
    updateItem(id, { location: { status: "locating" } });
    // A fresh reading for this photo, as close to its capture as possible.
    getLocation().then((location) => updateItem(id, { location }));
  }

  function handleCapture(blob, capturedAt) {
    const meta = retakeRef.current ?? { evidenceType, evidenceDate };
    retakeRef.current = null;
    const item = { id: nextId++, blob, url: URL.createObjectURL(blob), capturedAt, ...meta, location: { status: "locating" }, error: "" };
    setPending((items) => [...items, item]);
    setMessage(null);
    locate(item.id);
  }

  function remove(item) {
    URL.revokeObjectURL(item.url);
    setPending((items) => items.filter((i) => i.id !== item.id));
  }

  function retake(item) {
    retakeRef.current = { evidenceType: item.evidenceType, evidenceDate: item.evidenceDate };
    remove(item);
    setCameraOpen(true);
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

  const { claim } = data;
  const saved = data.evidence ?? []; // the server returns only this surveyor's own captures
  const locked = !progress.unlocked.has("evidence");
  const canCapture = !locked && progress.canEdit;
  const minDate = progress.schedule?.scheduled_date;
  const maxDate = todayIst();
  const readyToSave = (item) => item.location.status === "captured" && !dateProblem(item.evidenceDate, minDate, maxDate);

  async function saveAll() {
    if (savingRef.current) return;
    const ready = pendingRef.current.filter(readyToSave);
    if (ready.length === 0) {
      setMessage({ tone: "error", text: "Each photo needs a usable location and a valid evidence date before it can be saved." });
      return;
    }
    savingRef.current = true;
    setSaving(true);
    setMessage(null);
    let savedCount = 0;
    // One at a time: predictable progress and no burst of uploads.
    for (const item of ready) {
      updateItem(item.id, { error: "", saving: true });
      try {
        await createEvidenceCapture(claimId, {
          evidenceType: item.evidenceType,
          evidenceDate: item.evidenceDate,
          photo: item.blob,
          capturedAt: item.capturedAt,
          latitude: item.location.latitude,
          longitude: item.location.longitude,
          accuracy: item.location.accuracy,
        });
        savedCount += 1;
        remove(item);
      } catch (err) {
        // Nothing counts as saved until the server confirms it; the photo stays for a retry.
        updateItem(item.id, { saving: false, error: serverMessage(err, getUploadErrorMessage(err)) });
      }
    }
    savingRef.current = false;
    setSaving(false);
    if (savedCount) {
      setMessage({ tone: "success", text: `${savedCount} photo${savedCount === 1 ? "" : "s"} saved.` });
      reload();
    }
  }

  async function handleNext() {
    if (pending.length) return "Save or remove the captured images before continuing.";
    return true;
  }

  let blockedReason = "";
  if (locked) blockedReason = lockedReason(progress);
  else if (!progress.submitted && pending.length) blockedReason = "Save or remove the captured images before continuing.";
  else if (!progress.submitted && !progress.evidenceComplete) {
    blockedReason = "Save at least one photo captured with the in-app camera, with your location, to continue.";
  }

  const imageCount = saved.length + pending.length;

  return (
    <div>
      <Breadcrumbs
        items={[
          { label: "Assigned Inspections", to: "/surveyor/claims" },
          { label: claim.Claim_Number, to: `/surveyor/claims/${claim.Claim_ID}` },
          { label: "Evidence" },
        ]}
      />
      <PageHeader title={`Evidence — ${claim.Claim_Number}`} />
      <ClaimTabs claimId={claim.Claim_ID} progress={progress} hasUnsavedChanges={pending.length > 0} />

      {locked ? (
        <StepLockNotice progress={progress} claimId={claim.Claim_ID} />
      ) : (
        <div className="space-y-6">
          {progress.submitted && <CompletedStepBar submitted />}
          <SubmissionReviewNotice review={progress.submissionReview} />

          {canCapture && (
            <Card>
              <h3 className="mb-1 text-sm font-semibold text-ink">Capture Evidence</h3>
              <p className="mb-4 text-xs text-muted">
                Photos are taken with your device camera only, and your location is recorded with each photo. The type
                and date below apply to the next photo; you can change them per photo before saving.
              </p>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <label className="block">
                  <span className="mb-1 block text-sm font-medium text-ink">
                    Evidence Type <span className="text-danger">*</span>
                  </span>
                  <select className="input" value={evidenceType} onChange={(e) => setEvidenceType(e.target.value)}>
                    {EVIDENCE_TYPES.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="mb-1 block text-sm font-medium text-ink">
                    Evidence Date <span className="text-danger">*</span>
                  </span>
                  <input
                    type="date"
                    className="input"
                    min={minDate}
                    max={maxDate}
                    value={evidenceDate}
                    onChange={(e) => setEvidenceDate(e.target.value)}
                  />
                </label>
              </div>

              <div className="mt-4 rounded-card border-2 border-dashed border-brand-200 bg-brand-50/40 p-5">
                {cameraOpen ? (
                  <CameraView onCapture={handleCapture} onClose={() => setCameraOpen(false)} />
                ) : (
                  <div className="flex flex-col items-center gap-3 text-center">
                    <span className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-100 text-brand-700">
                      <Camera className="h-6 w-6" aria-hidden="true" />
                    </span>
                    <div>
                      <h4 className="text-sm font-semibold text-ink">Capture Your Image</h4>
                      <p className="mt-0.5 text-xs text-muted">
                        Allow camera and location access when your browser asks. You can take several photos.
                      </p>
                    </div>
                    <Button onClick={() => setCameraOpen(true)}>
                      <Camera className="h-4 w-4" aria-hidden="true" />
                      Open Camera
                    </Button>
                  </div>
                )}
              </div>
            </Card>
          )}

          <Card>
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <h3 className="text-sm font-semibold text-ink">Images ({imageCount})</h3>
              {pending.length > 0 && (
                <Button onClick={saveAll} isLoading={saving}>
                  Save {pending.length} image{pending.length === 1 ? "" : "s"}
                </Button>
              )}
            </div>

            {message && (
              <p
                role={message.tone === "error" ? "alert" : "status"}
                className={`mb-4 flex items-center gap-2 rounded-card border p-3 text-sm ${
                  message.tone === "error" ? "border-red-200 bg-red-50 text-danger" : "border-green-200 bg-green-50 text-success"
                }`}
              >
                {message.tone === "success" && <CheckCircle2 className="h-4 w-4" aria-hidden="true" />}
                {message.text}
              </p>
            )}

            {imageCount === 0 ? (
              <p className="text-sm text-muted">
                {progress.submitted
                  ? "No surveyor-captured images are recorded for this inspection."
                  : "No images yet. Photos you capture appear here."}
              </p>
            ) : (
              <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-label="Evidence images">
                {pending.map((item, index) => {
                  const problem = dateProblem(item.evidenceDate, minDate, maxDate);
                  const retryable = !["captured", "locating"].includes(item.location.status);
                  return (
                    <li key={item.id} className="overflow-hidden rounded-card border border-amber-200 bg-card" aria-label={`Unsaved image ${index + 1}`}>
                      <img src={item.url} alt={`Captured image ${index + 1}`} className="aspect-[4/3] w-full object-cover" />
                      <div className="space-y-2 p-3">
                        <StatusBadge label="Not saved" tone="warning" />
                        <label className="block">
                          <span className="mb-1 block text-xs font-medium text-muted">Evidence Type</span>
                          <select
                            className="input"
                            value={item.evidenceType}
                            disabled={item.saving}
                            onChange={(e) => updateItem(item.id, { evidenceType: e.target.value })}
                          >
                            {EVIDENCE_TYPES.map((option) => (
                              <option key={option} value={option}>
                                {option}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="block">
                          <span className="mb-1 block text-xs font-medium text-muted">Evidence Date</span>
                          <input
                            type="date"
                            className="input"
                            min={minDate}
                            max={maxDate}
                            value={item.evidenceDate}
                            disabled={item.saving}
                            onChange={(e) => updateItem(item.id, { evidenceDate: e.target.value })}
                          />
                          {problem && <span className="mt-1 block text-xs text-danger">{problem}</span>}
                        </label>
                        <p
                          className={`flex items-start gap-1 text-xs ${
                            item.location.status === "captured" ? "text-success" : item.location.status === "locating" ? "text-muted" : "text-amber-800"
                          }`}
                        >
                          <MapPin className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
                          {locationMessage(item.location)}
                        </p>
                        {item.error && (
                          <p role="alert" className="text-xs text-danger">
                            {item.error}
                          </p>
                        )}
                        <div className="flex flex-wrap gap-2">
                          {retryable && (
                            <Button size="sm" variant="secondary" onClick={() => locate(item.id)} disabled={item.saving}>
                              <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                              Retry location
                            </Button>
                          )}
                          <Button size="sm" variant="secondary" onClick={() => retake(item)} disabled={item.saving || !canCapture}>
                            <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
                            Retake
                          </Button>
                          <Button size="sm" variant="secondary" onClick={() => remove(item)} disabled={item.saving}>
                            <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                            Remove
                          </Button>
                        </div>
                      </div>
                    </li>
                  );
                })}
                {saved.map((item) => (
                  <li key={item.Evidence_ID} className="overflow-hidden rounded-card border border-border bg-card" aria-label={`Saved image ${item.File_Name}`}>
                    <EvidenceThumbnail evidenceId={item.Evidence_ID} alt={`Saved image ${item.File_Name}`} />
                    <dl className="space-y-1 p-3 text-xs">
                      <div className="flex flex-wrap items-center gap-2">
                        <StatusBadge label="Saved" tone="success" />
                        <StatusBadge
                          label={item.qualifying_capture ? "Counts as surveyor photo" : "Does not count"}
                          tone={item.qualifying_capture ? "info" : "neutral"}
                        />
                      </div>
                      <div>
                        <dt className="inline font-medium text-muted">Type: </dt>
                        <dd className="inline text-ink">{item.Evidence_Type}</dd>
                      </div>
                      <div>
                        <dt className="inline font-medium text-muted">Date: </dt>
                        <dd className="inline text-ink">{formatDate(item.Evidence_Date)}</dd>
                      </div>
                      <div>
                        <dt className="inline font-medium text-muted">Location: </dt>
                        <dd className="inline text-ink">
                          {locationText(item.capture)} · {locationStatusText(item.capture)}
                        </dd>
                      </div>
                      <div>
                        <dt className="inline font-medium text-muted">AI analysis: </dt>
                        <dd className="inline text-ink">{item.Verification_Status === "Pending" ? "Not analysed yet" : item.Verification_Status}</dd>
                      </div>
                    </dl>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-4 text-xs text-muted">
              Device-reported time and location are recorded and checked for plausibility; they are not proof of where or
              when a photo was taken.
            </p>
          </Card>
        </div>
      )}
      <ClaimStepNav
        claimId={claim.Claim_ID}
        current="evidence"
        onNext={handleNext}
        hasUnsavedChanges={pending.length > 0}
        blockedReason={blockedReason}
      />
    </div>
  );
}
