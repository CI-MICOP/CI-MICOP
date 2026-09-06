import { Info } from "lucide-react";
import { useState } from "react";

import Card from "../../components/common/Card";
import EmptyState from "../../components/common/EmptyState";
import ErrorState from "../../components/common/ErrorState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import { useFetch } from "../../hooks/useFetch";
import { getClaimProcessingDetail, listClaimsForProcessing } from "../../services/officerService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatDate } from "../../utils/format";

export default function AuditLogsPage() {
  const [claimId, setClaimId] = useState("");
  const { data: claims, isLoading: claimsLoading, error: claimsError, reload: reloadClaims } = useFetch(
    () => listClaimsForProcessing({ limit: 200 }),
    []
  );
  const {
    data: detail,
    isLoading: detailLoading,
    error: detailError,
  } = useFetch(() => (claimId ? getClaimProcessingDetail(claimId) : Promise.resolve(null)), [claimId]);

  return (
    <div>
      <PageHeader title="Audit Logs" subtitle="Decision audit trail for a selected claim." />

      <p className="mb-6 flex items-start gap-2 rounded-card border border-surface bg-surface p-3 text-xs text-muted">
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        There is no bulk endpoint listing audit records across all claims, so select a claim below to view
        its audit trail. Note: the database has an internal Audit_Timestamp column that is not exposed by
        the API - Decision Date is shown instead as the closest available real timestamp.
      </p>

      {claimsError ? (
        <ErrorState message={getApiErrorMessage(claimsError)} onRetry={reloadClaims} />
      ) : (
        <Card className="mb-6">
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-ink">Claim</span>
            <select className="input sm:max-w-md" value={claimId} onChange={(e) => setClaimId(e.target.value)} disabled={claimsLoading}>
              <option value="">Select a claim</option>
              {(claims ?? []).map((c) => (
                <option key={c.Claim_ID} value={c.Claim_ID}>
                  {c.Claim_Number}
                </option>
              ))}
            </select>
          </label>
        </Card>
      )}

      {claimId && (
        <Card>
          {detailLoading || !detail ? (
            <LoadingState label="Loading audit trail..." />
          ) : detailError ? (
            <ErrorState message={getApiErrorMessage(detailError)} />
          ) : detail.decision_audit.length === 0 ? (
            <EmptyState title="No audit records for this claim" />
          ) : (
            <div className="space-y-4">
              {detail.decision_audit.map((audit) => (
                <div key={audit.Audit_ID} className="rounded-card border border-border p-4">
                  <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    <Row label="Officer (Employee ID)" value={audit.Claims_Officer_ID} />
                    <Row label="AI Recommendation" value={audit.AI_Recommendation} />
                    <Row label="AI Confidence" value={audit.AI_Confidence_Score} />
                    <Row label="Human Review Required" value={audit.Human_Review_Required ? "Yes" : "No"} />
                    <Row label="Final Decision" value={audit.Final_Decision} />
                    <Row label="Approved Amount" value={audit.Approved_Amount} />
                    <Row label="Decision Date" value={formatDate(audit.Decision_Date)} />
                    <Row label="Escalation Status" value={audit.Escalation_Status} />
                    <Row label="Audit Action" value={audit.Audit_Action} />
                  </dl>
                  <div className="mt-3">
                    <p className="text-xs font-medium uppercase tracking-wide text-muted">Decision Reason</p>
                    <p className="text-sm text-ink">{audit.Decision_Reason || "-"}</p>
                  </div>
                  <div className="mt-2">
                    <p className="text-xs font-medium uppercase tracking-wide text-muted">Officer Comments</p>
                    <p className="text-sm text-ink">{audit.Officer_Comments || "-"}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-muted">{label}</dt>
      <dd className="text-sm text-ink">{value ?? "-"}</dd>
    </div>
  );
}
