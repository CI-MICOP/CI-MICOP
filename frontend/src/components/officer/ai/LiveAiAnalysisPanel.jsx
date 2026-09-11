import Card from "../../common/Card";
import EmptyState from "../../common/EmptyState";
import StatusBadge from "../../common/StatusBadge";
import { REVIEW_PRIORITY_LABEL, REVIEW_PRIORITY_TONE, reviewPriorityMessage } from "../../../utils/aiReviewPriority";
import ConfidenceCard from "./ConfidenceCard";
import HumanReviewNotice from "./HumanReviewNotice";
import ReasonCodeList from "./ReasonCodeList";
import RiskScoreCard from "./RiskScoreCard";
import SignalBreakdown from "./SignalBreakdown";

const UNRELIABLE_CONFIDENCE = new Set(["LOW_CONFIDENCE", "INSUFFICIENT_EVIDENCE"]);
const HIGH_RISK_BANDS = new Set(["HIGH", "CRITICAL"]);

function scaleTo100(value) {
  return value === null || value === undefined ? null : Math.round(value * 100);
}

/**
 * Live GET /officer/claims/{claimId}/ai-analysis panel (Step 5.8.10) -
 * the "AI/ML -> FastAPI -> React" integration point. Reuses the exact
 * same leaf components the Step 5.5 static demo (AIInsightCard.jsx)
 * already established (RiskScoreCard/ConfidenceCard/SignalBreakdown/
 * ReasonCodeList/HumanReviewNotice) so the visual language and
 * human-in-the-loop wording stay identical - only the data source is
 * live now. `analysis` is the raw AiClaimAnalysisOut response; `null`
 * means still loading (the caller handles the loading state).
 *
 * This component is READ-ONLY: no buttons, no form controls, no write
 * call - the officer's decision stays on the separate "Make Decision"
 * tab (DecisionPage.jsx / POST /officer/claims/{id}/decision).
 */
export default function LiveAiAnalysisPanel({ analysis }) {
  if (!analysis) return null;

  const isHighRiskLowConfidence =
    HIGH_RISK_BANDS.has(analysis.overall_risk) && UNRELIABLE_CONFIDENCE.has(analysis.confidence_band);
  const isInsufficientEvidence = analysis.confidence_band === "INSUFFICIENT_EVIDENCE";
  const noticeVariant = isInsufficientEvidence
    ? "insufficientEvidence"
    : isHighRiskLowConfidence
      ? "highRiskLowConfidence"
      : "default";

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-base font-semibold text-ink">AI Claim Analysis</h2>
        <p className="mt-1 text-sm text-muted">AI-assisted analysis — final decision remains with Claims Officer.</p>
      </div>

      <HumanReviewNotice variant={noticeVariant} />

      {!analysis.available ? (
        <Card>
          <EmptyState
            title="No overall AI risk assessment available for this claim"
            message="This claim is outside the Step 5.4 research-prototype dataset (654 claims), so no overall risk/confidence score was generated for it. The sections below still show any available fraud, consistency, and repair-estimate analysis."
          />
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
            <RiskScoreCard riskScoreOn100={scaleTo100(analysis.risk_score)} riskBand={analysis.overall_risk} />
            <ConfidenceCard
              confidenceOn100={scaleTo100(analysis.confidence_score)}
              confidenceBand={analysis.confidence_band}
            />
          </div>

          <Card>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-ink">Review Priority</h3>
                <p className="mt-1 text-sm text-muted">
                  {reviewPriorityMessage(analysis.review_priority, analysis.confidence_band)}
                </p>
              </div>
              <StatusBadge
                label={REVIEW_PRIORITY_LABEL[analysis.review_priority] ?? analysis.review_priority}
                tone={REVIEW_PRIORITY_TONE[analysis.review_priority] ?? "neutral"}
              />
            </div>
            <div className="mt-4 flex items-center gap-2 border-t border-border pt-4 text-sm">
              <span className="text-ink">Human Review Required:</span>
              <span className="font-medium text-ink">{analysis.human_review_required ? "YES" : "NO"}</span>
            </div>
            {analysis.contributing_signal_count !== null && (
              <dl className="mt-4 grid grid-cols-2 gap-4 border-t border-border pt-4 text-sm">
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-muted">Contributing Signals</dt>
                  <dd className="mt-0.5 text-ink">{analysis.contributing_signal_count} of 7</dd>
                </div>
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-muted">Unavailable Signals</dt>
                  <dd className="mt-0.5 text-ink">{analysis.unavailable_signal_count} of 7</dd>
                </div>
              </dl>
            )}
          </Card>

          <ReasonCodeList reasonCodes={analysis.reason_codes} officerExplanations={analysis.officer_explanations} />
          <SignalBreakdown signals={analysis.signals} />

          {analysis.explanation.length > 0 && (
            <Card>
              <h3 className="mb-2 text-sm font-semibold text-ink">Explanation</h3>
              {analysis.explanation.map((line) => (
                <p key={line} className="text-sm text-ink">{line}</p>
              ))}
            </Card>
          )}
        </>
      )}

      <FraudAnalysisCard fraud={analysis.fraud_analysis} />
      <ConsistencyAnalysisCard consistency={analysis.consistency_analysis} />
      <RepairEstimateAnalysisCard repairEstimate={analysis.repair_estimate_analysis} />

      {analysis.limitations.length > 0 && (
        <Card>
          <h3 className="mb-2 text-sm font-semibold text-ink">Limitations</h3>
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
            {analysis.limitations.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </Card>
      )}

      <HumanReviewNotice />
    </div>
  );
}

