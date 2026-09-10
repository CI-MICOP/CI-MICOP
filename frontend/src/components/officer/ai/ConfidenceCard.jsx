import Card from "../../common/Card";
import StatusBadge from "../../common/StatusBadge";

const CONFIDENCE_BAND_TONE = {
  HIGH_CONFIDENCE: "success",
  MEDIUM_CONFIDENCE: "info",
  LOW_CONFIDENCE: "warning",
  INSUFFICIENT_EVIDENCE: "danger",
};

const CONFIDENCE_BAND_LABEL = {
  HIGH_CONFIDENCE: "HIGH",
  MEDIUM_CONFIDENCE: "MEDIUM",
  LOW_CONFIDENCE: "LOW",
  INSUFFICIENT_EVIDENCE: "INSUFFICIENT EVIDENCE",
};

/**
 * Confidence axis only - deliberately a separate card from RiskScoreCard.
 * Step 5.4's central research point is that risk and confidence are
 * independent: a claim can be high-risk with low confidence, so this
 * component never derives its value from the risk score.
 */
export default function ConfidenceCard({ confidenceOn100, confidenceBand, uncertaintyReasons = [] }) {
  return (
    <Card>
      <h3 className="mb-1 text-sm font-semibold text-ink">Confidence</h3>
      <p className="text-2xl font-semibold text-ink">
        {confidenceOn100 ?? "N/A"}
        {confidenceOn100 !== null && <span className="text-base font-normal text-muted"> / 100</span>}
      </p>
      <div className="mt-2">
        <StatusBadge label={CONFIDENCE_BAND_LABEL[confidenceBand] ?? confidenceBand ?? "UNKNOWN"} tone={CONFIDENCE_BAND_TONE[confidenceBand] ?? "neutral"} />
      </div>
      <p className="mt-3 text-xs text-muted">
        Confidence indicates how reliable and complete the available evidence and signals are - it is not a
        measure of risk.
      </p>
      {uncertaintyReasons.length > 0 && (
        <ul className="mt-3 space-y-1 border-t border-border pt-3 text-xs text-muted">
          {uncertaintyReasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      )}
    </Card>
  );
}
