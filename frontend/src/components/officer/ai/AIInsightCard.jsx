import { BadgeCheck, ShieldAlert } from "lucide-react";

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

/**
 * The complete "AI Risk Insights" panel for one claim (Step 5.5, Part 3).
 * `insight` is the object returned by
 * `aiRiskService.getAiInsightsForClaim(claimId)` - `null` means Step 5.4
 * produced no result for this claim, which is rendered as an explicit
 * empty state, never a fabricated score.
 *
 * This component is READ-ONLY: it has no decision buttons and calls no
 * write endpoint. The officer's actual decision stays on the separate
 * "Make Decision" tab (see AiInsightsPage.jsx / DecisionPage.jsx).
 */
export default function AIInsightCard({ insight, demoLabel }) {
  if (!insight) {
    return (
      <Card>
        <EmptyState
          icon={ShieldAlert}
          title="No AI risk assessment available for this claim"
          message="This claim is outside the Step 5.4 research-prototype dataset, so no AI risk insight was generated for it."
        />
      </Card>
    );
  }

  const isHighRiskLowConfidence = HIGH_RISK_BANDS.has(insight.riskBand) && UNRELIABLE_CONFIDENCE.has(insight.confidenceBand);
  const isInsufficientEvidence = insight.confidenceBand === "INSUFFICIENT_EVIDENCE";
  const noticeVariant = isInsufficientEvidence ? "insufficientEvidence" : isHighRiskLowConfidence ? "highRiskLowConfidence" : "default";

  return (
    <div className="space-y-6">
      {demoLabel && (
        <p className="rounded-card border border-dashed border-brand-300 bg-brand-50 px-3 py-2 text-xs font-medium uppercase tracking-wide text-brand-700">
          AI Demonstration Example — {demoLabel}
        </p>
      )}

      <HumanReviewNotice variant={noticeVariant} />

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <RiskScoreCard riskScoreOn100={insight.riskScoreOn100} riskBand={insight.riskBand} />
        <ConfidenceCard
          confidenceOn100={insight.confidenceOn100}
          confidenceBand={insight.confidenceBand}
          uncertaintyReasons={insight.uncertaintyReasons}
        />
      </div>

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-ink">Review Priority</h3>
            <p className="mt-1 text-sm text-muted">{reviewPriorityMessage(insight.reviewPriority, insight.confidenceBand)}</p>
          </div>
          <StatusBadge
            label={REVIEW_PRIORITY_LABEL[insight.reviewPriority] ?? insight.reviewPriority}
            tone={REVIEW_PRIORITY_TONE[insight.reviewPriority] ?? "neutral"}
          />
        </div>
        <div className="mt-4 flex items-center gap-2 border-t border-border pt-4 text-sm">
          <BadgeCheck className="h-4 w-4 shrink-0 text-brand-600" aria-hidden="true" />
          <span className="text-ink">Human Review Required:</span>
          <span className="font-medium text-ink">{insight.humanReviewRequired ? "YES" : "NO"}</span>
        </div>
        <dl className="mt-4 grid grid-cols-2 gap-4 border-t border-border pt-4 text-sm">
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-muted">Contributing Signals</dt>
            <dd className="mt-0.5 text-ink">{insight.contributingSignalCount} of 7</dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-muted">Unavailable Signals</dt>
            <dd className="mt-0.5 text-ink">{insight.unavailableSignalCount} of 7</dd>
          </div>
        </dl>
      </Card>

      <ReasonCodeList reasonCodes={insight.reasonCodes} officerExplanations={insight.officerExplanations} />

      <SignalBreakdown signals={insight.signals} />

      <Card>
        <h3 className="mb-2 text-sm font-semibold text-ink">Explanation</h3>
        <p className="text-sm text-ink">{insight.plainLanguageExplanation}</p>
      </Card>

      <HumanReviewNotice />
    </div>
  );
}
