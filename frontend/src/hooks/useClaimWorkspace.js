import { useCallback } from "react";

import { getClaimWorkspaceData } from "../services/officerService";
import { useFetch } from "./useFetch";

/** Shared data source for every officer per-claim tab (Details, Fraud
 * Risk, AI Insights, Consistency, Estimate, Decision). */
export function useClaimWorkspace(claimId) {
  const fetcher = useCallback(() => getClaimWorkspaceData(claimId), [claimId]);
  return useFetch(fetcher, [fetcher]);
}
