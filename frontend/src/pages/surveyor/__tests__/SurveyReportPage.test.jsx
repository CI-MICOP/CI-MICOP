import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../hooks/useAuth", () => ({
  useAuth: () => ({ user: { Employee_ID: "EMP-1" } }),
}));
vi.mock("../../../services/claimService", () => ({
  getClaimById: vi.fn(),
}));
vi.mock("../../../services/surveyorService", () => ({
  getAssignedClaimDetail: vi.fn(),
  updateInspection: vi.fn(),
  getSurveyReport: vi.fn(),
  downloadSurveyReportPdf: vi.fn(),
}));

import { REPORT } from "../../../components/surveyor/__tests__/reportFixture";
import { COMPLETE_INSPECTION, schedule, workflow } from "../../../components/surveyor/__tests__/workflowFixture";
import { getClaimById } from "../../../services/claimService";
import { getAssignedClaimDetail, getSurveyReport, updateInspection } from "../../../services/surveyorService";
import SurveyReportPage from "../SurveyReportPage";

const CLAIM = { Claim_ID: "CLM-1", Claim_Number: "CLM-2026-AAAA" };

const detail = (stage = "evidence", overrides = {}, inspection = COMPLETE_INSPECTION) => ({
  inspections: [inspection],
  vehicle_damage: [{ Damage_ID: "DMG-1" }],
  evidence: [],
  workflow: workflow(stage, overrides),
});

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/surveyor/claims/CLM-1/report"]}>
      <Routes>
        <Route path="/surveyor/claims/:claimId/report" element={<SurveyReportPage />} />
        <Route path="/surveyor/claims/:claimId/report/view" element={<p>Report view</p>} />
      </Routes>
    </MemoryRouter>
  );
}

describe("SurveyReportPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getClaimById.mockResolvedValue(CLAIM);
    getSurveyReport.mockResolvedValue(REPORT);
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });
  afterEach(() => vi.restoreAllMocks());

  it("shows the review of every section from the backend's report", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail());
    renderPage();

    for (const heading of [
      "A. Claim Information",
      "B. Accident Information",
      "C. Inspection Details",
      "D. Vehicle Damage Assessment",
      "E. Evidence and Capture Metadata",
      "F. Surveyor",
    ]) {
      expect(await screen.findByRole("heading", { name: heading })).toBeInTheDocument();
    }
    expect(getSurveyReport).toHaveBeenCalledWith("CLM-1");
    expect(screen.getByText("Asha R")).toBeInTheDocument();
    expect(screen.getByText("Damage 1: Rear Bumper")).toBeInTheDocument();
    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /view report/i })).toHaveAttribute("href", "/surveyor/claims/CLM-1/report/view");
    expect(screen.getByRole("button", { name: /download report/i })).toBeInTheDocument();
  });

  it("does not request the report until the earlier steps are complete", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail("damage"));
    renderPage();
    expect(await screen.findByRole("heading", { name: "Complete the earlier steps first" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /go to evidence/i })).toBeInTheDocument();
    expect(getSurveyReport).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: /submit final survey report/i })).not.toBeInTheDocument();
  });

  it("is locked before the scheduled date", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail("evidence", { schedule: schedule({ reached: false }) }));
    renderPage();
    expect(await screen.findByRole("heading", { name: "Inspection not open yet" })).toBeInTheDocument();
    expect(getSurveyReport).not.toHaveBeenCalled();
  });

  it("submits only after the final-submission confirmation, once", async () => {
    getAssignedClaimDetail
      .mockResolvedValueOnce(detail())
      .mockResolvedValue(detail("submitted", {}, { ...COMPLETE_INSPECTION, Survey_Report_Submitted: true }));
    updateInspection.mockResolvedValueOnce({ ...COMPLETE_INSPECTION, Survey_Report_Submitted: true });
    window.confirm.mockReturnValueOnce(false);

    renderPage();
    const submit = await screen.findByRole("button", { name: "Submit Final Survey Report" });
    fireEvent.click(submit);
    expect(window.confirm).toHaveBeenCalledWith(expect.stringMatching(/submission is final/i));
    expect(updateInspection).not.toHaveBeenCalled(); // cancelled

    fireEvent.click(submit);
    await waitFor(() => expect(updateInspection).toHaveBeenCalledWith("INSP-1", { Survey_Report_Submitted: true }));
    expect(updateInspection).toHaveBeenCalledTimes(1);
    expect(await screen.findByText(/final survey report submitted/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Survey Reports" })).toHaveAttribute("href", "/surveyor/history");
  });

  it("viewing the review never submits the report", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail());
    renderPage();
    await screen.findByRole("heading", { name: "A. Claim Information" });
    expect(updateInspection).not.toHaveBeenCalled();
  });

  it("shows a submitted report read-only, without a submit button", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail("submitted", {}, { ...COMPLETE_INSPECTION, Survey_Report_Submitted: true }));
    getSurveyReport.mockResolvedValue({ ...REPORT, report_status: "Submitted" });
    renderPage();
    expect(await screen.findByText("Submitted")).toBeInTheDocument();
    expect(screen.getByText(/can no longer be changed/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /submit final survey report/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /download report/i })).toBeInTheDocument();
  });

  it("shows the backend's reason, without claiming success, when it rejects the submission", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail());
    updateInspection.mockRejectedValueOnce({
      response: { status: 400, data: { detail: "Cannot submit the survey report yet. No photo captured with the in-app camera has been saved." } },
    });
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Submit Final Survey Report" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/no photo captured with the in-app camera/i);
    expect(screen.queryByText(/final survey report submitted/i)).not.toBeInTheDocument();
  });

  it("explains when the backend refuses the report as incomplete", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail());
    getSurveyReport.mockRejectedValueOnce({ response: { status: 409 } });
    renderPage();
    expect(await screen.findByText(/available once the inspection, vehicle damage and evidence steps are complete/i)).toBeInTheDocument();
  });
});
