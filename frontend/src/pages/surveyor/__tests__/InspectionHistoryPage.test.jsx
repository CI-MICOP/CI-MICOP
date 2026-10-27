import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../services/surveyorService", () => ({
  getSurveyReports: vi.fn(),
  downloadSubmittedSurveyReportPdf: vi.fn(),
  downloadSurveyReportPdf: vi.fn(),
}));

import { downloadSubmittedSurveyReportPdf, getSurveyReports } from "../../../services/surveyorService";
import InspectionHistoryPage from "../InspectionHistoryPage";

const ROW = {
  inspection: {
    Inspection_ID: "INSP-OLD",
    Claim_ID: "CLM-1",
    Inspection_Date: "2026-10-28",
    Inspection_Location: "Chennai",
    Inspection_Status: "Completed",
    Survey_Report_Submitted: true,
  },
  claim: { Claim_ID: "CLM-1", Claim_Number: "CLM-2026-AAAA", Vehicle_ID: "VEH-1" },
};

function renderPage() {
  return render(
    <MemoryRouter>
      <InspectionHistoryPage />
    </MemoryRouter>
  );
}

describe("InspectionHistoryPage (Survey Reports)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSurveyReports.mockResolvedValue([ROW]);
  });
  afterEach(() => vi.restoreAllMocks());

  it("lists submitted reports with View Document and Download Document - never the editable workflow", async () => {
    renderPage();
    expect(await screen.findByText("CLM-2026-AAAA")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Survey Reports" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /view document/i })).toHaveAttribute("href", "/surveyor/history/INSP-OLD");
    expect(screen.queryByRole("link", { name: /view claim/i })).not.toBeInTheDocument();
    expect(screen.getByText("Submitted")).toBeInTheDocument();
  });

  it("downloads the submitted report's PDF", async () => {
    downloadSubmittedSurveyReportPdf.mockResolvedValue({ blob: new Blob(["%PDF"]), filename: "survey-report-CLM-2026-AAAA.pdf" });
    const originalCreate = URL.createObjectURL;
    const originalRevoke = URL.revokeObjectURL;
    URL.createObjectURL = vi.fn(() => "blob:report");
    URL.revokeObjectURL = vi.fn();
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /download document/i }));
    await waitFor(() => expect(click).toHaveBeenCalled());
    expect(downloadSubmittedSurveyReportPdf).toHaveBeenCalledWith("INSP-OLD", "survey-report-CLM-2026-AAAA.pdf");
    URL.createObjectURL = originalCreate;
    URL.revokeObjectURL = originalRevoke;
  });

  it("shows an empty state before any report is submitted", async () => {
    getSurveyReports.mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText("No submitted survey reports yet.")).toBeInTheDocument();
  });

  it("shows an error with a retry when loading fails", async () => {
    getSurveyReports.mockRejectedValue({ response: { status: 500 } });
    renderPage();
    expect(await screen.findByText("Something went wrong while loading this data.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry|try again/i })).toBeInTheDocument();
  });

  it("centres the Document header over its two actions, which share one centred row", async () => {
    renderPage();
    await screen.findByText("CLM-2026-AAAA");
    const header = screen.getByRole("columnheader", { name: "Document" });
    expect(header).toHaveClass("text-center", "align-middle");
    const view = screen.getByRole("link", { name: /view document/i });
    const download = screen.getByRole("button", { name: /download document/i });
    const row = view.parentElement;
    expect(download.parentElement).toBe(row);
    expect(row).toHaveClass("flex", "items-center", "justify-center");
    expect(view).toHaveClass("whitespace-nowrap");
    expect(download).toHaveClass("whitespace-nowrap");
    expect(view.closest("td")).toHaveClass("sm:text-center", "align-middle");
  });
});
