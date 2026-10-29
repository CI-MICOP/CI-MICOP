import { ShieldAlert } from "lucide-react";
import { useParams } from "react-router-dom";

import BackButton from "../../components/common/BackButton";
import Breadcrumbs from "../../components/common/Breadcrumbs";
import Card from "../../components/common/Card";
import EmptyState from "../../components/common/EmptyState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import StatusBadge from "../../components/common/StatusBadge";
import ClaimTabs from "../../components/officer/ClaimTabs";
import { getStatusTone } from "../../utils/statusTone";
import ClaimWorkspaceError from "../../components/officer/ClaimWorkspaceError";
import { useClaimWorkspace } from "../../hooks/useClaimWorkspace";

const INDICATORS = [
  ["Duplicate_Claim_Indicator", "Duplicate Claim"],
  ["Previous_Similar_Claim", "Similar Previous Claim"],
  ["Suspicious_Garage_Indicator", "Suspicious Garage"],
  ["Claim_Immediately_After_Policy_Indicator", "Immediate Post-Policy Claim"],
  ["Excessive_Claim_Amount_Indicator", "Excessive Claim Amount"],
  ["Document_Mismatch_Indicator", "Document Mismatch"],
  ["Vehicle_Damage_Mismatch_Indicator", "Vehicle Damage Mismatch"],
  ["Accident_Details_Mismatch_Indicator", "Accident Details Mismatch"],
  ["Evidence_Reuse_Indicator", "Evidence Reuse"],
];

export default function FraudRiskPage() {
  const { claimId } = useParams();
  const { data, isLoading, error, reload } = useClaimWorkspace(claimId);

  if (isLoading) return <LoadingState label="Loading fraud risk analysis..." />;
  if (error) {
    return (
      <div>
        <PageHeader title="Fraud Risk" />
        <BackButton fallback={`/officer/claims/${claimId}`} />
        <ClaimWorkspaceError error={error} onRetry={reload} />
      </div>
    );
  }

  const { claim, fraud_risk_analysis: fraud } = data;
  const risk = fraud[0];

  return (
    <div>
      <Breadcrumbs items={[{ label: "All Claims", to: "/officer/claims" }, { label: claim.Claim_Number, to: `/officer/claims/${claim.Claim_ID}` }, { label: "Fraud Risk" }]} />
      <PageHeader title={`Fraud Risk — ${claim.Claim_Number}`} subtitle="Future AI integration point - only real backend values are shown." />
      <ClaimTabs claimId={claim.Claim_ID} />
      <BackButton fallback={`/officer/claims/${claim.Claim_ID}`} />

      {!risk ? (
        <Card>
          <EmptyState icon={ShieldAlert} title="AI fraud analysis will appear here when the AI service is connected." />
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <Card>
              <h3 className="mb-4 text-sm font-semibold text-ink">Fraud Indicators</h3>
              <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {INDICATORS.map(([field, label]) => (
                  <li key={field} className="flex items-center justify-between rounded-card border border-border p-3 text-sm">
                    <span className="text-ink">{label}</span>
                    <StatusBadge label={risk[field] ? "Yes" : "No"} tone={risk[field] ? "danger" : "success"} />
                  </li>
                ))}
              </ul>
            </Card>
          </div>

          <div className="space-y-6">
            <Card>
              <h3 className="mb-3 text-sm font-semibold text-ink">Overall Risk Score</h3>
              <p className="text-2xl font-semibold text-ink">{risk.Overall_Risk_Score}</p>
              <div className="mt-2">
                <StatusBadge label={risk.Risk_Category} tone={getStatusTone(risk.Risk_Category)} />
              </div>
            </Card>
            <Card>
              <h3 className="mb-3 text-sm font-semibold text-ink">Fraud Risk Score</h3>
              <p className="text-lg font-medium text-ink">{risk.Fraud_Risk_Score}</p>
            </Card>
            <Card>
              <h3 className="mb-3 text-sm font-semibold text-ink">Anomaly Score</h3>
              <p className="text-lg font-medium text-ink">{risk.Anomaly_Score}</p>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
