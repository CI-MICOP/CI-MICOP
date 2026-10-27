// The surveyor's claim workflow as the browser shows it:
// Claim Details -> Inspection -> Vehicle Damage -> Evidence -> Survey Report.
//
// Step completion, the schedule and submission come from the server
// ("workflow" in GET /surveyor/claims/{id}, computed by
// backend/app/services/surveyor_workflow.py, which also enforces every rule
// on each write). The browser only validates the form fields being edited
// and keeps the schedule check live between server refreshes.
import { TABS } from "./claimSteps";

export const UNSAVED_CHANGES_PROMPT = "You have unsaved changes on this step. Leave without saving them?";

export const SUBMIT_CONFIRM_PROMPT =
  "Submit the final survey report? Submission is final: you will no longer be able to change the inspection, " +
  "damage records or evidence for this claim.";

export const CORRECTION_PROMPT =
  "Reopen this completed step to correct it? The correction is recorded. Later steps will be checked again and may " +
  "need to be completed again before you can submit the report.";

export const PENDING = "Pending";
export const VEHICLE_CONDITION_VALUES = ["Good", "Fair", "Poor"];
export const DAMAGE_OBSERVED_VALUES = ["Yes", "No"];
export const DAMAGE_SEVERITY_VALUES = ["Minor", "Moderate", "Severe"];
export const REPAIR_RECOMMENDATION_VALUES = ["Repair", "Replace", "Total Loss"];

// Mirrors MAX_LOCATION_ACCURACY_M in backend/app/services/evidence_capture.py
// (the backend re-checks every reading).
export const MAX_LOCATION_ACCURACY_M = 100;

export const INSPECTION_FIELD_LABELS = {
  Vehicle_Condition: "Vehicle Condition",
  Damage_Observed: "Damage Observed",
  Damage_Severity: "Damage Severity",
  Parts_Required: "Parts Required",
  Repair_Recommendation: "Repair Recommendation",
};

// Step states shown to the surveyor.
export const STEP_STATE = {
  NOT_STARTED: "not_started",
  IN_PROGRESS: "in_progress",
  COMPLETED: "completed",
  LOCKED_SCHEDULE: "locked_schedule",
  LOCKED_PREREQUISITE: "locked_prerequisite",
  SUBMITTED: "submitted",
};

function choice(issues, field, value, allowed, missingMessage) {
  if (value === PENDING || value === "" || value == null) {
    issues.push({ field, kind: "missing", message: missingMessage });
  } else if (!allowed.includes(value)) {
    issues.push({
      field,
      kind: "invalid",
      message: `"${value}" is not a valid ${INSPECTION_FIELD_LABELS[field].toLowerCase()} - choose ${allowed.join(", ")}.`,
    });
  }
}

/**
 * Problems with inspection form values. `missing` problems may be saved as
 * a draft but block Next; `invalid` ones the backend rejects.
 */
export function inspectionIssues(values) {
  const issues = [];
  if (!values) return issues;
  choice(issues, "Vehicle_Condition", values.Vehicle_Condition, VEHICLE_CONDITION_VALUES, "Choose the vehicle condition.");
  choice(issues, "Damage_Observed", values.Damage_Observed, DAMAGE_OBSERVED_VALUES, "Choose whether damage was observed.");
  if (values.Damage_Observed === "Yes") {
    choice(issues, "Damage_Severity", values.Damage_Severity, DAMAGE_SEVERITY_VALUES, "Choose the damage severity (damage was observed).");
  } else if (![PENDING, ...DAMAGE_SEVERITY_VALUES].includes(values.Damage_Severity)) {
    choice(issues, "Damage_Severity", values.Damage_Severity, DAMAGE_SEVERITY_VALUES, "");
  }
  const parts = String(values.Parts_Required ?? "").trim();
  if (!/^\d+$/.test(parts)) {
    issues.push({ field: "Parts_Required", kind: "invalid", message: "Enter the number of parts required as a whole number (0 or more)." });
  }
  choice(issues, "Repair_Recommendation", values.Repair_Recommendation, REPAIR_RECOMMENDATION_VALUES, "Choose a repair recommendation.");
  return issues;
}

export function damageIssues(form) {
  const issues = [];
  if (!form.Damaged_Part.trim()) issues.push({ field: "Damaged_Part", message: "Enter the damaged part." });
  const cost = String(form.Estimated_Damage_Cost).trim();
  if (cost === "" || Number.isNaN(Number(cost)) || Number(cost) < 0) {
    issues.push({ field: "Estimated_Damage_Cost", message: "Enter the estimated cost as 0 or more." });
  }
  if (!form.Damage_Description.trim()) issues.push({ field: "Damage_Description", message: "Describe the damage." });
  return issues;
}

