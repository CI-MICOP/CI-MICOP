import { CheckCircle2, Lock } from "lucide-react";
import { NavLink } from "react-router-dom";

import { TABS } from "./claimSteps";
import { STEP_STATE, UNSAVED_CHANGES_PROMPT } from "./workflowProgress";

const LOCK_TITLES = {
  [STEP_STATE.LOCKED_SCHEDULE]: "Available from the scheduled inspection date",
  [STEP_STATE.LOCKED_PREREQUISITE]: "Complete the earlier steps first",
};

/**
 * Horizontal tab strip for moving between the views of one claim (order =
 * TABS). With `progress` (from workflowProgress) each tab shows its state:
 * locked until the scheduled date, locked until earlier steps are complete,
 * or completed. Without it every tab is open. `hasUnsavedChanges` asks
 * before a tab click discards the current form.
 */
export default function ClaimTabs({ claimId, progress, hasUnsavedChanges = false }) {
  const base = `/surveyor/claims/${claimId}`;
  const steps = progress?.steps ?? {};

  function confirmLeave(event) {
    if (hasUnsavedChanges && !window.confirm(UNSAVED_CHANGES_PROMPT)) event.preventDefault();
  }

  return (
    <nav className="mb-6 flex gap-1 overflow-x-auto border-b border-border" aria-label="Claim sections">
      {TABS.map((tab) => {
        const state = steps[tab.key];
        if (progress && !progress.unlocked.has(tab.key)) {
          return (
            <span
              key={tab.key}
              aria-disabled="true"
              title={LOCK_TITLES[state] ?? "Not available yet"}
              className="inline-flex shrink-0 cursor-not-allowed items-center gap-1 border-b-2 border-transparent px-3 py-2 text-sm font-medium text-muted/50"
            >
              <Lock className="h-3 w-3" aria-hidden="true" />
              {tab.label}
            </span>
          );
        }
        const done = tab.key !== "details" && (state === STEP_STATE.COMPLETED || state === STEP_STATE.SUBMITTED);
        return (
          <NavLink
            key={tab.key}
            to={tab.path ? `${base}/${tab.path}` : base}
            end
            onClick={confirmLeave}
            title={done ? (state === STEP_STATE.SUBMITTED ? "Submitted" : "Completed") : undefined}
            className={({ isActive }) =>
              `inline-flex shrink-0 items-center gap-1 border-b-2 px-3 py-2 text-sm font-medium ${
                isActive ? "border-brand-600 text-brand-700" : "border-transparent text-muted hover:text-ink"
              }`
            }
          >
            {done && <CheckCircle2 className="h-3.5 w-3.5 text-success" aria-hidden="true" />}
            {tab.label}
          </NavLink>
        );
      })}
    </nav>
  );
}
