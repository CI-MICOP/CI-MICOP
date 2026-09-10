import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../services/claimService", () => ({
  getClaimById: vi.fn(),
}));
vi.mock("../../../services/surveyorService", () => ({
  getAssignedClaimDetail: vi.fn(),
  createVehicleDamage: vi.fn(),
}));

import { getClaimById } from "../../../services/claimService";
import { createVehicleDamage, getAssignedClaimDetail } from "../../../services/surveyorService";
import VehicleDamagePage from "../VehicleDamagePage";

const CLAIM = { Claim_ID: "CLM-1", Claim_Number: "CLM-2026-AAAA" };

const DAMAGE_1 = {
  Damage_ID: "DMG-1",
  Claim_ID: "CLM-1",
  Vehicle_ID: "VEH-1",
  Damage_Type: "Front Damage",
  Damaged_Part: "Bumper",
  Damage_Severity: "Minor",
  Damage_Location: "Front",
  Estimated_Damage_Cost: 15000,
  Repair_or_Replace: "Repair",
  Photo_Evidence_Available: true,
  Vehicle_Damage_Mismatch_Indicator: false,
  Damage_Description: "Cracked bumper.",
};

const DAMAGE_2 = { ...DAMAGE_1, Damage_ID: "DMG-2", Damaged_Part: "Headlight", Damage_Location: "Left" };

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/surveyor/claims/CLM-1/damage"]}>
      <Routes>
        <Route path="/surveyor/claims/:claimId/damage" element={<VehicleDamagePage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("VehicleDamagePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getClaimById.mockResolvedValue(CLAIM);
  });

  it("loads and displays existing damage records", async () => {
    getAssignedClaimDetail.mockResolvedValue({ vehicle_damage: [DAMAGE_1] });
    renderPage();
    expect(await screen.findByText("Bumper")).toBeInTheDocument();
    expect(screen.getByText("Cracked bumper.")).toBeInTheDocument();
  });

  it("renders multiple damage records", async () => {
    getAssignedClaimDetail.mockResolvedValue({ vehicle_damage: [DAMAGE_1, DAMAGE_2] });
    renderPage();
    expect(await screen.findByText("Bumper")).toBeInTheDocument();
    expect(screen.getByText("Headlight")).toBeInTheDocument();
  });

  it("shows the Add Damage form when the button is clicked", async () => {
    getAssignedClaimDetail.mockResolvedValue({ vehicle_damage: [] });
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /add damage/i }));
    expect(screen.getByRole("button", { name: /save damage record/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/damaged part/i)).toBeInTheDocument();
  });

  it("does not allow submission until required fields are filled (validation)", async () => {
    getAssignedClaimDetail.mockResolvedValue({ vehicle_damage: [] });
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /add damage/i }));
    expect(screen.getByRole("button", { name: /save damage record/i })).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/damaged part/i), { target: { value: "Bumper" } });
    fireEvent.change(screen.getByLabelText(/estimated damage cost/i), { target: { value: "15000" } });
    fireEvent.change(screen.getByLabelText(/damage description/i), { target: { value: "Front bumper cracked." } });

    expect(screen.getByRole("button", { name: /save damage record/i })).not.toBeDisabled();
  });

  it("valid submission calls POST via createVehicleDamage() and refreshes the list", async () => {
    getAssignedClaimDetail
      .mockResolvedValueOnce({ vehicle_damage: [] })
      .mockResolvedValueOnce({ vehicle_damage: [DAMAGE_1] });
    createVehicleDamage.mockResolvedValueOnce(DAMAGE_1);

    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /add damage/i }));
    fireEvent.change(screen.getByLabelText(/damaged part/i), { target: { value: "Bumper" } });
    fireEvent.change(screen.getByLabelText(/estimated damage cost/i), { target: { value: "15000" } });
    fireEvent.change(screen.getByLabelText(/damage description/i), { target: { value: "Cracked bumper." } });
    fireEvent.click(screen.getByRole("button", { name: /save damage record/i }));

    await waitFor(() =>
      expect(createVehicleDamage).toHaveBeenCalledWith(
        expect.objectContaining({ Claim_ID: "CLM-1", Damaged_Part: "Bumper", Damage_Description: "Cracked bumper." })
      )
    );
    expect(await screen.findByText(/damage record saved/i)).toBeInTheDocument();
    expect(await screen.findByText("Bumper")).toBeInTheDocument();
  });

  it("displays the actual API error when submission fails", async () => {
    getAssignedClaimDetail.mockResolvedValue({ vehicle_damage: [] });
    createVehicleDamage.mockRejectedValueOnce({ response: { status: 403 } });

    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /add damage/i }));
    fireEvent.change(screen.getByLabelText(/damaged part/i), { target: { value: "Bumper" } });
    fireEvent.change(screen.getByLabelText(/estimated damage cost/i), { target: { value: "15000" } });
    fireEvent.change(screen.getByLabelText(/damage description/i), { target: { value: "Cracked bumper." } });
    fireEvent.click(screen.getByRole("button", { name: /save damage record/i }));

    expect(await screen.findByText(/don't have access/i)).toBeInTheDocument();
  });
});
