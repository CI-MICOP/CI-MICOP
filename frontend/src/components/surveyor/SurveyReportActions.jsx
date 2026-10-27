import { Download, Eye } from "lucide-react";
import { useRef, useState } from "react";
import { Link } from "react-router-dom";

import { downloadSubmittedSurveyReportPdf, downloadSurveyReportPdf } from "../../services/surveyorService";
import Button from "../common/Button";
import { surveyReportErrorMessage } from "./workflowProgress";

const viewLinkClass =
  "inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-white px-4 py-2 text-sm font-medium text-ink transition-colors hover:bg-surface";

/**
 * View (the readable report page) and Download (the PDF the backend
 * renders from the same report data). Neither changes the report:
 * submission stays a separate step.
 *
 * For the current claim workflow pass `claimId`; for a submitted report in
 * the Survey Reports history pass `inspectionId`.
 */
export default function SurveyReportActions({
  claimId,
  inspectionId,
  claimNumber,
  showView = true,
  viewLabel = "View Report",
  downloadLabel = "Download Report",
  size = "md",
  centered = false,
}) {
  const [state, setState] = useState({ status: "idle", message: "" });
  const downloadingRef = useRef(false);
  const viewTo = inspectionId ? `/surveyor/history/${inspectionId}` : `/surveyor/claims/${claimId}/report/view`;
  const fallbackName = `survey-report-${claimNumber ?? inspectionId ?? claimId}.pdf`;

  async function handleDownload() {
    if (downloadingRef.current) return;
    downloadingRef.current = true;
    setState({ status: "downloading", message: "" });
    try {
      const { blob, filename } = inspectionId
        ? await downloadSubmittedSurveyReportPdf(inspectionId, fallbackName)
        : await downloadSurveyReportPdf(claimId, fallbackName);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setState({ status: "idle", message: "" });
    } catch (err) {
      setState({ status: "error", message: surveyReportErrorMessage(err) });
    } finally {
      downloadingRef.current = false;
    }
  }

  const small = size === "sm";
  return (
    <div className="print:hidden">
      <div className={`flex flex-wrap items-center gap-2 ${centered ? "justify-center max-sm:justify-end" : ""}`}>
        {showView && (
          <Link to={viewTo} className={`${small ? viewLinkClass.replace("px-4 py-2", "px-3 py-1.5") : viewLinkClass} whitespace-nowrap`}>
            <Eye className="h-4 w-4" aria-hidden="true" />
            {viewLabel}
          </Link>
        )}
        <Button variant="secondary" size={size} className="whitespace-nowrap" onClick={handleDownload} isLoading={state.status === "downloading"}>
          {state.status !== "downloading" && <Download className="h-4 w-4" aria-hidden="true" />}
          {downloadLabel}
        </Button>
      </div>
      {state.status === "error" && (
        <p role="alert" className={`mt-2 text-sm text-danger ${centered ? "text-center" : ""}`}>
          {state.message}
        </p>
      )}
    </div>
  );
}
