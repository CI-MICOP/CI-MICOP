import Card from "../../common/Card";
import EmptyState from "../../common/EmptyState";
import StatusBadge from "../../common/StatusBadge";
import { contributionLevel, signalLabel, signalStatus, STATUS_TONE } from "../../../utils/aiSignalLabels";

/**
 * Per-signal breakdown (Step 5.4 Part A "signals"). Only renders signals
 * Step 5.4 actually computed for this claim - an unavailable signal is
 * shown explicitly as "Not Available", never silently omitted or
 * invented with a placeholder value.
 */
export default function SignalBreakdown({ signals }) {
  if (!signals || signals.length === 0) {
    return (
      <Card>
        <h3 className="mb-3 text-sm font-semibold text-ink">Signal Breakdown</h3>
        <EmptyState
          title="Full signal breakdown not generated for this claim"
          message="Step 5.4 generated a full per-signal breakdown only for its representative demonstration examples. See “AI Demonstration Examples” below to view one."
        />
      </Card>
    );
  }

  return (
    <Card>
      <h3 className="mb-4 text-sm font-semibold text-ink">Signal Breakdown</h3>
      <ul className="space-y-3">
        {signals.map((signal) => {
          const status = signalStatus(signal);
          const level = contributionLevel(signal.signal_value);
          return (
            <li key={signal.signal_name} className="rounded-card border border-border p-3">
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm font-medium text-ink">{signalLabel(signal.signal_name)}</span>
                <StatusBadge label={status} tone={STATUS_TONE[status]} />
              </div>
              <p className="mt-1 text-xs text-muted">
                Contribution: {level ?? "Not available"}
              </p>
              <p className="mt-1 text-sm text-ink">{signal.explanation}</p>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