function FraudAnalysisCard({ fraud }) {
  return (
    <Card>
      <h3 className="mb-3 text-sm font-semibold text-ink">Fraud / Risk Signals</h3>
      {!fraud.available ? (
        <EmptyState title="Fraud risk analysis unavailable" message={fraud.message} />
      ) : (
        <>
          <dl className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Detail label="Risk Category">
              <StatusBadge label={fraud.risk_category} tone="warning" />
            </Detail>
            <Detail label="Fraud Risk Score" value={fraud.fraud_risk_score} />
            <Detail label="Anomaly Score" value={fraud.anomaly_score} />
          </dl>
          {fraud.reason_codes.length > 0 && (
            <ul className="mt-4 flex flex-wrap gap-2 border-t border-border pt-4">
              {fraud.reason_codes.map((code) => (
                <li key={code}>
                  <StatusBadge label={code} tone="warning" />
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </Card>
  );
}

function ConsistencyAnalysisCard({ consistency }) {
  return (
    <Card>
      <h3 className="mb-3 text-sm font-semibold text-ink">Consistency Analysis</h3>
      {!consistency.available ? (
        <EmptyState title="Cross-document consistency analysis unavailable" message={consistency.message} />
      ) : (
        <>
          <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Detail label="Overall Status">
              <StatusBadge label={consistency.overall_status} tone={consistency.overall_status === "Match" ? "success" : "warning"} />
            </Detail>
            <Detail label="Consistency Score" value={consistency.document_consistency_score} />
          </dl>
          {consistency.contradictions.length > 0 ? (
            <ul className="mt-4 space-y-1 border-t border-border pt-4 text-sm text-ink">
              {consistency.contradictions.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-4 border-t border-border pt-4 text-sm text-muted">No contradictions found.</p>
          )}
        </>
      )}
    </Card>
  );
}

function RepairEstimateAnalysisCard({ repairEstimate }) {
  return (
    <Card>
      <h3 className="mb-3 text-sm font-semibold text-ink">Repair Estimate Analysis</h3>
      {!repairEstimate.available ? (
        <EmptyState title="Repair estimate analysis unavailable" message={repairEstimate.message} />
      ) : (
        <>
          <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Detail label="Anomaly Detected">
              <StatusBadge
                label={repairEstimate.anomaly_detected ? "Yes" : "No"}
                tone={repairEstimate.anomaly_detected ? "danger" : "success"}
              />
            </Detail>
            <Detail label="Anomaly Score" value={repairEstimate.anomaly_score} />
          </dl>
          {repairEstimate.reason_codes.length > 0 && (
            <ul className="mt-4 flex flex-wrap gap-2 border-t border-border pt-4">
              {repairEstimate.reason_codes.map((code) => (
                <li key={code}>
                  <StatusBadge label={code} tone="warning" />
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </Card>
  );
}

function Detail({ label, value, children }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-muted">{label}</dt>
      <dd className="mt-0.5 text-sm text-ink">{children ?? value}</dd>
    </div>
  );
}
