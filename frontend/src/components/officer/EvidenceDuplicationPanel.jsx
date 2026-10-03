import { Images, Info } from "lucide-react";
import { useState } from "react";

import Button from "../common/Button";
import Card from "../common/Card";
import StatusBadge from "../common/StatusBadge";
import { checkEvidenceDuplication } from "../../services/officerService";
import { getApiErrorMessage } from "../../utils/errors";

// A copy found is "needs review" (warning), never an accusation (danger).
// NO_MATCH_FOUND stays neutral rather than green: not finding a copy among
// this application's own photos does not prove a photo is original.
const STATUS_TONE = {
  EXACT_DUPLICATE: "warning",
  NEAR_DUPLICATE: "warning",
  NO_MATCH_FOUND: "neutral",
  UNAVAILABLE: "neutral",
};

const STATUS_LABEL = {
  EXACT_DUPLICATE: "Exact copy found",
  NEAR_DUPLICATE: "Near copy found",
  NO_MATCH_FOUND: "No copy found",
  UNAVAILABLE: "Unavailable",
};

/**
 * Officer-side view of the Step 5.8.14 evidence duplication check
 * (POST .../evidence/duplication-check). One explicit, read-only action -
 * nothing runs on page load, nothing is saved, and nothing here calls the
 * decision workflow.
 */
export default function EvidenceDuplicationPanel({ claimId }) {
  const [check, setCheck] = useState({ status: "idle", result: null, message: "" });

  async function handleCheck() {
    setCheck({ status: "running", result: null, message: "" });
    try {
      const result = await checkEvidenceDuplication(claimId);
      setCheck({ status: "done", result, message: "" });
    } catch (err) {
      setCheck({ status: "error", result: null, message: getApiErrorMessage(err) });
    }
  }

  return (
    <Card className="mb-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-ink">Evidence Photo Check</h3>
          <p className="mt-1 text-sm text-muted">
            Compares each photo on this claim with every other evidence photo stored in CI-MICOP, on this claim and
            on other claims.
          </p>
        </div>
        <Button onClick={handleCheck} isLoading={check.status === "running"} disabled={check.status === "running"}>
          <Images className="h-4 w-4" aria-hidden="true" />
          Check Photos
        </Button>
      </div>

      <p className="mt-4 flex items-center gap-2 rounded-card border border-brand-200 bg-brand-50 p-3 text-sm text-brand-800">
        <Info className="h-4 w-4 shrink-0" aria-hidden="true" />
        Investigative findings for officer review only. A copied photo can have an innocent explanation and is not an
        accusation of wrongdoing. Final claim decision remains with the Claims Officer.
      </p>

      {check.status === "error" && <p className="mt-4 text-sm text-danger">Photo check failed: {check.message}</p>}
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
      <p className="text-ink">
        <span className="font-medium">{result.photos_checked}</span> photo(s) on this claim checked against{" "}
        <span className="font-medium">{result.photos_compared_against}</span> readable stored photo(s).
      </p>

      <ul className="space-y-3">
        {result.results.map((photo) => (
          <li key={photo.evidence_id} className="rounded-card border border-border p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="min-w-0 truncate font-medium text-ink">
                {photo.file_name} <span className="font-normal text-muted">({photo.evidence_id})</span>
              </span>
              <StatusBadge label={STATUS_LABEL[photo.status] ?? photo.status} tone={STATUS_TONE[photo.status] ?? "neutral"} />
            </div>
            <p className="mt-0.5 text-xs text-muted">{photo.evidence_type}</p>
            <p className="mt-2 text-ink">{photo.explanation}</p>
            {photo.matches.length > 0 && (
              <ul className="mt-2 space-y-1 text-xs">
                {photo.matches.map((match) => (
                  <li key={match.evidence_id} className="flex flex-wrap items-center gap-2 text-muted">
                    <StatusBadge label={match.match_type === "EXACT" ? "Exact" : "Near"} tone="warning" />
                    <span className="text-ink">{match.evidence_id}</span>
                    <span>{match.same_claim ? "same claim" : `claim ${match.claim_id}`}</span>
                    {match.match_type === "NEAR" && match.hash_distance !== null && (
                      <span>· {match.hash_distance} of 64 fingerprint bits differ</span>
                    )}
                  </li>
                ))}
              </ul>
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
