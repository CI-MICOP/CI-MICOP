import { CheckCircle2 } from "lucide-react";
import { useCallback, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import Breadcrumbs from "../../components/common/Breadcrumbs";
import Button from "../../components/common/Button";
import Card from "../../components/common/Card";
import ErrorState from "../../components/common/ErrorState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import StatusBadge from "../../components/common/StatusBadge";
import ClaimStepNav from "../../components/surveyor/ClaimStepNav";
import ClaimTabs from "../../components/surveyor/ClaimTabs";
import SurveyReportActions from "../../components/surveyor/SurveyReportActions";
import SurveyReportContent from "../../components/surveyor/SurveyReportContent";
import { useSurveyorClaim } from "../../components/surveyor/useSurveyorClaim";
import { StepLockNotice } from "../../components/surveyor/WorkflowNotices";
import { SUBMIT_CONFIRM_PROMPT, serverMessage, surveyReportErrorMessage } from "../../components/surveyor/workflowProgress";
import { useFetch } from "../../hooks/useFetch";
import { getSurveyReport, updateInspection } from "../../services/surveyorService";
import { getApiErrorMessage } from "../../utils/errors";

export default function SurveyReportPage() {
  const { claimId } = useParams();
  const [saveState, setSaveState] = useState({ status: "idle", message: "" });
  const submittingRef = useRef(false);

  const { data, isLoading, error, reload, progress } = useSurveyorClaim(claimId);

  // The review is the backend's report - the same data View Report and the
  // PDF use. It is only requested once the server says it is available;
  // the backend checks completeness again itself.
  const reportAvailable = Boolean(progress?.reportAvailable);
  const submitted = Boolean(progress?.submitted);
  const fetchReport = useCallback(
    () => (reportAvailable ? getSurveyReport(claimId) : Promise.resolve(null)),
    [claimId, reportAvailable]
  );
  // `submitted` also re-fetches it, so the review shows "Submitted" afterwards.
  const report = useFetch(fetchReport, [fetchReport, submitted]);

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
  const { inspection } = progress;

  async function handleSubmitReport() {
    if (submittingRef.current) return;
    if (!window.confirm(SUBMIT_CONFIRM_PROMPT)) return;
    submittingRef.current = true;
    setSaveState({ status: "saving", message: "" });
    try {
      await updateInspection(inspection.Inspection_ID, { Survey_Report_Submitted: true });
      setSaveState({ status: "success", message: "Final survey report submitted." });
      reload();
    } catch (err) {
      // The backend explains what is still missing (for example a damage
      // record or a camera-captured photo).
      setSaveState({ status: "error", message: serverMessage(err, getApiErrorMessage(err)) });
    } finally {
      submittingRef.current = false;
    }
  }

  return (
    <div>
      <Breadcrumbs
        items={[
          { label: "Assigned Inspections", to: "/surveyor/claims" },
          { label: claim.Claim_Number, to: `/surveyor/claims/${claim.Claim_ID}` },
          { label: "Survey Report" },
        ]}
      />
      <PageHeader title={`Survey Report — ${claim.Claim_Number}`} />
      <ClaimTabs claimId={claim.Claim_ID} progress={progress} />

      {!progress.unlocked.has("report") || !progress.reportAvailable ? (
        <StepLockNotice progress={progress} claimId={claim.Claim_ID} />
      ) : (
        <div className="space-y-6">
          <Card>
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h3 className="mb-2 text-sm font-semibold text-ink">Report Status</h3>
                <StatusBadge label={submitted ? "Submitted" : "Draft"} tone={submitted ? "success" : "warning"} />
                <p className="mt-2 text-sm text-muted">
                  {submitted
                    ? "This survey report has been submitted and can no longer be changed."
                    : "Review the report below. To fix a mistake, go back to the step and use “Correct this step”. Viewing or downloading does not submit the report."}
                </p>
              </div>
              <div className="flex flex-col items-start gap-3 sm:items-end">
                <SurveyReportActions claimId={claim.Claim_ID} claimNumber={claim.Claim_Number} />
                {!submitted && (
                  <Button onClick={handleSubmitReport} isLoading={saveState.status === "saving"}>
                    Submit Final Survey Report
                  </Button>
                )}
              </div>
            </div>

            {saveState.status === "success" && (
              <div className="mt-4 flex flex-wrap items-center gap-2 rounded-card border border-green-200 bg-green-50 p-3 text-sm text-success">
                <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                {saveState.message} It has moved to
                <Link to="/surveyor/history" className="font-medium text-brand-700 underline">
                  Survey Reports
                </Link>
              </div>
            )}
            {saveState.status === "error" && (
              <p role="alert" className="mt-4 text-sm text-danger">
                {saveState.message}
              </p>
            )}
          </Card>

          {report.isLoading ? (
            <LoadingState label="Loading report..." />
          ) : report.data ? (
            <SurveyReportContent report={report.data} />
          ) : (
            <ErrorState message={surveyReportErrorMessage(report.error)} onRetry={report.reload} />
          )}
        </div>
      )}
      <ClaimStepNav claimId={claim.Claim_ID} current="report" />
    </div>
  );
}
