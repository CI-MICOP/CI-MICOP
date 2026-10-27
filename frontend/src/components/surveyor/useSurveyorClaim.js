import { useCallback, useEffect, useState } from "react";

import { useAuth } from "../../hooks/useAuth";
import { useFetch } from "../../hooks/useFetch";
import { getClaimById } from "../../services/claimService";
import { getAssignedClaimDetail } from "../../services/surveyorService";
import { workflowProgress } from "./workflowProgress";

// Longest delay setTimeout accepts; later schedules re-arm the timer.
const MAX_TIMEOUT_MS = 2 ** 31 - 1;

/**
 * Whether the inspection's scheduled start has arrived, kept current
 * without a page refresh. The server's own answer at load time is the
 * baseline; the timer only opens the step when the start time passes,
 * measured on the server's clock (`clockOffsetMs` = server time minus this
 * device's time at load), so a wrong device clock or time zone does not
 * change the answer. The server still enforces the schedule on every write.
 */
export function useScheduleReached(schedule, clockOffsetMs = 0) {
  const startsAt = schedule ? Date.parse(schedule.starts_at) : NaN;
  const [openedFor, setOpenedFor] = useState(null);

  useEffect(() => {
    if (!schedule || schedule.reached || Number.isNaN(startsAt)) return undefined;
    let timer;
    const arm = () => {
      const remaining = startsAt - (Date.now() + clockOffsetMs);
      if (remaining <= 0) {
        setOpenedFor(schedule.starts_at);
        return;
      }
      timer = setTimeout(arm, Math.min(remaining + 50, MAX_TIMEOUT_MS));
    };
    arm();
    return () => clearTimeout(timer);
  }, [schedule, startsAt, clockOffsetMs]);

  if (!schedule) return false;
  return Boolean(schedule.reached) || openedFor === schedule.starts_at;
}

/** A claim's details plus the authoritative workflow state, for one surveyor page. */
export function useSurveyorClaim(claimId) {
  const { user } = useAuth();
  const fetchDetail = useCallback(async () => {
    const [claim, assigned] = await Promise.all([getClaimById(claimId), getAssignedClaimDetail(claimId)]);
    const serverTime = Date.parse(assigned?.workflow?.schedule?.server_time ?? "");
    const clockOffsetMs = Number.isNaN(serverTime) ? 0 : serverTime - Date.now();
    return { claim, ...assigned, clockOffsetMs };
  }, [claimId]);
  const result = useFetch(fetchDetail, [fetchDetail]);
  const reached = useScheduleReached(result.data?.workflow?.schedule ?? null, result.data?.clockOffsetMs ?? 0);
  const progress = result.data ? workflowProgress(result.data, user?.Employee_ID, reached) : null;
  return { ...result, progress };
}
