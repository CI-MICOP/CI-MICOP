import Card from "../../common/Card";
import StatusBadge from "../../common/StatusBadge";

const RISK_BAND_TONE = { CRITICAL: "danger", HIGH: "danger", MEDIUM: "warning", LOW: "success", UNSCORED: "neutral" };

/**
 * Risk axis only - never mixes in confidence (see ConfidenceCard, kept as
 * a fully separate component/card so the two axes cannot visually merge
 * into one "AI confidence = risk" number).
 */
export default function RiskScoreCard({ riskScoreOn100, riskBand }) {
  return (
    <Card>
      <h3 className="mb-1 text-sm font-semibold text-ink">Risk Score</h3>
      <p className="text-2xl font-semibold text-ink">
        {riskScoreOn100 ?? "N/A"}
        {riskScoreOn100 !== null && <span className="text-base font-normal text-muted"> / 100</span>}
      </p>
      <div className="mt-2">
        <StatusBadge label={riskBand ?? "UNSCORED"} tone={RISK_BAND_TONE[riskBand] ?? "neutral"} />
      </div>
      <p className="mt-3 text-xs text-muted">
        Risk indicates the strength of available warning signals. It is a prototype research score, not a
        validated insurance risk threshold.
      </p>
    </Card>
  );
}
