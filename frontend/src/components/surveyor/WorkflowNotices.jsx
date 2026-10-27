import { AlertTriangle, CalendarClock, CheckCircle2, Lock, PencilLine } from "lucide-react";
import { Link } from "react-router-dom";

import Button from "../common/Button";
import Card from "../common/Card";
import { CORRECTION_PROMPT, lockedReason } from "./workflowProgress";

/** Shown in place of a step that cannot be used yet (schedule or order). */
export function StepLockNotice({ progress, claimId }) {
  if (progress.workflow && !progress.scheduleReached) {
    return (
      <Card className="border-amber-200 bg-amber-50">
        <div className="flex items-start gap-3">
          <CalendarClock className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" aria-hidden="true" />
          <div>
            <h3 className="text-sm font-semibold text-amber-900">Inspection not open yet</h3>
            <p className="mt-1 text-sm text-amber-900">{progress.schedule?.message}</p>
            <p className="mt-1 text-xs text-amber-800">
              You can view the claim details now. Nothing can be recorded or submitted before the scheduled date.
            </p>
          </div>
        </div>
      </Card>
    );
  }

  const target = !progress.inspectionComplete
    ? { path: "inspection", label: "Inspection" }
    : !progress.damageComplete
      ? { path: "damage", label: "Vehicle Damage" }
      : { path: "evidence", label: "Evidence" };
  return (
    <Card>
      <div className="flex items-start gap-3">
        <Lock className="mt-0.5 h-5 w-5 shrink-0 text-muted" aria-hidden="true" />
        <div>
          <h3 className="text-sm font-semibold text-ink">{progress.workflow ? "Complete the earlier steps first" : "Not available"}</h3>
          <p className="mt-1 text-sm text-muted">{lockedReason(progress)}</p>
          {progress.workflow && (
            <Link
              to={`/surveyor/claims/${claimId}/${target.path}`}
              className="mt-2 inline-block text-sm font-medium text-brand-600 hover:text-brand-700"
            >
              Go to {target.label}
            </Link>
          )}
        </div>
      </div>
    </Card>
  );
}

/**
 * A submitted report whose saved records do not meet the current submission
 * rules (for example one submitted before surveyor camera captures were
 * required). It stays exactly as submitted; this only says so.
 */
export function SubmissionReviewNotice({ review }) {
  if (!review || review.meets_current_requirements) return null;
  return (
    <div role="note" className="flex items-start gap-2 rounded-card border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <div>
        <p className="font-medium">{review.message}</p>
        {review.problems.length > 0 && (
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs">
            {review.problems.map((problem) => (
              <li key={problem}>{problem}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

/**
 * A completed step is read-only. Before submission the surveyor can reopen
 * it deliberately (with a confirmation) to correct a mistake; the server
 * then re-checks every later step from saved data.
 */
export function CompletedStepBar({ submitted, correcting, onCorrect, onFinishCorrecting, busy = false, error = "", children }) {
  if (submitted) {
    return (
      <p className="mb-4 flex items-center gap-2 rounded-card border border-green-200 bg-green-50 p-3 text-sm text-success">
        <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
        The survey report has been submitted. This step can no longer be changed.
      </p>
    );
  }
  if (correcting) {
    return (
      <div className="mb-4 flex flex-col gap-2 rounded-card border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 sm:flex-row sm:items-center sm:justify-between">
        <span>
          Correcting this step. Later steps will be checked again after you save.
          {error && <span role="alert" className="mt-1 block text-danger">{error}</span>}
        </span>
        {onFinishCorrecting && (
          <Button size="sm" variant="secondary" onClick={onFinishCorrecting} isLoading={busy}>
            Done correcting
          </Button>
        )}
      </div>
    );
  }
  function handleCorrect() {
    if (window.confirm(CORRECTION_PROMPT)) onCorrect();
  }
  return (
    <div className="mb-4 flex flex-col gap-2 rounded-card border border-green-200 bg-green-50 p-3 text-sm text-success sm:flex-row sm:items-center sm:justify-between">
      <span className="flex items-center gap-2">
        <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
        {children ?? "This step is complete and saved."}
        {error && <span role="alert" className="block text-danger">{error}</span>}
      </span>
      <Button size="sm" variant="secondary" onClick={handleCorrect} isLoading={busy}>
        <PencilLine className="h-4 w-4" aria-hidden="true" />
        Correct this step
      </Button>
    </div>
  );
}
