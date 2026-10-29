import { useCallback, useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import BackButton from "../../components/common/BackButton";
import Breadcrumbs from "../../components/common/Breadcrumbs";
import Card from "../../components/common/Card";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import AIInsightCard from "../../components/officer/ai/AIInsightCard";
import LiveAiAnalysisPanel from "../../components/officer/ai/LiveAiAnalysisPanel";
import LiveRunPanel from "../../components/officer/ai/LiveRunPanel";
import ClaimTabs from "../../components/officer/ClaimTabs";
import ClaimWorkspaceError from "../../components/officer/ClaimWorkspaceError";
import { useClaimWorkspace } from "../../hooks/useClaimWorkspace";
import { useFetch } from "../../hooks/useFetch";
import { getAiInsightsForClaim, listDemonstrationExamples } from "../../services/aiRiskService";
import { getAiAnalysis } from "../../services/officerService";

/**
 * Step 5.8.10: the currently-open claim's AI analysis is now live -
 * GET /officer/claims/{claimId}/ai-analysis (see
 * services/officerService.js, backend app/services/ai_analysis.py) -
 * replacing the Step 5.5 static per-claim lookup. The "AI Demonstration
 * Examples" section below remains backed by the Step 5.4 static export
 * (src/services/aiRiskService.js) because it deliberately lets an
 * officer browse the 4 representative research examples by their
 * original dataset Claim_ID, independent of which real claim is
 * currently open - those example claims do not exist in the live
 * `claims` table, so the live endpoint cannot serve them. See
 * docs/project_documentation/AI_BACKEND_INTEGRATION.md.
 */
export default function AiInsightsPage() {
  const { claimId } = useParams();
  const { data, isLoading, error, reload } = useClaimWorkspace(claimId);
  const examples = useMemo(() => listDemonstrationExamples(), []);
  const [selectedExampleKey, setSelectedExampleKey] = useState("");

  const fetchAiAnalysis = useCallback(() => getAiAnalysis(claimId), [claimId]);
  const { data: analysis, isLoading: isAnalysisLoading, error: analysisError, reload: reloadAnalysis } = useFetch(
    fetchAiAnalysis,
    [fetchAiAnalysis]
  );

  if (isLoading) return <LoadingState label="Loading claim..." />;
  if (error) {
    return (
      <div>
        <PageHeader title="AI Risk Insights" />
        <BackButton fallback={`/officer/claims/${claimId}`} />
        <ClaimWorkspaceError error={error} onRetry={reload} />
      </div>
    );
  }

  const { claim } = data;
  const selectedExample = examples.find((example) => example.key === selectedExampleKey) ?? null;
  const exampleInsight = selectedExample ? getAiInsightsForClaim(selectedExample.claimId) : null;

  return (
    <div>
      <Breadcrumbs items={[{ label: "All Claims", to: "/officer/claims" }, { label: claim.Claim_Number, to: `/officer/claims/${claim.Claim_ID}` }, { label: "AI Insights" }]} />
      <PageHeader
        title={`AI Risk Insights — ${claim.Claim_Number}`}
        subtitle="Research-prototype decision support (Step 5.4/5.5), validated only on a synthetic/de-identified dataset. Not production fraud-detection accuracy."
      />
      <ClaimTabs claimId={claim.Claim_ID} />
      <BackButton fallback={`/officer/claims/${claim.Claim_ID}`} />

      <LiveRunPanel claimId={claim.Claim_ID} onAfterRun={reloadAnalysis} />

      {isAnalysisLoading ? (
        <LoadingState label="Loading AI analysis..." />
      ) : analysisError ? (
        <ClaimWorkspaceError error={analysisError} onRetry={reloadAnalysis} />
      ) : (
        <LiveAiAnalysisPanel analysis={analysis} />
      )}

      <Card className="mt-6">
        <h3 className="mb-1 text-sm font-semibold text-ink">AI Demonstration Examples</h3>
        <p className="mb-4 text-sm text-muted">
          Four real claims from the Step 5.4 dataset, one for each risk/confidence combination the research
          prototype actually found. A fifth category, "insufficient evidence", is intentionally not shown here
          because Step 5.4 found no claim in the current dataset that genuinely qualifies for it - every claim
          in this dataset has complete document and evidence records.
        </p>
        <label className="block max-w-sm">
          <span className="mb-1 block text-sm font-medium text-ink">Select an example</span>
          <select className="input" value={selectedExampleKey} onChange={(e) => setSelectedExampleKey(e.target.value)}>
            <option value="">Choose a demonstration example…</option>
            {examples.map((example) => (
              <option key={example.key} value={example.key}>
                {example.label} ({example.claimId})
              </option>
            ))}
          </select>
        </label>

        {exampleInsight && (
          <div className="mt-6 border-t border-border pt-6">
            <AIInsightCard insight={exampleInsight} demoLabel={selectedExample.label} />
          </div>
        )}
      </Card>
    </div>
  );
}
