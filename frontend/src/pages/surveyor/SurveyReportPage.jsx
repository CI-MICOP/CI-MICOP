import { CheckCircle2 } from "lucide-react";
import { useCallback, useState } from "react";
import { useParams } from "react-router-dom";

import Breadcrumbs from "../../components/common/Breadcrumbs";
import Button from "../../components/common/Button";
import Card from "../../components/common/Card";
import EmptyState from "../../components/common/EmptyState";
import ErrorState from "../../components/common/ErrorState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import StatusBadge from "../../components/common/StatusBadge";
import ClaimTabs from "../../components/surveyor/ClaimTabs";
import { useAuth } from "../../hooks/useAuth";
import { useFetch } from "../../hooks/useFetch";
import { getClaimById } from "../../services/claimService";
import { getAssignedClaimDetail, updateInspection } from "../../services/surveyorService";
import { getApiErrorMessage } from "../../utils/errors";

export default function SurveyReportPage() {
  const { claimId } = useParams();
  const { user } = useAuth();
  const [saveState, setSaveState] = useState({ status: "idle", message: "" });

  const fetchDetail = useCallback(async () => {
    const [claim, assigned] = await Promise.all([getClaimById(claimId), getAssignedClaimDetail(claimId)]);
    return { claim, ...assigned };
  }, [claimId]);

  const { data, isLoading, error, reload } = useFetch(fetchDetail, [fetchDetail]);
  const inspection = data?.inspections.find((i) => i.Surveyor_ID === user?.Employee_ID) ?? data?.inspections[0];

  async function handleSubmitReport() {
    setSaveState({ status: "saving", message: "" });
    try {
      await updateInspection(inspection.Inspection_ID, { Survey_Report_Submitted: true });
      setSaveState({ status: "success", message: "Survey report marked as submitted." });
      reload();
    } catch (err) {
      setSaveState({ status: "error", message: getApiErrorMessage(err) });
    }
  }

  if (isLoading) return <LoadingState label="Loading survey report..." />;
  if (error) {
    return (
      <div>
        <PageHeader title="Survey Report" />
        <ErrorState message={getApiErrorMessage(error)} onRetry={reload} />
      </div>
    );
  }

  const { claim } = data;

  return (
    <div>
      <Breadcrumbs
        items={[
          { label: "Assigned Claims", to: "/surveyor/claims" },
          { label: claim.Claim_Number, to: `/surveyor/claims/${claim.Claim_ID}` },
          { label: "Survey Report" },
        ]}
      />
      <PageHeader title={`Survey Report — ${claim.Claim_Number}`} />
      <ClaimTabs claimId={claim.Claim_ID} />

      {!inspection ? (
        <EmptyState title="No inspection record exists for this claim" />
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <Card>
              <h3 className="mb-4 text-sm font-semibold text-ink">Inspection Findings</h3>
              <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Detail label="Vehicle Condition" value={inspection.Vehicle_Condition} />
                <Detail label="Damage Observed" value={inspection.Damage_Observed} />
                <Detail label="Damage Severity" value={inspection.Damage_Severity} />
                <Detail label="Parts Required" value={inspection.Parts_Required} />
                <Detail label="Repair Recommendation" value={inspection.Repair_Recommendation} />
                <Detail label="Inspection Status" value={inspection.Inspection_Status} />
              </dl>
            </Card>

            <Card>
              <h3 className="mb-3 text-sm font-semibold text-ink">Surveyor Comments</h3>
              <p className="text-sm text-ink">{inspection.Surveyor_Comments || "No comments recorded."}</p>
              <p className="mt-3 text-xs text-muted">
                To change any of these findings, use the Inspection tab - this page only manages the
                report-submitted status.
              </p>
            </Card>
          </div>

          <div className="space-y-6">
            <Card>
              <h3 className="mb-3 text-sm font-semibold text-ink">Report Status</h3>
              <StatusBadge
                label={inspection.Survey_Report_Submitted ? "Submitted" : "Not Submitted"}
                tone={inspection.Survey_Report_Submitted ? "success" : "warning"}
              />

              {saveState.status === "success" && (
                <div className="mt-4 flex items-center gap-2 rounded-card border border-green-200 bg-green-50 p-3 text-sm text-success">
                  <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                  {saveState.message}
                </div>
              )}
              {saveState.status === "error" && <p className="mt-4 text-sm text-danger">{saveState.message}</p>}

              {!inspection.Survey_Report_Submitted && (
                <Button className="mt-4 w-full" onClick={handleSubmitReport} isLoading={saveState.status === "saving"}>
                  Submit Survey Report
                </Button>
              )}
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
