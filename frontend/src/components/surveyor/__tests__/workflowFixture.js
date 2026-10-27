// Builders for the server's "workflow" summary (GET /surveyor/claims/{id},
// computed by backend/app/services/surveyor_workflow.py), shared by the
// surveyor page tests.

export function schedule({ reached = true, date = "2026-10-28", startsAt, serverTime } = {}) {
  return {
    scheduled_date: date,
    starts_at: startsAt ?? `${date}T00:00:00+05:30`,
    has_time: false,
    timezone: "India Standard Time (UTC+05:30)",
    reached,
    server_time: serverTime ?? (reached ? "2026-10-28T10:00:00+05:30" : "2026-10-27T09:00:00+05:30"),
    message: "This inspection will become available on 28 October 2026 (India Standard Time).",
  };
}

/**
 * A workflow summary. `stage` sets the completed steps:
 * "new" | "inspection" | "damage" | "evidence" | "submitted".
 */
export function workflow(stage = "new", overrides = {}) {
  const order = ["new", "inspection", "damage", "evidence", "submitted"];
  const at = order.indexOf(stage);
  const base = {
    inspection_id: "INSP-1",
    schedule: schedule(),
    inspection_complete: at >= 1,
    incomplete_fields: at >= 1 ? [] : ["Vehicle_Condition", "Damage_Observed", "Repair_Recommendation"],
    damage_required: true,
    damage_count: at >= 2 ? 1 : 0,
    damage_complete: at >= 2,
    qualifying_photo_count: at >= 3 ? 1 : 0,
    evidence_complete: at >= 3,
    submitted: at >= 4,
    report_available: at >= 3,
  };
  return { ...base, ...overrides };
}

export const COMPLETE_INSPECTION = {
  Inspection_ID: "INSP-1",
  Claim_ID: "CLM-1",
  Surveyor_ID: "EMP-1",
  Inspection_Date: "2026-10-28",
  Inspection_Location: "Chennai",
  Vehicle_Condition: "Fair",
  Damage_Observed: "Yes",
  Damage_Severity: "Minor",
  Parts_Required: 2,
  Repair_Recommendation: "Repair",
  Surveyor_Comments: "",
  Inspection_Status: "In Progress",
  Survey_Report_Submitted: false,
  Surveyor_Confidence_Score: 0,
};

export const NEW_INSPECTION = {
  ...COMPLETE_INSPECTION,
  Vehicle_Condition: "Pending",
  Damage_Observed: "Pending",
  Damage_Severity: "Pending",
  Parts_Required: 0,
  Repair_Recommendation: "Pending",
  Inspection_Status: "Assigned",
};
