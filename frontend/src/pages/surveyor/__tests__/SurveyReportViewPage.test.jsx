import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../services/surveyorService", () => ({
  getSurveyReport: vi.fn(),
  downloadSurveyReportPdf: vi.fn(),
  getSubmittedSurveyReport: vi.fn(),
  downloadSubmittedSurveyReportPdf: vi.fn(),
}));

import { REPORT } from "../../../components/surveyor/__tests__/reportFixture";
import {
  downloadSubmittedSurveyReportPdf,
  downloadSurveyReportPdf,
  getSubmittedSurveyReport,
  getSurveyReport,
} from "../../../services/surveyorService";
import SurveyReportViewPage from "../SurveyReportViewPage";

function renderPage(claimId = "CLM-1", path = `/surveyor/claims/${claimId}/report/view`) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/surveyor/claims/:claimId/report/view" element={<SurveyReportViewPage />} />
        <Route path="/surveyor/history/:inspectionId" element={<SurveyReportViewPage />} />
      </Routes>
    </MemoryRouter>
  );
}

const section = (title) => within(screen.getByRole("heading", { name: title }).closest("section"));

describe("SurveyReportViewPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSurveyReport.mockResolvedValue(REPORT);
  });
  afterEach(() => vi.restoreAllMocks());

  it("opens the report for the selected claim with every section", async () => {
    renderPage("CLM-1");
    expect(await screen.findByRole("heading", { name: "Motor Insurance Survey Report" })).toBeInTheDocument();
    expect(getSurveyReport).toHaveBeenCalledWith("CLM-1");
    expect(screen.getByText(/claim CLM-2026-AAAA · surveyor EMP-1/i)).toBeInTheDocument();
    expect(screen.getByText("Draft - not yet submitted")).toBeInTheDocument();

    expect(section("A. Claim Information").getByText("Asha R")).toBeInTheDocument();
    expect(section("A. Claim Information").getByText("TN01AB1234")).toBeInTheDocument();
    expect(section("B. Accident Information").getByText("Anna Salai")).toBeInTheDocument();
    expect(section("C. Inspection Details").getByText("Rear bumper cracked.")).toBeInTheDocument();
    expect(section("D. Vehicle Damage Assessment").getByText("Damage 1: Rear Bumper")).toBeInTheDocument();
    expect(section("E. Evidence and Capture Metadata").getByText("Evidence 1: rear.jpg")).toBeInTheDocument();
    expect(section("F. Surveyor").getByText("EMP-1")).toBeInTheDocument();
  });

  it("shows missing values and pending analysis honestly", async () => {
    renderPage();
    await screen.findByRole("heading", { name: "Motor Insurance Survey Report" });
    const claimInfo = section("A. Claim Information");
    expect(within(claimInfo.getByText("Policy Number").parentElement).getByText("Not available")).toBeInTheDocument();
    const evidence = section("E. Evidence and Capture Metadata");
    expect(evidence.getByText("Not analysed yet")).toBeInTheDocument();
    expect(evidence.getByText(/image quality 0\.82/i)).toBeInTheDocument(); // the analysed one
  });

  it("flags an invalid stored value instead of hiding or correcting it", async () => {
    getSurveyReport.mockResolvedValue({
      ...REPORT,
      report_status: "Submitted",
      inspection: { ...REPORT.inspection, Vehicle_Condition: "Damaged" },
      invalid_values: [{ field: "Vehicle_Condition", label: "Vehicle Condition", value: "Damaged" }],
    });
    renderPage();
    await screen.findByRole("heading", { name: "Motor Insurance Survey Report" });
    expect(screen.getByText("(not a valid option)")).toBeInTheDocument();
    expect(screen.getByText("Submitted")).toBeInTheDocument();
  });

  it("downloads the PDF for the same claim", async () => {
    const blob = new Blob(["%PDF-1.7"], { type: "application/pdf" });
    downloadSurveyReportPdf.mockResolvedValue({ blob, filename: "survey-report-CLM-2026-AAAA.pdf" });
    URL.createObjectURL = vi.fn(() => "blob:report");
    URL.revokeObjectURL = vi.fn();
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    renderPage("CLM-1");
    const download = await screen.findByRole("button", { name: /download report/i });
    fireEvent.click(download);
    fireEvent.click(download); // a repeated click while downloading

    await waitFor(() => expect(click).toHaveBeenCalledTimes(1));
    expect(downloadSurveyReportPdf).toHaveBeenCalledTimes(1);
    expect(downloadSurveyReportPdf).toHaveBeenCalledWith("CLM-1", "survey-report-CLM-2026-AAAA.pdf");
    expect(URL.createObjectURL).toHaveBeenCalledWith(blob);
  });

  it("shows why a download failed", async () => {
    downloadSurveyReportPdf.mockRejectedValue({ response: { status: 403 } });
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /download report/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/only the surveyor assigned to this claim/i);
  });

  it("explains an unavailable report instead of showing a placeholder", async () => {
    getSurveyReport.mockRejectedValue({ response: { status: 409 } });
    renderPage();
    expect(await screen.findByText(/available once the inspection, vehicle damage and evidence steps are complete/i)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Motor Insurance Survey Report" })).not.toBeInTheDocument();
  });

  it("shows the capture metadata, keeping device-reported and server values apart", async () => {
    renderPage();
    await screen.findByRole("heading", { name: "Motor Insurance Survey Report" });
    const evidence = section("E. Evidence and Capture Metadata");
    expect(evidence.getByText("In-app camera")).toBeInTheDocument();
    expect(evidence.getByText("13.082700, 80.270700 (±12 m)")).toBeInTheDocument();
    expect(evidence.getByText("GPS verified")).toBeInTheDocument();
    expect(evidence.getByText(/No in-app capture record/)).toBeInTheDocument(); // the customer upload
    expect(evidence.getByText(/not proof of where or when/i)).toBeInTheDocument();
  });

  it("opens a submitted report from the Survey Reports history, read-only", async () => {
    getSubmittedSurveyReport.mockResolvedValue({ ...REPORT, report_status: "Submitted" });
    downloadSubmittedSurveyReportPdf.mockResolvedValue({ blob: new Blob(["%PDF"]), filename: "r.pdf" });
    URL.createObjectURL = vi.fn(() => "blob:report");
    URL.revokeObjectURL = vi.fn();
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    renderPage(undefined, "/surveyor/history/INSP-OLD");

    expect(await screen.findByText("Submitted")).toBeInTheDocument();
    expect(getSubmittedSurveyReport).toHaveBeenCalledWith("INSP-OLD");
    expect(getSurveyReport).not.toHaveBeenCalled();
    expect(screen.getByRole("link", { name: /back to survey reports/i })).toHaveAttribute("href", "/surveyor/history");
    expect(screen.queryByRole("button", { name: /submit/i })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /download document/i }));
    await waitFor(() => expect(downloadSubmittedSurveyReportPdf).toHaveBeenCalledWith("INSP-OLD", "survey-report-CLM-2026-AAAA.pdf"));
  });

  it("states when a submitted report does not meet the current rules, keeping it as submitted", async () => {
    getSubmittedSurveyReport.mockResolvedValue({
      ...REPORT,
      report_status: "Submitted",
      evidence: [],
      submission_review: {
        meets_current_requirements: false,
        problems: ["No photo captured with the in-app camera by the assigned surveyor, with a usable location reading, has been saved."],
        message: "This report was submitted, but its saved records do not meet the current submission requirements. It is kept exactly as submitted and has not been re-verified.",
      },
    });
    renderPage(undefined, "/surveyor/history/INSP-OLD");
    expect(await screen.findByRole("note")).toHaveTextContent(/has not been re-verified/i);
    expect(screen.getByText("Submitted")).toBeInTheDocument();
  });

  it("shows no review notice for a draft or a compliant submission", async () => {
    renderPage();
    await screen.findByText("Draft - not yet submitted");
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
  });
});
