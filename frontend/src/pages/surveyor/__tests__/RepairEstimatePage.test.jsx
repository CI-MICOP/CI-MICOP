import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../services/claimService", () => ({
  getClaimById: vi.fn(),
}));
vi.mock("../../../services/surveyorService", () => ({
  getAssignedClaimDetail: vi.fn(),
  createRepairEstimate: vi.fn(),
}));

import { getClaimById } from "../../../services/claimService";
import { createRepairEstimate, getAssignedClaimDetail } from "../../../services/surveyorService";
import RepairEstimatePage from "../RepairEstimatePage";

const CLAIM = {
  Claim_ID: "CLM-1",
  Claim_Number: "CLM-2026-AAAA",
  Claim_Type: "Own Damage",
  Claim_Amount: 50000,
  Claim_Status: "Under Investigation",
};

const ESTIMATE_1 = {
  Estimate_ID: "EST-1",
  Claim_ID: "CLM-1",
  Vehicle_ID: "VEH-1",
  Garage_ID: "GAR-0001",
  Estimate_Date: "2026-09-01",
  Repair_Estimate: 50000,
  Repair_Cost: 52000,
  Parts_Cost: 20000,
  Labour_Cost: 15000,
  Painting_Cost: 5000,
  Replacement_Parts_Count: 2,
  Repaired_Parts_Count: 1,
  Estimated_Repair_Days: 7,
  Actual_Repair_Days: 0,
  Excessive_Claim_Amount_Indicator: false,
  Estimate_Anomaly_Score: 0,
};

const ESTIMATE_2 = { ...ESTIMATE_1, Estimate_ID: "EST-2", Garage_ID: "GAR-0002" };

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/surveyor/claims/CLM-1/repair-estimate"]}>
      <Routes>
        <Route path="/surveyor/claims/:claimId/repair-estimate" element={<RepairEstimatePage />} />
      </Routes>
    </MemoryRouter>
  );
}

function fillRequiredFields() {
  fireEvent.change(screen.getByLabelText(/garage id/i), { target: { value: "GAR-0099" } });
  fireEvent.change(screen.getByLabelText(/^repair estimate/i), { target: { value: "50000" } });
  fireEvent.change(screen.getByLabelText(/^repair cost/i), { target: { value: "52000" } });
  fireEvent.change(screen.getByLabelText(/^parts cost/i), { target: { value: "20000" } });
  fireEvent.change(screen.getByLabelText(/^labour cost/i), { target: { value: "15000" } });
  fireEvent.change(screen.getByLabelText(/^painting cost/i), { target: { value: "5000" } });
  fireEvent.change(screen.getByLabelText(/replacement parts count/i), { target: { value: "2" } });
  fireEvent.change(screen.getByLabelText(/repaired parts count/i), { target: { value: "1" } });
  fireEvent.change(screen.getByLabelText(/estimated repair days/i), { target: { value: "7" } });
}

describe("RepairEstimatePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getClaimById.mockResolvedValue(CLAIM);
  });

  it("loads the page", async () => {
    getAssignedClaimDetail.mockResolvedValue({ repair_estimates: [] });
    renderPage();
    expect(await screen.findByText(/repair estimate — clm-2026-aaaa/i)).toBeInTheDocument();
  });

  it("displays the claim summary", async () => {
    getAssignedClaimDetail.mockResolvedValue({ repair_estimates: [] });
    renderPage();
    expect(await screen.findByText("Own Damage")).toBeInTheDocument();
    expect(screen.getByText("₹50,000")).toBeInTheDocument();
    expect(screen.getByText("Under Investigation")).toBeInTheDocument();
  });

  it("shows the estimate form fields when Add Estimate is clicked", async () => {
    getAssignedClaimDetail.mockResolvedValue({ repair_estimates: [] });
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /add estimate/i }));
    expect(screen.getByLabelText(/garage id/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^repair estimate/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save repair estimate/i })).toBeInTheDocument();
  });

  it("does not allow submission until required fields are filled (validation)", async () => {
    getAssignedClaimDetail.mockResolvedValue({ repair_estimates: [] });
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /add estimate/i }));
    expect(screen.getByRole("button", { name: /save repair estimate/i })).toBeDisabled();

    fillRequiredFields();

    expect(screen.getByRole("button", { name: /save repair estimate/i })).not.toBeDisabled();
  });

  it("valid submission calls createRepairEstimate and refreshes the list", async () => {
    getAssignedClaimDetail
      .mockResolvedValueOnce({ repair_estimates: [] })
      .mockResolvedValueOnce({ repair_estimates: [ESTIMATE_1] });
    createRepairEstimate.mockResolvedValueOnce(ESTIMATE_1);

    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /add estimate/i }));
    fillRequiredFields();
    fireEvent.click(screen.getByRole("button", { name: /save repair estimate/i }));

    await waitFor(() =>
      expect(createRepairEstimate).toHaveBeenCalledWith(
        expect.objectContaining({ Claim_ID: "CLM-1", Garage_ID: "GAR-0099" })
      )
    );
    expect(await screen.findByText(/repair estimate saved/i)).toBeInTheDocument();
    expect(await screen.findByText("EST-1")).toBeInTheDocument();
  });

  it("displays the actual API error when submission fails", async () => {
    getAssignedClaimDetail.mockResolvedValue({ repair_estimates: [] });
    createRepairEstimate.mockRejectedValueOnce({ response: { status: 403 } });

    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /add estimate/i }));
    fillRequiredFields();
    fireEvent.click(screen.getByRole("button", { name: /save repair estimate/i }));

    expect(await screen.findByText(/don't have access/i)).toBeInTheDocument();
  });

  it("shows the automated analysis as pending, never a fabricated score", async () => {
    getAssignedClaimDetail.mockResolvedValue({ repair_estimates: [ESTIMATE_1] });
    renderPage();

    expect(await screen.findByText(/ai analysis pending/i)).toBeInTheDocument();
    expect(screen.queryByText("Anomaly Score")).not.toBeInTheDocument();
    expect(screen.queryByText(/anomaly score: 0/i)).not.toBeInTheDocument();
  });

  it("renders multiple estimates", async () => {
    getAssignedClaimDetail.mockResolvedValue({ repair_estimates: [ESTIMATE_1, ESTIMATE_2] });
    renderPage();
    expect(await screen.findByText("EST-1")).toBeInTheDocument();
    expect(screen.getByText("EST-2")).toBeInTheDocument();
  });
});
