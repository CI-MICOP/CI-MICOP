import { AlertTriangle, Info } from "lucide-react";
import { useParams } from "react-router-dom";
import { useState } from "react";

import Breadcrumbs from "../../components/common/Breadcrumbs";
import Button from "../../components/common/Button";
import Card from "../../components/common/Card";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import StatusBadge from "../../components/common/StatusBadge";
import ClaimTabs from "../../components/officer/ClaimTabs";
import { formatCurrency } from "../../utils/format";
import { getStatusTone } from "../../utils/statusTone";
import ClaimWorkspaceError from "../../components/officer/ClaimWorkspaceError";
import { useClaimWorkspace } from "../../hooks/useClaimWorkspace";

export default function DecisionPage() {
  const { claimId } = useParams();
  const { data, isLoading, error, reload } = useClaimWorkspace(claimId);
  const [form, setForm] = useState({ finalDecision: "", decisionReason: "", approvedAmount: "", officerComments: "" });
  const [submitAttempted, setSubmitAttempted] = useState(false);

  if (isLoading) return <LoadingState label="Loading decision workspace..." />;
  if (error) {
    return (
      <div>
        <PageHeader title="Make Decision" />
        <ClaimWorkspaceError error={error} onRetry={reload} />
      </div>
    );
  }

  const { claim, decision_audit: audits } = data;
  const latestAudit = audits[0];

  function update(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  return (
    <div>
      <Breadcrumbs items={[{ label: "All Claims", to: "/officer/claims" }, { label: claim.Claim_Number, to: `/officer/claims/${claim.Claim_ID}` }, { label: "Make Decision" }]} />
      <PageHeader title={`Make Decision — ${claim.Claim_Number}`} />
      <ClaimTabs claimId={claim.Claim_ID} />

      <p className="mb-6 flex items-center gap-2 rounded-card border border-brand-200 bg-brand-50 p-3 text-sm text-brand-800">
        <Info className="h-4 w-4 shrink-0" aria-hidden="true" />
        AI provides decision support. Final decision remains with the Claims Officer.
      </p>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <h3 className="mb-4 text-sm font-semibold text-ink">Claim Summary</h3>
            <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Detail label="Claim Type" value={claim.Claim_Type} />
              <Detail label="Claim Amount" value={formatCurrency(claim.Claim_Amount)} />
              <Detail label="Current Status"><StatusBadge label={claim.Claim_Status} tone={getStatusTone(claim.Claim_Status)} /></Detail>
              <Detail label="Current Final Decision" value={claim.Final_Decision || "Pending"} />
            </dl>
          </Card>

          <Card>
            <h3 className="mb-4 text-sm font-semibold text-ink">AI Recommendation</h3>
            {!latestAudit ? (
              <p className="text-sm text-muted">No AI recommendation is available for this claim yet.</p>
            ) : (
              <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Detail label="AI Recommendation" value={latestAudit.AI_Recommendation} />
                <Detail label="AI Confidence" value={latestAudit.AI_Confidence_Score} />
                <Detail label="Human Review Required" value={latestAudit.Human_Review_Required ? "Yes" : "No"} />
                <Detail label="Escalation Status" value={latestAudit.Escalation_Status} />
              </dl>
            )}
          </Card>

          <Card>
            <h3 className="mb-4 text-sm font-semibold text-ink">Record a Decision</h3>
            <div className="space-y-4">
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-ink">Final Decision</span>
                <select className="input" value={form.finalDecision} onChange={(e) => update("finalDecision", e.target.value)}>
                  <option value="">Select a decision</option>
                  <option value="Approved">Approved</option>
                  <option value="Rejected">Rejected</option>
                  <option value="Partially Approved">Partially Approved</option>
                </select>
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-ink">Decision Reason</span>
                <textarea className="input resize-none" rows={3} value={form.decisionReason} onChange={(e) => update("decisionReason", e.target.value)} />
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-ink">Approved Amount</span>
                <input type="number" min="0" className="input" value={form.approvedAmount} onChange={(e) => update("approvedAmount", e.target.value)} />
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-ink">Officer Comments</span>
                <textarea className="input resize-none" rows={3} value={form.officerComments} onChange={(e) => update("officerComments", e.target.value)} />
              </label>

              {submitAttempted && (
                <div className="flex gap-3 rounded-card border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                  <AlertTriangle className="h-5 w-5 shrink-0 text-warning" aria-hidden="true" />
                  <div>
                    <p className="font-medium">Decision submission is not yet connected to the backend</p>
                    <p className="mt-1 text-amber-800">
                      The CI-MICOP API does not currently expose a write endpoint for recording an officer
                      decision. Nothing entered above has been saved.
                    </p>
                  </div>
                </div>
              )}

              <div className="flex justify-end border-t border-border pt-4">
                <Button onClick={() => setSubmitAttempted(true)}>Submit Decision</Button>
              </div>
            </div>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <h3 className="mb-3 text-sm font-semibold text-ink">Escalation Status</h3>
            <p className="text-sm text-ink">{latestAudit?.Escalation_Status ?? "No escalation on file"}</p>
          </Card>
        </div>
      </div>
    </div>
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
