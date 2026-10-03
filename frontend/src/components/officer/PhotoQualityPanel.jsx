import { Gauge } from "lucide-react";
import { useState } from "react";

import Button from "../common/Button";
import Card from "../common/Card";
import StatusBadge from "../common/StatusBadge";
import { checkPhotoQuality } from "../../services/officerService";
import { getApiErrorMessage } from "../../utils/errors";

const STATUS_TONE = {
  NO_ISSUES_FOUND: "success",
  ISSUES_FOUND: "warning",
  UNAVAILABLE: "neutral",
};

const STATUS_LABEL = {
  NO_ISSUES_FOUND: "No issues found",
  ISSUES_FOUND: "Quality issues",
  UNAVAILABLE: "Unavailable",
};

const FLAG_LABEL = {
  LOW_RESOLUTION: "Low resolution",
  TOO_DARK: "Too dark",
  TOO_BRIGHT: "Too bright",
  LOW_CONTRAST: "Low contrast",
  BLURRY: "Blurry",
};

/**
 * Officer-side view of the Step 5.8.15 evidence photo quality check
 * (POST .../evidence/quality-check). One explicit, read-only action -
 * nothing runs on page load and nothing is saved. Shows the raw
 * measurements next to the flags rather than a combined score.
 */
export default function PhotoQualityPanel({ claimId }) {
  const [check, setCheck] = useState({ status: "idle", result: null, message: "" });

  async function handleCheck() {
    setCheck({ status: "running", result: null, message: "" });
    try {
      const result = await checkPhotoQuality(claimId);
      setCheck({ status: "done", result, message: "" });
    } catch (err) {
      setCheck({ status: "error", result: null, message: getApiErrorMessage(err) });
    }
  }

  return (
    <Card className="mb-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-ink">Photo Quality</h3>
          <p className="mt-1 text-sm text-muted">
            Checks whether each photo on this claim is large, bright, contrasty and sharp enough to rely on.
          </p>
        </div>
        <Button variant="secondary" onClick={handleCheck} isLoading={check.status === "running"} disabled={check.status === "running"}>
          <Gauge className="h-4 w-4" aria-hidden="true" />
          Check Quality
        </Button>
      </div>

      {check.status === "error" && <p className="mt-4 text-sm text-danger">Quality check failed: {check.message}</p>}
      {check.result && <Results result={check.result} />}
    </Card>
  );
}

function Results({ result }) {
  if (result.photos_checked === 0) {
    return (
      <p className="mt-4 border-t border-border pt-4 text-sm text-muted">
        This claim has no evidence photos to check yet.
      </p>
    );
  }

  return (
    <div className="mt-4 space-y-3 border-t border-border pt-4 text-sm">
      <ul className="space-y-3">
        {result.results.map((photo) => (
          <li key={photo.evidence_id} className="rounded-card border border-border p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="min-w-0 truncate font-medium text-ink">
                {photo.file_name} <span className="font-normal text-muted">({photo.evidence_id})</span>
              </span>
              <StatusBadge label={STATUS_LABEL[photo.status] ?? photo.status} tone={STATUS_TONE[photo.status] ?? "neutral"} />
            </div>
            {photo.flags.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {photo.flags.map((flag) => (
                  <StatusBadge key={flag} label={FLAG_LABEL[flag] ?? flag} tone="warning" />
                ))}
              </div>
            )}
            <p className="mt-2 text-ink">{photo.explanation}</p>
            {photo.measurements && (
              <dl className="mt-2 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
                <Measure label="Size" value={`${photo.measurements.width} × ${photo.measurements.height}`} />
                <Measure label="Brightness" value={`${photo.measurements.brightness} / 255`} />
                <Measure label="Contrast" value={photo.measurements.contrast} />
                <Measure label="Blur measure" value={`${photo.measurements.reblur_ratio} (higher = blurrier)`} />
              </dl>
            )}
          </li>
        ))}
      </ul>

      {result.limitations.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted">Limitations</p>
          <ul className="list-disc space-y-1 pl-5 text-muted">
            {result.limitations.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function Measure({ label, value }) {
  return (
    <div>
      <dt className="uppercase tracking-wide text-muted">{label}</dt>
      <dd className="text-ink">{value}</dd>
    </div>
  );
}