/** The surveyor's own inspection: the one the server's workflow names. */
export function ownInspection(detail, employeeId) {
  const inspections = detail?.inspections ?? [];
  const id = detail?.workflow?.inspection_id;
  if (id) return inspections.find((inspection) => inspection.Inspection_ID === id);
  const mine = inspections.filter((inspection) => inspection.Surveyor_ID === employeeId);
  return mine.filter((inspection) => !inspection.Survey_Report_Submitted).at(-1) ?? mine.at(-1);
}

/**
 * Step states from the server's workflow summary. `scheduleReached` is the
 * live value from useScheduleReached (the server's value at load time, kept
 * current by the clock) - the server enforces the schedule on every write.
 */
export function workflowProgress(detail, employeeId, scheduleReached) {
  const workflow = detail?.workflow ?? null;
  const inspection = ownInspection(detail, employeeId);
  const reached = Boolean(workflow) && (scheduleReached ?? workflow.schedule?.reached ?? false);
  const submitted = Boolean(workflow?.submitted);
  const inspectionComplete = Boolean(workflow?.inspection_complete);
  const damageComplete = Boolean(workflow?.damage_complete);
  const evidenceComplete = Boolean(workflow?.evidence_complete);

  const complete = { inspection: inspectionComplete, damage: damageComplete, evidence: evidenceComplete };
  const started = {
    inspection: Boolean(inspection) && !["Assigned", "Scheduled"].includes(inspection.Inspection_Status),
    damage: (workflow?.damage_count ?? 0) > 0,
    evidence: (workflow?.qualifying_photo_count ?? 0) > 0,
  };

  const steps = { details: STEP_STATE.COMPLETED };
  let prerequisitesMet = true;
  for (const key of ["inspection", "damage", "evidence", "report"]) {
    if (submitted) steps[key] = STEP_STATE.SUBMITTED;
    else if (!workflow || !reached) steps[key] = STEP_STATE.LOCKED_SCHEDULE;
    else if (!prerequisitesMet) steps[key] = STEP_STATE.LOCKED_PREREQUISITE;
    else if (key === "report") steps[key] = STEP_STATE.IN_PROGRESS;
    else if (complete[key]) steps[key] = STEP_STATE.COMPLETED;
    else steps[key] = started[key] ? STEP_STATE.IN_PROGRESS : STEP_STATE.NOT_STARTED;
    if (key !== "report" && !complete[key]) prerequisitesMet = false;
  }

  const locked = [STEP_STATE.LOCKED_SCHEDULE, STEP_STATE.LOCKED_PREREQUISITE];
  const unlocked = new Set(TABS.map((tab) => tab.key).filter((key) => !locked.includes(steps[key])));

  return {
    workflow,
    inspection,
    schedule: workflow?.schedule ?? null,
    scheduleReached: reached,
    submitted,
    inspectionComplete,
    damageRequired: Boolean(workflow?.damage_required),
    damageCount: workflow?.damage_count ?? 0,
    damageComplete,
    qualifyingPhotoCount: workflow?.qualifying_photo_count ?? 0,
    evidenceComplete,
    reportAvailable: Boolean(workflow?.report_available) && (submitted || reached),
    steps,
    unlocked,
    // Corrections the surveyor opened, recorded by the server; only inside
    // one does the server accept changes to a locked step.
    corrections: workflow?.open_corrections ?? {},
    warnings: workflow?.warnings ?? [],
    // Submitted reports only: whether the saved records still meet today's
    // submission rules (the server reports it; the submission is unchanged).
    submissionReview: workflow?.submission_review ?? null,
    // Writes are possible only on an active inspection whose time has come.
    canEdit: Boolean(workflow) && reached && !submitted,
  };
}

/** Why a step cannot be used yet, for messages next to disabled actions. */
export function lockedReason(progress) {
  if (!progress.workflow) return "No inspection is assigned to you for this claim.";
  if (!progress.scheduleReached) return progress.schedule?.message ?? "This inspection has not reached its scheduled date yet.";
  return "Complete the earlier steps first.";
}

/**
 * User-facing message for a failed survey report request. 409 means the
 * backend found the workflow incomplete (its own check, not the browser's).
 */
export function surveyReportErrorMessage(error) {
  if (!error?.response) return "Unable to connect to the CI-MICOP server. Please try again.";
  switch (error.response.status) {
    case 403:
      return "Only the surveyor assigned to this claim can view its survey report.";
    case 404:
      return "This survey report could not be found.";
    case 409:
      return "The survey report is available once the Inspection, Vehicle Damage and Evidence steps are complete.";
    default:
      return "The survey report could not be loaded. Please try again.";
  }
}

/** The backend's own explanation when it refuses a write, else a fallback. */
export function serverMessage(error, fallback) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (!error?.response) return "Unable to connect to the CI-MICOP server. Please try again.";
  return fallback;
}
