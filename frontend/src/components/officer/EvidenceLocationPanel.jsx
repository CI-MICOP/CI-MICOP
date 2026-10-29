import { MapPin } from "lucide-react";
import { useCallback } from "react";

import { locationStatusText, locationText } from "../../components/surveyor/captureDisplay";
import { getClaimEvidenceLocations } from "../../services/officerService";
import { useFetch } from "../../hooks/useFetch";
import { getApiErrorMessage } from "../../utils/errors";
import Card from "../common/Card";
import ErrorState from "../common/ErrorState";
import LoadingState from "../common/LoadingState";
import StatusBadge from "../common/StatusBadge";

// Never treat a map-selected location as GPS-verified, however it is
// displayed - captured is the only tone that reads as confirmed/verified.
const STATUS_TONE = {
  captured: "success",
  map_selected: "info",
  accuracy_insufficient: "warning",
  unavailable: "neutral",
};

/**
 * Read-only: every surveyor-camera evidence item's location source for
 * this claim (GET .../evidence/locations), so the Claims Officer can see
 * at a glance which photos have a GPS-verified location and which were
 * recorded with the indoor-friendly map-selection fallback - never
 * presented as equivalent.
 */
export default function EvidenceLocationPanel({ claimId }) {
  const fetchLocations = useCallback(() => getClaimEvidenceLocations(claimId), [claimId]);
  const { data, isLoading, error, reload } = useFetch(fetchLocations, [fetchLocations]);

  return (
    <Card>
      <h3 className="mb-1 text-sm font-semibold text-ink">Evidence Location</h3>
      <p className="mb-4 text-xs text-muted">
        Whether each surveyor photo's location is a verified GPS reading or a map-selected fallback. Map selection is
        an indoor-friendly alternative, not proof of physical presence.
      </p>
      {isLoading ? (
        <LoadingState label="Loading evidence locations..." />
      ) : error ? (
        <ErrorState message={getApiErrorMessage(error)} onRetry={reload} />
      ) : data.evidence.length === 0 ? (
        <p className="text-sm text-muted">No surveyor-captured photos are recorded for this claim yet.</p>
      ) : (
        <ul className="divide-y divide-border" aria-label="Evidence locations">
          {data.evidence.map((item) => {
            const status = item.capture?.checks?.location_status;
            return (
              <li key={item.Evidence_ID} className="flex flex-col gap-1 py-3 text-sm sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-start gap-2">
                  <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-muted" aria-hidden="true" />
                  <div>
                    <p className="font-medium text-ink">{item.Evidence_Type}</p>
                    <p className="text-xs text-muted">{locationText(item.capture)}</p>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2 sm:justify-end">
                  <StatusBadge label={locationStatusText(item.capture)} tone={STATUS_TONE[status] ?? "neutral"} />
                  <StatusBadge
                    label={item.qualifying_capture ? "Counts as surveyor photo" : "Does not count"}
                    tone={item.qualifying_capture ? "info" : "neutral"}
                  />
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
