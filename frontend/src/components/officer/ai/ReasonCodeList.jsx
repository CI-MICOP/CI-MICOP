import Card from "../../common/Card";
import EmptyState from "../../common/EmptyState";
import StatusBadge from "../../common/StatusBadge";

const SEVERITY_TONE = { HIGH: "danger", MEDIUM: "warning", LOW: "info" };

/**
 * Reason codes are decision-support wording ("AI risk signal: ...") -
 * never a verdict. `officerExplanations` (title/detail/severity), when
 * available, is preferred over the bare code list.
 */
export default function ReasonCodeList({ reasonCodes = [], officerExplanations }) {
  if (reasonCodes.length === 0) {
    return (
      <Card>
        <h3 className="mb-3 text-sm font-semibold text-ink">Reason Codes</h3>
        <EmptyState title="No risk signals reached the reporting threshold for this claim" />
      </Card>
    );
  }

  return (
    <Card>
      <h3 className="mb-4 text-sm font-semibold text-ink">Reason Codes</h3>
      {officerExplanations && officerExplanations.length > 0 ? (
        <ul className="space-y-3">
          {officerExplanations.map((item) => (
            <li key={item.code} className="rounded-card border border-border p-3">
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm font-medium text-ink">{item.title}</span>
                <StatusBadge label={item.severity} tone={SEVERITY_TONE[item.severity] ?? "neutral"} />
              </div>
              <p className="mt-1 text-sm text-ink">{item.officer_explanation}</p>
              <p className="mt-1 text-xs text-muted">{item.detail}</p>
            </li>
          ))}
        </ul>
      ) : (
        <ul className="flex flex-wrap gap-2">
          {reasonCodes.map((code) => (
            <li key={code}>
              <StatusBadge label={code} tone="warning" />
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
