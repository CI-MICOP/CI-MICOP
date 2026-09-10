import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../hooks/useAuth", () => ({
  useAuth: () => ({ user: { Employee_ID: "EMP-1" } }),
}));
vi.mock("../../../services/claimService", () => ({
  getClaimById: vi.fn(),
}));
vi.mock("../../../services/surveyorService", () => ({
  getAssignedClaimDetail: vi.fn(),
  updateInspection: vi.fn(),
}));

import { getClaimById } from "../../../services/claimService";
import { getAssignedClaimDetail, updateInspection } from "../../../services/surveyorService";
import SurveyReportPage from "../SurveyReportPage";

const CLAIM = { Claim_ID: "CLM-1", Claim_Number: "CLM-2026-AAAA" };

const COMPLETE_INSPECTION = {
  Inspection_ID: "INSP-1",
  Claim_ID: "CLM-1",
  Surveyor_ID: "EMP-1",
  Vehicle_Condition: "Good",
  Damage_Observed: "Yes",
  Damage_Severity: "Minor",
  Parts_Required: 2,
  Repair_Recommendation: "Repair",
  Surveyor_Comments: "Front bumper scratch.",
  Inspection_Status: "In Progress",
  Survey_Report_Submitted: false,
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/surveyor/claims/CLM-1/report"]}>
      <Routes>
        <Route path="/surveyor/claims/:claimId/report" element={<SurveyReportPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("SurveyReportPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getClaimById.mockResolvedValue(CLAIM);
  });

  it("Submit Survey Report calls PATCH via updateInspection() with Survey_Report_Submitted: true", async () => {
    getAssignedClaimDetail.mockResolvedValue({ inspections: [COMPLETE_INSPECTION] });
    updateInspection.mockResolvedValueOnce({ ...COMPLETE_INSPECTION, Survey_Report_Submitted: true });

    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /submit survey report/i }));

    await waitFor(() =>
      expect(updateInspection).toHaveBeenCalledWith("INSP-1", { Survey_Report_Submitted: true })
    );
    expect(await screen.findByText(/marked as submitted/i)).toBeInTheDocument();
  });

  it("does not show a submit button once the report is already submitted", async () => {
    getAssignedClaimDetail.mockResolvedValue({
      inspections: [{ ...COMPLETE_INSPECTION, Survey_Report_Submitted: true }],
    });
    renderPage();

    expect(await screen.findByText("Submitted")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /submit survey report/i })).not.toBeInTheDocument();
  });

  it("displays a clear error, without claiming success, when the backend rejects an incomplete submission", async () => {
    getAssignedClaimDetail.mockResolvedValue({
      inspections: [{ ...COMPLETE_INSPECTION, Vehicle_Condition: "Pending" }],
    });
    updateInspection.mockRejectedValueOnce({
      response: { status: 400, data: { detail: "Cannot submit an incomplete inspection." } },
    });

    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /submit survey report/i }));

    expect(await screen.findByText(/something went wrong while loading this data\./i)).toBeInTheDocument();
    expect(screen.queryByText(/marked as submitted/i)).not.toBeInTheDocument();
  });
});
