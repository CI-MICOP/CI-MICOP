import { AlertTriangle, CheckCircle2, Info, Lock } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";

import BackButton from "../../components/common/BackButton";
import Breadcrumbs from "../../components/common/Breadcrumbs";
import Button from "../../components/common/Button";
import Card from "../../components/common/Card";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import StatusBadge from "../../components/common/StatusBadge";
import ClaimTabs from "../../components/officer/ClaimTabs";
import ClaimWorkspaceError from "../../components/officer/ClaimWorkspaceError";
import { useClaimWorkspace } from "../../hooks/useClaimWorkspace";
import { submitDecision } from "../../services/officerService";
import { formatCurrency, formatDate } from "../../utils/format";
import { getStatusTone } from "../../utils/statusTone";

// Real values from the approved dataset (see
// docs/project_documentation/CLAIMS_OFFICER_DECISION_WORKFLOW.md). Kept
// in sync with backend/app/schemas/officer.py's FINAL_DECISION_VALUES.
const FINAL_DECISION_OPTIONS = ["Approved", "Rejected", "Partially Approved"];

// Anything outside this set (e.g. the seed data's "Pending"/"Review"
// placeholders) is not a genuine AI recommendation - kept in sync with
// backend/app/services/claim_decision.py's REAL_AI_RECOMMENDATION_VALUES.
const REAL_AI_RECOMMENDATION_VALUES = new Set(["Approve", "Reject", "Investigate"]);

function emptyForm() {
  return { finalDecision: "", decisionReason: "", approvedAmount: "", officerComments: "" };
}

function getDecisionErrorMessage(error) {
  if (!error?.response) return "Unable to connect to the CI-MICOP server.";
  switch (error.response.status) {
    case 403:
      return "You don't have permission to record a decision for this claim.";
    case 404:
      return "This claim could not be found.";
    case 409:
      return error.response.data?.detail || "This claim's decision has already been finalized and cannot be changed.";
    case 422:
      return error.response.data?.detail || "That decision is not valid. Please check the fields and try again.";
    default:
      return "Something went wrong while saving the decision.";
  }
}

// "Pending" (schemas/surveyor.py) is the only non-final value - once the
// claim's own persisted Final_Decision is anything else, the decision is
// locked server-side too (services/claim_decision.py), so this page must
// never let the officer submit again.
function isFinalized(claim) {
  return Boolean(claim.Final_Decision) && claim.Final_Decision !== "Pending";
}

