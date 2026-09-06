import { Sparkles } from "lucide-react";
import { useParams } from "react-router-dom";

import Breadcrumbs from "../../components/common/Breadcrumbs";
import Card from "../../components/common/Card";
import EmptyState from "../../components/common/EmptyState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import ClaimTabs from "../../components/officer/ClaimTabs";
import ClaimWorkspaceError from "../../components/officer/ClaimWorkspaceError";
import { useClaimWorkspace } from "../../hooks/useClaimWorkspace";

const SECTIONS = [
  { title: "Overall Risk", message: "Risk score and model confidence will appear here once an AI model is connected." },
  { title: "Why the Model Gave This Result", message: "Top contributing factors will be listed here once explainability output is available." },
  { title: "Evidence", message: "Documents and events supporting each factor will be shown here." },
  { title: "Explanation", message: "A human-readable explanation of the AI's reasoning will appear here." },
  { title: "Recommended Action", message: "The AI's recommended action will be shown here for officer review." },
];

/**
 * Explainable-AI interface placeholder. No AI/ML service exists yet
 * (see Step 4.5 report) - every section is an honest "not connected"
 * state rather than fabricated SHAP values, confidence, or recommendations.
 */
export default function AiInsightsPage() {
  const { claimId } = useParams();
  const { data, isLoading, error, reload } = useClaimWorkspace(claimId);

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

  return (
    <div>
      <Breadcrumbs items={[{ label: "All Claims", to: "/officer/claims" }, { label: claim.Claim_Number, to: `/officer/claims/${claim.Claim_ID}` }, { label: "AI Insights" }]} />
      <PageHeader title={`AI Risk Insights — ${claim.Claim_Number}`} subtitle="Explainable AI is not connected yet. This is the reserved interface for a future model." />
      <ClaimTabs claimId={claim.Claim_ID} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {SECTIONS.map((section) => (
          <Card key={section.title}>
            <h3 className="mb-3 text-sm font-semibold text-ink">{section.title}</h3>
            <EmptyState icon={Sparkles} title="AI analysis not connected yet" message={section.message} />
          </Card>
        ))}
        <Card className="lg:col-span-2">
          <h3 className="mb-3 text-sm font-semibold text-ink">Human Review</h3>
          <p className="text-sm text-muted">
            When AI insights are available, this section will let the officer confirm or override the AI's
            suggestion. Until then, all decisions are made entirely by the Claims Officer on the Make
            Decision tab.
          </p>
        </Card>
      </div>
    </div>
  );
}
