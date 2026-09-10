import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import Breadcrumbs from "../../components/common/Breadcrumbs";
import Card from "../../components/common/Card";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import AIInsightCard from "../../components/officer/ai/AIInsightCard";
import ClaimTabs from "../../components/officer/ClaimTabs";
import ClaimWorkspaceError from "../../components/officer/ClaimWorkspaceError";
import { useClaimWorkspace } from "../../hooks/useClaimWorkspace";
import { getAiInsightsForClaim, listDemonstrationExamples } from "../../services/aiRiskService";

/**
 * Step 5.5: read-only "AI Risk Insights" surface, wired to the Step 5.4
 * risk-fusion research prototype (ai_ml/risk_fusion, ai_ml/experiments/
 * run_risk_fusion_experiment.py) via a static, bundled export of its
 * ACTUAL output - see src/services/aiRiskService.js. No backend AI
 * endpoint exists or was added for this step; nothing on this page is
 * connected to any decision action. See
 * docs/project_documentation/AI_OFFICER_INTEGRATION.md.
 */
export default function AiInsightsPage() {
  const { claimId } = useParams();
  const { data, isLoading, error, reload } = useClaimWorkspace(claimId);
  const examples = useMemo(() => listDemonstrationExamples(), []);
  const [selectedExampleKey, setSelectedExampleKey] = useState("");

  if (isLoading) return <LoadingState label="Loading claim..." />;
  if (error) {
    return (
      <div>
        <PageHeader title="AI Risk Insights" />
        <ClaimWorkspaceError error={error} onRetry={reload} />
      </div>
    );
  }

  const { claim } = data;
  const insight = getAiInsightsForClaim(claim.Claim_ID);
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

      <AIInsightCard insight={insight} />

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
