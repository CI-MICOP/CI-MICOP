import { ArrowLeft, Printer } from "lucide-react";
import { useCallback } from "react";
import { Link, useParams } from "react-router-dom";

import Button from "../../components/common/Button";
import ErrorState from "../../components/common/ErrorState";
import LoadingState from "../../components/common/LoadingState";
import StatusBadge from "../../components/common/StatusBadge";
import SurveyReportActions from "../../components/surveyor/SurveyReportActions";
import SurveyReportContent from "../../components/surveyor/SurveyReportContent";
import { surveyReportErrorMessage } from "../../components/surveyor/workflowProgress";
import { useFetch } from "../../hooks/useFetch";
import { getSubmittedSurveyReport, getSurveyReport } from "../../services/surveyorService";

// The readable survey report (View Report). Read-only: it shows the
// backend's report for this claim - the same data as the PDF download - and
// never submits or changes anything. Access and workflow completeness are
// enforced by the backend (403 for anyone but the assigned surveyor, 409
// while the workflow is incomplete).
export default function SurveyReportViewPage() {
  // /surveyor/claims/:claimId/report/view (current workflow) or
  // /surveyor/history/:inspectionId (a submitted report from the history).
  const { claimId, inspectionId } = useParams();
  const fetchReport = useCallback(
    () => (inspectionId ? getSubmittedSurveyReport(inspectionId) : getSurveyReport(claimId)),
    [claimId, inspectionId]
  );
  const { data: report, isLoading, error, reload } = useFetch(fetchReport, [fetchReport]);

  const backLink = (
    <Link
      to={inspectionId ? "/surveyor/history" : `/surveyor/claims/${claimId}/report`}
      className="inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:text-brand-700 print:hidden"
    >
      <ArrowLeft className="h-4 w-4" aria-hidden="true" />
      {inspectionId ? "Back to Survey Reports" : "Back to Survey Report"}
    </Link>
  );

  if (isLoading) return <LoadingState label="Loading survey report..." />;
  if (error) {
    return (
      <div className="space-y-4">
        {backLink}
        <ErrorState message={surveyReportErrorMessage(error)} onRetry={reload} />
      </div>
    );
  }

  const submitted = report.report_status === "Submitted";
  const generated = new Date(report.generated_at);

  return (
    <div className="mx-auto max-w-4xl">
      {backLink}
      <header className="mb-6 mt-4 border-b-2 border-brand-600 pb-4">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-brand-800">Motor Insurance Survey Report</h1>
            <p className="mt-1 text-sm text-muted">
              Claim {report.claim.Claim_Number} · Surveyor {report.surveyor?.Employee_ID ?? "Not available"}
            </p>
            <p className="mt-1 text-xs text-muted">
              Generated{" "}
              {Number.isNaN(generated.getTime())
                ? report.generated_at
                : generated.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}
            </p>
            <div className="mt-2">
              <StatusBadge label={submitted ? "Submitted" : "Draft - not yet submitted"} tone={submitted ? "success" : "warning"} />
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3 print:hidden">
            <Button variant="secondary" onClick={() => window.print()}>
              <Printer className="h-4 w-4" aria-hidden="true" />
              Print
            </Button>
            <SurveyReportActions
              claimId={claimId}
              inspectionId={inspectionId}
              claimNumber={report.claim.Claim_Number}
              showView={false}
              downloadLabel={inspectionId ? "Download Document" : "Download Report"}
            />
          </div>
        </div>
      </header>
      <SurveyReportContent report={report} />
    </div>
  );
}
