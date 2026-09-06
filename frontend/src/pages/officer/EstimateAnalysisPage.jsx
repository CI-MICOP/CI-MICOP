import { Calculator } from "lucide-react";
import { useParams } from "react-router-dom";

import Breadcrumbs from "../../components/common/Breadcrumbs";
import Card from "../../components/common/Card";
import EmptyState from "../../components/common/EmptyState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import StatusBadge from "../../components/common/StatusBadge";
import ClaimTabs from "../../components/officer/ClaimTabs";
import { formatCurrency, formatDate } from "../../utils/format";
import ClaimWorkspaceError from "../../components/officer/ClaimWorkspaceError";
import { useClaimWorkspace } from "../../hooks/useClaimWorkspace";

export default function EstimateAnalysisPage() {
  const { claimId } = useParams();
  const { data, isLoading, error, reload } = useClaimWorkspace(claimId);

  if (isLoading) return <LoadingState label="Loading estimate analysis..." />;
  if (error) {
    return (
      <div>
        <PageHeader title="Estimate Analysis" />
        <ClaimWorkspaceError error={error} onRetry={reload} />
      </div>
    );
  }

  const { claim, repair_estimates: estimates } = data;
  const estimate = estimates[0];

  return (
    <div>
      <Breadcrumbs items={[{ label: "All Claims", to: "/officer/claims" }, { label: claim.Claim_Number, to: `/officer/claims/${claim.Claim_ID}` }, { label: "Estimate Analysis" }]} />
      <PageHeader title={`Estimate Analysis — ${claim.Claim_Number}`} subtitle="Future integration point for the Smart Repair Estimate / Claim Leakage model." />
      <ClaimTabs claimId={claim.Claim_ID} />

      {!estimate ? (
        <Card>
          <EmptyState icon={Calculator} title="No repair estimate on file for this claim" />
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <Card>
              <h3 className="mb-4 text-sm font-semibold text-ink">Cost Breakdown</h3>
              <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Detail label="Repair Estimate" value={formatCurrency(estimate.Repair_Estimate)} />
                <Detail label="Repair Cost" value={formatCurrency(estimate.Repair_Cost)} />
                <Detail label="Parts Cost" value={formatCurrency(estimate.Parts_Cost)} />
                <Detail label="Labour Cost" value={formatCurrency(estimate.Labour_Cost)} />
                <Detail label="Painting Cost" value={formatCurrency(estimate.Painting_Cost)} />
                <Detail label="Estimate Date" value={formatDate(estimate.Estimate_Date)} />
              </dl>
            </Card>
            <Card>
              <h3 className="mb-4 text-sm font-semibold text-ink">Parts & Timeline</h3>
              <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Detail label="Replacement Parts Count" value={estimate.Replacement_Parts_Count} />
                <Detail label="Repaired Parts Count" value={estimate.Repaired_Parts_Count} />
                <Detail label="Estimated Repair Days" value={estimate.Estimated_Repair_Days} />
                <Detail label="Actual Repair Days" value={estimate.Actual_Repair_Days} />
              </dl>
            </Card>
          </div>
          <div className="space-y-6">
            <Card>
              <h3 className="mb-3 text-sm font-semibold text-ink">Excessive Claim Amount</h3>
              <StatusBadge label={estimate.Excessive_Claim_Amount_Indicator ? "Flagged" : "Not Flagged"} tone={estimate.Excessive_Claim_Amount_Indicator ? "danger" : "success"} />
            </Card>
            <Card>
              <h3 className="mb-3 text-sm font-semibold text-ink">Estimate Anomaly Score</h3>
              <p className="text-lg font-medium text-ink">{estimate.Estimate_Anomaly_Score}</p>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}

function Detail({ label, value }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-muted">{label}</dt>
      <dd className="mt-0.5 text-sm text-ink">{value}</dd>
    </div>
  );
}
