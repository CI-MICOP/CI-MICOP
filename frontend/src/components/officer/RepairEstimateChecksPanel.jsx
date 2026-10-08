import { ClipboardCheck } from "lucide-react";
import { useState } from "react";

import Button from "../common/Button";
import Card from "../common/Card";
import StatusBadge from "../common/StatusBadge";
import { checkRepairEstimates } from "../../services/officerService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatCurrency, formatDate } from "../../utils/format";

const ESTIMATE_TONE = {
  POINTS_TO_REVIEW: "warning",
  NO_POINTS_FOUND: "success",
  UNAVAILABLE: "neutral",
};

const ESTIMATE_LABEL = {
  POINTS_TO_REVIEW: "Points to review",
  NO_POINTS_FOUND: "No points found",
  UNAVAILABLE: "Unavailable",
};

const CHECK_TONE = {
  FLAGGED: "warning",
  NOT_FLAGGED: "success",
  INFO: "info",
  UNAVAILABLE: "neutral",
};

const CHECK_STATUS_LABEL = {
  FLAGGED: "Review",
  NOT_FLAGGED: "No point found",
  INFO: "For information",
  UNAVAILABLE: "Unavailable",
};

const CHECK_LABEL = {
  ESTIMATE_DATE: "Estimate date",
  CLAIM_AMOUNT_RATIO: "Estimate vs claim amount",
  REPLACEMENT_PARTS: "Replaced parts vs damage recorded",
  COST_VS_ESTIMATE: "Repair cost vs estimate",
  DAMAGE_COST_RATIO: "Estimate vs surveyor's damage cost",
  REPAIR_DAYS: "Repair days",
};

/**
 * Officer-side view of the Step 5.8.21 repair estimate checks
 * (POST .../repair-estimates/check). One explicit, read-only action -
 * nothing runs on page load and nothing is saved. Each check is shown on
 * its own; there is no combined score, and "For information" rows carry no
 * verdict.
 */
export default function RepairEstimateChecksPanel({ claimId }) {
  const [check, setCheck] = useState({ status: "idle", result: null, message: "" });

  async function handleCheck() {
    setCheck({ status: "running", result: null, message: "" });
    try {
      const result = await checkRepairEstimates(claimId);
      setCheck({ status: "done", result, message: "" });
    } catch (err) {
      setCheck({ status: "error", result: null, message: getApiErrorMessage(err) });
    }
  }

  return (
    <Card className="mb-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-ink">Estimate Checks</h3>
          <p className="mt-1 text-sm text-muted">
            Sets each repair estimate against this claim's amount, accident date and the surveyor's damage records.
          </p>
        </div>
        <Button variant="secondary" onClick={handleCheck} isLoading={check.status === "running"} disabled={check.status === "running"}>
          <ClipboardCheck className="h-4 w-4" aria-hidden="true" />
          Check Estimates
        </Button>
      </div>

      {check.status === "error" && <p className="mt-4 text-sm text-danger">Estimate check failed: {check.message}</p>}
      {check.result && <Results result={check.result} />}
    </Card>
  );
}

function Results({ result }) {
  if (result.estimates_checked === 0) {
    return (
      <p className="mt-4 border-t border-border pt-4 text-sm text-muted">
        This claim has no repair estimates to check yet.
      </p>
    );
  }

  return (
    <div className="mt-4 space-y-3 border-t border-border pt-4 text-sm">
      <ul className="space-y-3">
        {result.results.map((estimate) => (
          <li key={estimate.estimate_id} className="rounded-card border border-border p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="min-w-0 truncate font-medium text-ink">
                {estimate.estimate_id}{" "}
                <span className="font-normal text-muted">
                  ({estimate.garage_id}, {formatDate(estimate.estimate_date)}, {formatCurrency(estimate.repair_estimate)})
                </span>
              </span>
              <StatusBadge label={ESTIMATE_LABEL[estimate.status] ?? estimate.status} tone={ESTIMATE_TONE[estimate.status] ?? "neutral"} />
            </div>
            <ul className="mt-3 space-y-3">
              {estimate.checks.map((item) => (
                <li key={item.check} data-check={item.check}>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-medium uppercase tracking-wide text-muted">
                      {CHECK_LABEL[item.check] ?? item.check}
                    </span>
                    <StatusBadge label={CHECK_STATUS_LABEL[item.status] ?? item.status} tone={CHECK_TONE[item.status] ?? "neutral"} />
                  </div>
                  <p className="mt-1 text-ink">{item.explanation}</p>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>

      {result.quote_comparison && (
        <div className="rounded-card border border-border p-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium uppercase tracking-wide text-muted">Estimates side by side</span>
            <StatusBadge label={CHECK_STATUS_LABEL.INFO} tone={CHECK_TONE.INFO} />
          </div>
          <p className="mt-1 text-ink">{result.quote_comparison.explanation}</p>
        </div>
      )}

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
