import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../services/claimService", () => ({ getClaimById: vi.fn() }));
vi.mock("../../../services/documentService", () => ({ listDocumentsByClaim: vi.fn() }));
vi.mock("../../../services/policyService", () => ({ getPolicyById: vi.fn() }));
vi.mock("../../../services/vehicleService", () => ({ getVehicleById: vi.fn() }));

import { getClaimById } from "../../../services/claimService";
import { listDocumentsByClaim } from "../../../services/documentService";
import { getPolicyById } from "../../../services/policyService";
import { getVehicleById } from "../../../services/vehicleService";
import ClaimDetailsPage from "../ClaimDetailsPage";

const BASE_CLAIM = {
  Claim_ID: "CLM-1",
  Claim_Number: "CLM-2026-AAAA",
  Claim_Date: "2026-06-01",
  Claim_Type: "Own Damage",
  Claim_Amount: 50000,
  Approved_Amount: 0,
  Claim_Status: "Under Review",
  Final_Decision: null,
  Decision_Date: null,
  Claim_Description: "Test claim.",
  Place_of_Accident: "TestCity",
  Accident_Pincode: "123456",
  Policy_ID: "POL-1",
  Vehicle_ID: "VEH-1",
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/customer/claims/CLM-1"]}>
      <Routes>
        <Route path="/customer/claims/:claimId" element={<ClaimDetailsPage />} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  listDocumentsByClaim.mockResolvedValue([]);
  getPolicyById.mockResolvedValue({ Policy_Number: "POL-NUM-1", Policy_Type: "Comprehensive" });
  getVehicleById.mockResolvedValue({ Fuel_Type: "Petrol", Manufacturing_Year: 2020, Vehicle_Make: "Test", Vehicle_Model: "Car" });
});

describe("Customer ClaimDetailsPage - status consistency after a decision", () => {
  it("shows Under Review for a claim with no final decision yet", async () => {
    getClaimById.mockResolvedValue(BASE_CLAIM);
    renderPage();
    const statusDetail = (await screen.findByText("Claim Status")).closest("div");
    expect(within(statusDetail).getByText("Under Review")).toBeInTheDocument();
    const stageDetail = screen.getByText("Current Stage").closest("div");
    expect(within(stageDetail).getByText("Under Review")).toBeInTheDocument();
    expect(screen.getByText("Final Decision").closest("div")).toHaveTextContent("Pending");
  });

  it("shows the finalized Completed status for a rejected decision - never a stale Under Review", async () => {
    getClaimById.mockResolvedValue({
      ...BASE_CLAIM,
      Claim_Status: "Completed",
      Final_Decision: "Rejected",
      Decision_Date: "2026-10-28",
    });
    renderPage();
    const statusDetail = (await screen.findByText("Claim Status")).closest("div");
    expect(within(statusDetail).getByText("Completed")).toBeInTheDocument();
    expect(within(statusDetail).queryByText("Under Review")).not.toBeInTheDocument();

    const stageDetail = screen.getByText("Current Stage").closest("div");
    expect(within(stageDetail).getByText("Completed")).toBeInTheDocument();

    const decisionDetail = screen.getByText("Final Decision").closest("div");
    expect(within(decisionDetail).getByText("Rejected")).toBeInTheDocument();

    // Recent Activity stays consistent with the same saved decision.
    expect(await screen.findByText("Decision recorded: Rejected")).toBeInTheDocument();
  });

  it("shows the finalized Completed status for an approved decision", async () => {
    getClaimById.mockResolvedValue({
      ...BASE_CLAIM,
      Claim_Status: "Completed",
      Final_Decision: "Approved",
      Approved_Amount: 45000,
      Decision_Date: "2026-10-28",
    });
    renderPage();
    const statusDetail = (await screen.findByText("Claim Status")).closest("div");
    expect(within(statusDetail).getByText("Completed")).toBeInTheDocument();
    expect(screen.getByText("Final Decision").closest("div")).toHaveTextContent("Approved");
    expect(await screen.findByText("Decision recorded: Approved")).toBeInTheDocument();
  });

  it("reflects whatever the backend returns on a fresh load - a later re-fetch is never stale", async () => {
    getClaimById.mockResolvedValueOnce({ ...BASE_CLAIM, Claim_Status: "Under Review", Final_Decision: null });
    const { unmount } = renderPage();
    expect((await screen.findAllByText("Under Review")).length).toBeGreaterThan(0);
    unmount();

    // Simulates a refresh/re-login: a brand-new page instance re-fetches
    // from the backend rather than reusing any earlier in-memory value.
    getClaimById.mockResolvedValueOnce({
      ...BASE_CLAIM,
      Claim_Status: "Completed",
      Final_Decision: "Rejected",
      Decision_Date: "2026-10-28",
    });
    renderPage();
    const statusDetail = (await screen.findByText("Claim Status")).closest("div");
    expect(within(statusDetail).getByText("Completed")).toBeInTheDocument();
    expect(within(statusDetail).queryByText("Under Review")).not.toBeInTheDocument();
  });
});