export default function DecisionPage() {
  const { claimId } = useParams();
  const { data, isLoading, error, reload } = useClaimWorkspace(claimId);
  const [form, setForm] = useState(emptyForm());
  const [saveState, setSaveState] = useState({ status: "idle", message: "" });

  if (isLoading) return <LoadingState label="Loading decision workspace..." />;
  if (error) {
    return (
      <div>
        <PageHeader title="Make Decision" />
        <BackButton fallback={`/officer/claims/${claimId}`} />
        <ClaimWorkspaceError error={error} onRetry={reload} />
      </div>
    );
  }

  const { claim, decision_audit: audits } = data;
  // decision_audit is returned newest-first, so audits[0] is the latest.
  const latestAudit = audits[0];
  const hasRealAiRecommendation = Boolean(latestAudit) && REAL_AI_RECOMMENDATION_VALUES.has(latestAudit.AI_Recommendation);
  // Derived fresh from the just-fetched claim on every load - never local
  // state - so the lock holds after a refresh, logout/login, or opening
  // the claim from another page, exactly like the backend's own check.
  const locked = isFinalized(claim);

  function update(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  function selectDecision(value) {
    setForm((prev) => ({
      ...prev,
      finalDecision: value,
      // A Rejected claim cannot have a positive approved amount - default
      // it to 0 for the officer rather than making them discover the
      // validation error after submitting.
      approvedAmount: value === "Rejected" ? "0" : prev.approvedAmount,
    }));
  }

  const reasonValid = form.decisionReason.trim().length > 0;
  const amountValid =
    form.approvedAmount !== "" &&
    !Number.isNaN(Number(form.approvedAmount)) &&
    Number(form.approvedAmount) >= 0 &&
    (form.finalDecision === "Rejected"
      ? Number(form.approvedAmount) === 0
      : form.finalDecision
        ? Number(form.approvedAmount) > 0
        : true);
  const formValid = Boolean(form.finalDecision) && reasonValid && amountValid;

  async function handleSubmit() {
    if (!formValid || saveState.status === "saving") return;
    setSaveState({ status: "saving", message: "" });
    try {
      await submitDecision(claimId, {
        finalDecision: form.finalDecision,
        decisionReason: form.decisionReason,
        approvedAmount: form.approvedAmount,
        officerComments: form.officerComments,
      });
      setSaveState({ status: "success", message: "Decision recorded successfully." });
      setForm(emptyForm());
      reload();
    } catch (err) {
      setSaveState({ status: "error", message: getDecisionErrorMessage(err) });
    }
  }

  return (
    <div>
      <Breadcrumbs items={[{ label: "All Claims", to: "/officer/claims" }, { label: claim.Claim_Number, to: `/officer/claims/${claim.Claim_ID}` }, { label: "Make Decision" }]} />
      <PageHeader title={`Make Decision — ${claim.Claim_Number}`} />
      <ClaimTabs claimId={claim.Claim_ID} />
      <BackButton fallback={`/officer/claims/${claim.Claim_ID}`} />

      <p className="mb-6 flex items-center gap-2 rounded-card border border-brand-200 bg-brand-50 p-3 text-sm text-brand-800">
        <Info className="h-4 w-4 shrink-0" aria-hidden="true" />
        AI provides decision support only. The final decision below is always the Claims Officer's own selection -
        it is never made automatically by the system.
      </p>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <h3 className="mb-4 text-sm font-semibold text-ink">Claim Summary</h3>
            <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Detail label="Claim ID" value={claim.Claim_ID} />
              <Detail label="Claim Type" value={claim.Claim_Type} />
              <Detail label="Claim Amount" value={formatCurrency(claim.Claim_Amount)} />
              <Detail label="Current Status"><StatusBadge label={claim.Claim_Status} tone={getStatusTone(claim.Claim_Status)} /></Detail>
              <Detail label="Current Final Decision" value={claim.Final_Decision || "Pending"} />
              <Detail label="Last Decision Date" value={claim.Decision_Date ? formatDate(claim.Decision_Date) : "-"} />
            </dl>
          </Card>

          <Card>
            <h3 className="mb-4 text-sm font-semibold text-ink">AI Recommendation (Supporting Information)</h3>
            {!hasRealAiRecommendation ? (
              <p className="text-sm text-muted">No AI recommendation is available for this claim.</p>
            ) : (
              <>
                <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <Detail label="AI Recommendation" value={latestAudit.AI_Recommendation} />
                  <Detail label="AI Confidence" value={latestAudit.AI_Confidence_Score} />
                  <Detail label="Escalation Status" value={latestAudit.Escalation_Status} />
                </dl>
                {latestAudit.Human_Review_Required && (
                  <div className="mt-4 flex items-start gap-2 rounded-card border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
                    <p>This claim was flagged for human review. This is a recommendation, not the final decision.</p>
                  </div>
                )}
              </>
            )}
          </Card>

          <Card>
            <h3 className="mb-4 text-sm font-semibold text-ink">Record a Decision</h3>
            {locked ? (
              <div className="space-y-4">
                <div className="flex items-center gap-2 rounded-card border border-border bg-surface p-3 text-sm text-ink">
                  <Lock className="h-4 w-4 shrink-0 text-muted" aria-hidden="true" />
                  Final decision recorded. This claim's decision is locked and cannot be edited.
                </div>
                <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <Detail label="Final Decision" value={latestAudit?.Final_Decision ?? claim.Final_Decision} />
                  <Detail
                    label="Approved Amount (INR)"
                    value={formatCurrency(latestAudit?.Approved_Amount ?? claim.Approved_Amount)}
                  />
                  <Detail label="Decision Reason" value={latestAudit?.Decision_Reason ?? claim.Decision_Reason} />
                  <Detail label="Officer Comments" value={latestAudit?.Officer_Comments || "-"} />
                </dl>
              </div>
            ) : (
              <div className="space-y-4">
                <label className="block">
                  <span className="mb-1 block text-sm font-medium text-ink">
                    Final Decision<span className="text-danger"> *</span>
                  </span>
                  <select className="input" value={form.finalDecision} onChange={(e) => selectDecision(e.target.value)}>
                    <option value="">Select a decision</option>
                    {FINAL_DECISION_OPTIONS.map((option) => (
                      <option key={option} value={option}>{option}</option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="mb-1 block text-sm font-medium text-ink">
                    Decision Reason<span className="text-danger"> *</span>
                  </span>
                  <textarea
                    className="input resize-none"
                    rows={3}
                    maxLength={2000}
                    value={form.decisionReason}
                    onChange={(e) => update("decisionReason", e.target.value)}
                  />
                  {!reasonValid && form.decisionReason.length > 0 && (
                    <p className="mt-1 text-xs text-danger">Decision reason cannot be empty.</p>
                  )}
                </label>
                <label className="block">
                  <span className="mb-1 block text-sm font-medium text-ink">
                    Approved Amount (INR)<span className="text-danger"> *</span>
                  </span>
                  <input
                    type="number"
                    min="0"
                    step="1"
                    className="input"
                    disabled={form.finalDecision === "Rejected"}
                    value={form.approvedAmount}
                    onChange={(e) => update("approvedAmount", e.target.value)}
                  />
                  {form.finalDecision === "Rejected" ? (
                    <p className="mt-1 text-xs text-muted">A rejected claim cannot have a positive approved amount.</p>
                  ) : form.finalDecision && (
                    <p className="mt-1 text-xs text-muted">
                      {form.finalDecision} requires a positive approved amount.
                    </p>
                  )}
                </label>
                <label className="block">
                  <span className="mb-1 block text-sm font-medium text-ink">Officer Comments</span>
                  <textarea
                    className="input resize-none"
                    rows={3}
                    maxLength={2000}
                    value={form.officerComments}
                    onChange={(e) => update("officerComments", e.target.value)}
                  />
                </label>

                {saveState.status === "error" && <p className="text-sm text-danger">{saveState.message}</p>}

                <div className="flex justify-end border-t border-border pt-4">
                  <Button onClick={handleSubmit} isLoading={saveState.status === "saving"} disabled={!formValid}>
                    Submit Decision
                  </Button>
                </div>
              </div>
            )}
          </Card>

          {saveState.status === "success" && (
            <div className="flex items-center gap-2 rounded-card border border-green-200 bg-green-50 p-3 text-sm text-success">
              <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
              {saveState.message}
            </div>
          )}
        </div>

        <div className="space-y-6">
          <Card>
            <h3 className="mb-3 text-sm font-semibold text-ink">Escalation Status</h3>
            <p className="text-sm text-ink">{latestAudit?.Escalation_Status ?? "No escalation on file"}</p>
          </Card>

          <Card>
            <h3 className="mb-3 text-sm font-semibold text-ink">Decision History</h3>
            {audits.length === 0 ? (
              <p className="text-sm text-muted">No prior decisions recorded for this claim.</p>
            ) : (
              <ul className="space-y-3 text-sm">
                {audits.map((audit) => (
                  <li key={audit.Audit_ID} className="border-b border-border pb-2 last:border-0 last:pb-0">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-ink">{audit.Final_Decision}</span>
                      <span className="text-xs text-muted">{formatDate(audit.Decision_Date)}</span>
                    </div>
                    <p className="mt-0.5 text-xs text-muted">{formatCurrency(audit.Approved_Amount)}</p>
                  </li>
                ))}
              </ul>
            )}
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
