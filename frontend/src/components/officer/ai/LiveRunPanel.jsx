import { AlertTriangle, Info, PlayCircle } from "lucide-react";
import { useState } from "react";

import Button from "../../common/Button";
import Card from "../../common/Card";
import StatusBadge from "../../common/StatusBadge";
import { runAiAnalysis } from "../../../services/officerService";
import { getApiErrorMessage } from "../../../utils/errors";
import { signalLabel } from "../../../utils/aiSignalLabels";

// "Completed"/"Unavailable" are reserved for a future pipeline that can
// compute more than 2 of the 7 defined signal families live - the
// current pipeline can only ever reach "insufficient_evidence" or
// "partial" (see docs/project_documentation/LIVE_AI_PIPELINE.md).
const STATUS_LABEL = {
  ready: "Ready",
  running: "Running",
  completed: "Completed",
  insufficient_evidence: "Insufficient Evidence",
  partial: "Partially Available",
  unavailable: "Unavailable",
  error: "Error",
};

const STATUS_TONE = {
  ready: "neutral",
  running: "info",
  completed: "success",
  insufficient_evidence: "warning",
  partial: "info",
  unavailable: "neutral",
  error: "danger",
};

/**
 * "Run AI Analysis" button + on-demand live pipeline result (Step
 * 5.8.11). This calls a SEPARATE endpoint (POST .../ai-analysis/run)
 * from the read-only GET panel above it (LiveAiAnalysisPanel.jsx,
 * Step 5.8.10) - the run result is analyze-only and is never persisted,
 * so it is displayed here directly rather than by mutating that panel.
 * `onAfterRun` lets the page also refresh the read-only panel, matching
 * the existing "refresh the existing live AI panel" convention.
 */
export default function LiveRunPanel({ claimId, onAfterRun }) {
  const [state, setState] = useState({ status: "ready", result: null, message: "" });

  async function handleRun() {
    setState({ status: "running", result: null, message: "" });
    try {
      const result = await runAiAnalysis(claimId);
      setState({ status: result.status, result, message: "" });
      onAfterRun?.();
    } catch (err) {
      setState({ status: "error", result: null, message: getApiErrorMessage(err) });
    }
  }

  return (
    <Card className="mb-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-ink">Live AI Analysis</h3>
          <p className="mt-1 text-sm text-muted">
            Analyzes this claim's actual current data on demand, rather than a precomputed research export.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge label={STATUS_LABEL[state.status]} tone={STATUS_TONE[state.status]} />
          <Button onClick={handleRun} isLoading={state.status === "running"}>
            <PlayCircle className="h-4 w-4" aria-hidden="true" />
            Run AI Analysis
          </Button>
        </div>
      </div>

      <p className="mt-4 flex items-center gap-2 rounded-card border border-brand-200 bg-brand-50 p-3 text-sm text-brand-800">
        <Info className="h-4 w-4 shrink-0" aria-hidden="true" />
        AI-assisted analysis. Final claim decision remains with the Claims Officer.
      </p>

      {state.status === "error" && (
        <p className="mt-4 text-sm text-danger">{state.message}</p>
      )}

      {state.result && (
        <div className="mt-4 space-y-4 border-t border-border pt-4">
          <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-5">
            <Detail label="Documents" value={state.result.evidence_summary.documents} />
            <Detail label="Vehicle Damage" value={state.result.evidence_summary.vehicle_damage} />
            <Detail label="Evidence" value={state.result.evidence_summary.evidence} />
            <Detail label="Repair Estimates" value={state.result.evidence_summary.repair_estimates} />
            <Detail label="Inspections" value={state.result.evidence_summary.inspections} />
          </dl>

          {state.status === "insufficient_evidence" ? (
            <div className="flex items-start gap-2 rounded-card border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
              <p>Not enough live data exists yet for a reliable combined result - see the signals below.</p>
            </div>
          ) : (
            <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-3">
              <Detail label="Risk Band" value={state.result.risk_band ?? "N/A"} />
              <Detail
                label="Risk Score"
                value={state.result.overall_risk_score !== null ? state.result.overall_risk_score.toFixed(3) : "N/A"}
              />
              <Detail label="Confidence Band" value={state.result.confidence_band ?? "N/A"} />
            </dl>
          )}

          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">Signals</p>
            <ul className="space-y-2">
              {state.result.signals.map((signal) => (
                <li key={signal.signal_name} className="rounded-card border border-border p-3 text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-medium text-ink">{signalLabel(signal.signal_name)}</span>
                    <StatusBadge
                      label={signal.availability === "available" ? "Available" : "Not Available"}
                      tone={signal.availability === "available" ? "success" : "neutral"}
                    />
                  </div>
                  <p className="mt-1 text-ink">{signal.explanation}</p>
                </li>
              ))}
            </ul>
          </div>

          {state.result.limitations.length > 0 && (
            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">Limitations</p>
              <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
                {state.result.limitations.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

function Detail({ label, value }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-muted">{label}</dt>
      <dd className="text-ink">{value}</dd>
    </div>
  );
}
