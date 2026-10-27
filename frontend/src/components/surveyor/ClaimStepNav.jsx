import { ArrowLeft, ArrowRight, Loader2 } from "lucide-react";
import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { TABS } from "./claimSteps";
import { UNSAVED_CHANGES_PROMPT } from "./workflowProgress";

// Same look as the small secondary / primary Button (components/common/Button.jsx).
const linkBase =
  "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors " +
  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600";
const backClass = `${linkBase} border border-border bg-white text-ink hover:bg-surface`;
const nextClass = `${linkBase} bg-brand-600 text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60`;

/**
 * Back / Next buttons at the bottom of a claim's views, following the
 * ClaimTabs order: the first view has only Next, the last only Back.
 *
 * onNext (optional): async check run when Next is clicked. It returns true to
 * go to the next step, or a message saying why the surveyor cannot continue
 * yet (the step stays open). While it runs Next shows a spinner and ignores
 * further clicks, so a save behind it is never submitted twice.
 * hasUnsavedChanges: ask before Back (or an unchecked Next) discards input.
 * blockedReason: when set, Next is disabled and the reason is shown next to
 * it (for example the scheduled date, or the fields still required).
 */
export default function ClaimStepNav({ claimId, current, onNext, hasUnsavedChanges = false, blockedReason = "" }) {
  const navigate = useNavigate();
  const [isChecking, setIsChecking] = useState(false);
  const [blockedMessage, setBlockedMessage] = useState("");
  const runningRef = useRef(false);

  const index = TABS.findIndex((tab) => tab.key === current);
  const previous = index > 0 ? TABS[index - 1] : null;
  const next = index >= 0 && index < TABS.length - 1 ? TABS[index + 1] : null;
  const base = `/surveyor/claims/${claimId}`;
  const to = (tab) => (tab.path ? `${base}/${tab.path}` : base);

  function confirmLeave(event) {
    if (hasUnsavedChanges && !window.confirm(UNSAVED_CHANGES_PROMPT)) event.preventDefault();
  }

  async function handleNext() {
    if (runningRef.current) return;
    runningRef.current = true;
    setIsChecking(true);
    setBlockedMessage("");
    let result;
    try {
      result = await onNext();
    } catch {
      result = "Something went wrong while checking this step. Please try again.";
    }
    runningRef.current = false;
    setIsChecking(false);
    if (result === true) navigate(to(next));
    else setBlockedMessage(result || "This step is not complete yet.");
  }

  return (
    <div className="mt-6">
      {blockedMessage && !blockedReason && (
        <p role="alert" className="mb-3 rounded-card border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          {blockedMessage}
        </p>
      )}
      {next && blockedReason && (
        <p id="next-blocked-reason" role="status" className="mb-3 text-right text-sm text-amber-800">
          {blockedReason}
        </p>
      )}
      <nav aria-label="Claim steps" className={`flex items-center gap-3 ${previous ? "justify-between" : "justify-end"}`}>
        {previous && (
          <Link to={to(previous)} className={backClass} title={`Back to ${previous.label}`} onClick={confirmLeave}>
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            Back
          </Link>
        )}
        {next && blockedReason ? (
          <button type="button" className={nextClass} title={blockedReason} aria-describedby="next-blocked-reason" disabled>
            Next
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </button>
        ) : (
          next &&
          (onNext ? (
            <button type="button" className={nextClass} title={`Next: ${next.label}`} onClick={handleNext} disabled={isChecking}>
              Next
              {isChecking ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              )}
            </button>
          ) : (
            <Link to={to(next)} className={nextClass} title={`Next: ${next.label}`} onClick={confirmLeave}>
              Next
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
          ))
        )}
      </nav>
    </div>
  );
}
