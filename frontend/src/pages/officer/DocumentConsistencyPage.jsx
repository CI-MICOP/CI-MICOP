import { FileCheck2 } from "lucide-react";
import { useParams } from "react-router-dom";

import BackButton from "../../components/common/BackButton";
import Breadcrumbs from "../../components/common/Breadcrumbs";
import Card from "../../components/common/Card";
import EmptyState from "../../components/common/EmptyState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import StatusBadge from "../../components/common/StatusBadge";
import ClaimTabs from "../../components/officer/ClaimTabs";
import ConsistencyFindingsPanel from "../../components/officer/ConsistencyFindingsPanel";
import { getStatusTone } from "../../utils/statusTone";
import ClaimWorkspaceError from "../../components/officer/ClaimWorkspaceError";
import { useClaimWorkspace } from "../../hooks/useClaimWorkspace";

const MATCH_FIELDS = [
  ["Customer_Statement_Match", "Customer Statement Match"],
  ["FIR_Match", "FIR Match"],
  ["Surveyor_Report_Match", "Surveyor Report Match"],
  ["Repair_Estimate_Match", "Repair Estimate Match"],
  ["Accident_Date_Match", "Accident Date Match"],
  ["Accident_Location_Match", "Accident Location Match"],
  ["Vehicle_Details_Match", "Vehicle Details Match"],
  ["Damage_Description_Match", "Damage Description Match"],
  ["Claim_Amount_Match", "Claim Amount Match"],
];

export default function DocumentConsistencyPage() {
  const { claimId } = useParams();
  const { data, isLoading, error, reload } = useClaimWorkspace(claimId);

  if (isLoading) return <LoadingState label="Loading document consistency data..." />;
  if (error) {
    return (
      <div>
        <PageHeader title="Document Consistency" />
        <BackButton fallback={`/officer/claims/${claimId}`} />
        <ClaimWorkspaceError error={error} onRetry={reload} />
      </div>
    );
  }

  const { claim, cross_document_consistency: consistencyRows } = data;
  const consistency = consistencyRows[0];

  return (
    <div>
      <Breadcrumbs items={[{ label: "All Claims", to: "/officer/claims" }, { label: claim.Claim_Number, to: `/officer/claims/${claim.Claim_ID}` }, { label: "Document Consistency" }]} />
      <PageHeader title={`Document Consistency — ${claim.Claim_Number}`} />
      <ClaimTabs claimId={claim.Claim_ID} />
      <BackButton fallback={`/officer/claims/${claim.Claim_ID}`} />

      <ConsistencyFindingsPanel claimId={claim.Claim_ID} />

      {/* The cross_document_consistency row below comes from the seeded
          synthetic dataset - it is NOT computed from this claim's uploaded
          documents (see SEMANTIC_DOCUMENT_CONSISTENCY.md, Section 18). */}
      <div className="mb-4">
        <h2 className="text-sm font-semibold text-ink">Recorded Dataset Values</h2>
        <p className="mt-1 text-sm text-muted">
          Stored consistency record from the synthetic research dataset - not computed from this claim's uploaded
          documents.
        </p>
      </div>

      {!consistency ? (
        <Card>
          <EmptyState icon={FileCheck2} title="No recorded consistency data for this claim" />
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <Card>
              <h3 className="mb-4 text-sm font-semibold text-ink">Field-Level Matches</h3>
              <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {MATCH_FIELDS.map(([field, label]) => (
                  <li key={field} className="flex items-center justify-between rounded-card border border-border p-3 text-sm">
                    <span className="text-ink">{label}</span>
                    <StatusBadge label={consistency[field]} tone={getStatusTone(consistency[field])} />
                  </li>
                ))}
              </ul>
            </Card>
          </div>
          <div className="space-y-6">
            <Card>
              <h3 className="mb-3 text-sm font-semibold text-ink">Overall Consistency Status</h3>
              <StatusBadge label={consistency.Overall_Consistency_Status} tone={getStatusTone(consistency.Overall_Consistency_Status)} />
            </Card>
            <Card>
              <h3 className="mb-3 text-sm font-semibold text-ink">Consistency Score</h3>
              <p className="text-lg font-medium text-ink">{consistency.Document_Consistency_Score}</p>
            </Card>
            <Card>
              <h3 className="mb-3 text-sm font-semibold text-ink">Mismatch Indicators</h3>
              <ul className="space-y-2 text-sm">
                <li className="flex justify-between"><span className="text-muted">Document Mismatch</span><span className="text-ink">{consistency.Document_Mismatch_Indicator ? "Yes" : "No"}</span></li>
                <li className="flex justify-between"><span className="text-muted">Accident Details Mismatch</span><span className="text-ink">{consistency.Accident_Details_Mismatch_Indicator ? "Yes" : "No"}</span></li>
                <li className="flex justify-between"><span className="text-muted">Vehicle Damage Mismatch</span><span className="text-ink">{consistency.Vehicle_Damage_Mismatch_Indicator ? "Yes" : "No"}</span></li>
              </ul>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
