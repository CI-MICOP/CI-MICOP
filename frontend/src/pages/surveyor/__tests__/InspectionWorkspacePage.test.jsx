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
  startInspection: vi.fn(),
}));

import { getClaimById } from "../../../services/claimService";
import { getAssignedClaimDetail, startInspection, updateInspection } from "../../../services/surveyorService";
import InspectionWorkspacePage from "../InspectionWorkspacePage";

const CLAIM = { Claim_ID: "CLM-1", Claim_Number: "CLM-2026-AAAA", Claim_Type: "Own Damage", Claim_Status: "Under Review" };

const INSPECTION = {
  Inspection_ID: "INSP-1",
  Claim_ID: "CLM-1",
  Surveyor_ID: "EMP-1",
  Inspection_Date: "2026-09-01",
  Inspection_Location: "Chennai",
  Vehicle_Condition: "Pending",
  Damage_Observed: "Pending",
  Damage_Severity: "Pending",
  Parts_Required: 0,
  Repair_Recommendation: "Pending",
  Surveyor_Comments: "",
  Inspection_Status: "Assigned",
  Survey_Report_Submitted: false,
  Surveyor_Confidence_Score: 0,
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/surveyor/claims/CLM-1/inspection"]}>
      <Routes>
        <Route path="/surveyor/claims/:claimId/inspection" element={<InspectionWorkspacePage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("InspectionWorkspacePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getClaimById.mockResolvedValue(CLAIM);
  });

  it("shows a loading state while fetching", async () => {
    getAssignedClaimDetail.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getByText(/loading inspection/i)).toBeInTheDocument();
  });

  it("displays an API error when the claim/inspection fetch fails", async () => {
    getAssignedClaimDetail.mockRejectedValue({ response: { status: 403 } });
    renderPage();
    expect(await screen.findByText(/don't have access/i)).toBeInTheDocument();
  });

  it("shows the not-started empty state with a Start Inspection button when the surveyor has no inspection yet", async () => {
    getAssignedClaimDetail.mockResolvedValue({ accidents: [], inspections: [] });
    renderPage();
    expect(await screen.findByText(/inspection has not been started yet/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /start inspection/i })).toBeInTheDocument();
  });

  it("Start Inspection calls POST via startInspection() and then loads the newly created inspection", async () => {
    getAssignedClaimDetail
      .mockResolvedValueOnce({ accidents: [], inspections: [] })
      .mockResolvedValueOnce({ accidents: [], inspections: [INSPECTION] });
    startInspection.mockResolvedValueOnce(INSPECTION);

    renderPage();
    const startButton = await screen.findByRole("button", { name: /start inspection/i });
    fireEvent.click(startButton);

    await waitFor(() => expect(startInspection).toHaveBeenCalledWith("CLM-1"));
    expect(await screen.findByRole("button", { name: /save inspection/i })).toBeInTheDocument();
  });

  it("loads existing inspection values into the form", async () => {
    getAssignedClaimDetail.mockResolvedValue({
      accidents: [],
      inspections: [{ ...INSPECTION, Vehicle_Condition: "Good", Damage_Observed: "Yes", Parts_Required: 3 }],
    });
    renderPage();

    expect(await screen.findByDisplayValue("Good")).toBeInTheDocument();
    expect(screen.getByDisplayValue("3")).toBeInTheDocument();
  });

  it("Save Inspection calls PATCH via updateInspection() with the edited fields", async () => {
    getAssignedClaimDetail.mockResolvedValue({ accidents: [], inspections: [INSPECTION] });
    updateInspection.mockResolvedValueOnce({ ...INSPECTION, Vehicle_Condition: "Good" });

    renderPage();
    const vehicleConditionSelect = await screen.findByLabelText(/vehicle condition/i);
    fireEvent.change(vehicleConditionSelect, { target: { value: "Good" } });
    fireEvent.click(screen.getByRole("button", { name: /save inspection/i }));

    await waitFor(() =>
      expect(updateInspection).toHaveBeenCalledWith("INSP-1", expect.objectContaining({ Vehicle_Condition: "Good" }))
    );
    expect(await screen.findByText(/updated successfully/i)).toBeInTheDocument();
  });

  it("displays an API error when saving the inspection fails", async () => {
    getAssignedClaimDetail.mockResolvedValue({ accidents: [], inspections: [INSPECTION] });
    updateInspection.mockRejectedValueOnce({ response: { status: 403 } });

    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /save inspection/i }));

    expect(await screen.findByText(/don't have access/i)).toBeInTheDocument();
  });
});
