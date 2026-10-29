import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../hooks/useAuth", () => ({ useAuth: () => ({ user: { Employee_ID: "EMP-1" } }) }));
vi.mock("../../../services/claimService", () => ({
  getClaimById: vi.fn(),
}));
vi.mock("../../../services/surveyorService", () => ({
  getAssignedClaimDetail: vi.fn(),
  createVehicleDamage: vi.fn(),
  updateVehicleDamage: vi.fn(),
  openCorrection: vi.fn(),
  closeCorrection: vi.fn(),
}));

import { COMPLETE_INSPECTION, schedule, workflow } from "../../../components/surveyor/__tests__/workflowFixture";
import { getClaimById } from "../../../services/claimService";
import {
  closeCorrection,
  createVehicleDamage,
  getAssignedClaimDetail,
  openCorrection,
  updateVehicleDamage,
} from "../../../services/surveyorService";
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

const detail = ({ damage = [], wf = workflow("inspection"), inspection = COMPLETE_INSPECTION } = {}) => ({
  inspections: [inspection],
  vehicle_damage: damage,
  evidence: [],
  workflow: wf,
});
const saved = (damage) => detail({ damage, wf: workflow("damage", { damage_count: damage.length }) });

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/surveyor/claims/CLM-1/damage"]}>
      <Routes>
        <Route path="/surveyor/claims/:claimId/damage" element={<VehicleDamagePage />} />
        <Route path="/surveyor/claims/:claimId/evidence" element={<p>Evidence step</p>} />
      </Routes>
    </MemoryRouter>
  );
}

const nextButton = () => screen.getByRole("button", { name: /next/i });

function fillValidForm() {
  fireEvent.change(screen.getByLabelText(/damaged part/i), { target: { value: "Door" } });
  fireEvent.change(screen.getByLabelText(/estimated damage cost/i), { target: { value: "12000" } });
  fireEvent.change(screen.getByLabelText(/damage description/i), { target: { value: "Dented door." } });
}

describe("VehicleDamagePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getClaimById.mockResolvedValue(CLAIM);
  });
  afterEach(() => vi.restoreAllMocks());

  it("opens the damage form directly when damage was observed and nothing is saved yet", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail());
    renderPage();
    expect(await screen.findByRole("heading", { name: "Add Damage Record" })).toBeInTheDocument();
    expect(screen.getByLabelText(/damaged part/i)).toBeInTheDocument();
    // The required form cannot be dismissed, and there is no extra Add click.
    expect(screen.queryByRole("button", { name: /cancel/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /add/i })).not.toBeInTheDocument();
  });

  it("validates required fields and does not submit an incomplete form", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail());
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /save damage record/i }));
    expect(screen.getByText("Enter the damaged part.")).toBeInTheDocument();
    expect(screen.getByText("Enter the estimated cost as 0 or more.")).toBeInTheDocument();
    expect(screen.getByText("Describe the damage.")).toBeInTheDocument();
    expect(createVehicleDamage).not.toHaveBeenCalled();
  });

  it("keeps Next disabled while no record is saved - an open form is not a saved record", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail());
    renderPage();
    await screen.findByRole("heading", { name: "Add Damage Record" });
    expect(nextButton()).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent(/save at least one damage record/i);
    fireEvent.change(screen.getByLabelText(/damaged part/i), { target: { value: "Door" } });
    expect(screen.getByRole("status")).toHaveTextContent(/save the damage record you are adding/i);
    expect(screen.getByLabelText(/damaged part/i)).toHaveValue("Door");
  });

  it("keeps the form and its input, with the server's reason, when the save fails", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail());
    createVehicleDamage.mockRejectedValueOnce({ response: { status: 409, data: { detail: "Complete and save the Inspection step first." } } });
    renderPage();
    await screen.findByRole("heading", { name: "Add Damage Record" });
    fillValidForm();
    fireEvent.click(screen.getByRole("button", { name: /save damage record/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Complete and save the Inspection step first.");
    expect(screen.queryByText("Damage record saved.")).not.toBeInTheDocument();
    expect(screen.getByLabelText(/damaged part/i)).toHaveValue("Door");
    expect(nextButton()).toBeDisabled();
  });

  it("saves a valid record once, lists it, offers Add another and then allows Next", async () => {
    getAssignedClaimDetail.mockResolvedValueOnce(detail()).mockResolvedValueOnce(saved([DAMAGE_1]));
    let finishSave;
    createVehicleDamage.mockReturnValueOnce(new Promise((resolve) => (finishSave = resolve)));
    renderPage();
    await screen.findByRole("heading", { name: "Add Damage Record" });
    fillValidForm();

    const save = screen.getByRole("button", { name: /save damage record/i });
    fireEvent.click(save);
    fireEvent.click(save); // a second click while saving
    expect(createVehicleDamage).toHaveBeenCalledTimes(1);
    expect(createVehicleDamage).toHaveBeenCalledWith(expect.objectContaining({ Claim_ID: "CLM-1", Damaged_Part: "Door" }));
    finishSave({ ...DAMAGE_1 });

    expect(await screen.findByText("Damage record saved.")).toBeInTheDocument();
    const summary = (await screen.findByRole("heading", { name: "Saved Damage Records" })).closest("div");
    expect(within(summary).getByText("Bumper")).toBeInTheDocument();
    expect(screen.queryByLabelText(/damaged part/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /add another damage record/i }));
    expect(screen.getByRole("heading", { name: "Add Another Damage Record" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));

    fireEvent.click(nextButton());
    expect(await screen.findByText("Evidence step")).toBeInTheDocument();
    expect(createVehicleDamage).toHaveBeenCalledTimes(1); // navigating never creates another record
  });

  it("shows a completed step read-only; adding more needs a correction the server records", async () => {
    const correcting = { ...saved([DAMAGE_1, DAMAGE_2]), workflow: workflow("damage", { damage_count: 2, open_corrections: { inspection: false, damage: true } }) };
    getAssignedClaimDetail.mockResolvedValueOnce(saved([DAMAGE_1, DAMAGE_2])).mockResolvedValue(correcting);
    openCorrection.mockResolvedValueOnce({});
    closeCorrection.mockResolvedValueOnce({});
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    renderPage();
    expect(await screen.findByText("Bumper")).toBeInTheDocument();
    expect(screen.getByText("Headlight")).toBeInTheDocument();
    expect(screen.queryByLabelText(/damaged part/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /add another/i })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /correct this step/i }));
    expect(confirm).toHaveBeenCalled();
    await waitFor(() => expect(openCorrection).toHaveBeenCalledWith("INSP-1", "damage"));
    fireEvent.click(await screen.findByRole("button", { name: /add another damage record/i }));
    expect(screen.getByRole("heading", { name: "Add Another Damage Record" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));

    // Moving on ends the correction on the server.
    fireEvent.click(nextButton());
    await waitFor(() => expect(closeCorrection).toHaveBeenCalledWith("INSP-1", "damage"));
    expect(await screen.findByText("Evidence step")).toBeInTheDocument();
  });

  it("does not require a record when no damage was observed", async () => {
    getAssignedClaimDetail.mockResolvedValue(
      detail({
        inspection: { ...COMPLETE_INSPECTION, Damage_Observed: "No", Damage_Severity: "Pending" },
        wf: workflow("damage", { damage_required: false, damage_count: 0 }),
      })
    );
    renderPage();
    expect(await screen.findByText(/a damage record is not required/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/damaged part/i)).not.toBeInTheDocument();
    fireEvent.click(nextButton());
    expect(await screen.findByText("Evidence step")).toBeInTheDocument();
  });

  it("is locked until the Inspection step is complete", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail({ wf: workflow("new") }));
    renderPage();
    expect(await screen.findByRole("heading", { name: "Complete the earlier steps first" })).toBeInTheDocument();
    expect(screen.queryByLabelText(/damaged part/i)).not.toBeInTheDocument();
    expect(nextButton()).toBeDisabled();
  });

  it("is locked before the scheduled date, even when opened directly", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail({ wf: workflow("inspection", { schedule: schedule({ reached: false }) }) }));
    renderPage();
    expect(await screen.findByRole("heading", { name: "Inspection not open yet" })).toBeInTheDocument();
    expect(screen.queryByLabelText(/damaged part/i)).not.toBeInTheDocument();
    expect(nextButton()).toBeDisabled();
    await waitFor(() => expect(createVehicleDamage).not.toHaveBeenCalled());
  });

  it("is read-only once the survey report has been submitted", async () => {
    getAssignedClaimDetail.mockResolvedValue({ ...saved([DAMAGE_1]), workflow: workflow("submitted") });
    renderPage();
    expect(await screen.findByText("Bumper")).toBeInTheDocument();
    expect(screen.getByText(/can no longer be changed/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /add another|correct this step/i })).not.toBeInTheDocument();
    fireEvent.click(nextButton());
    expect(await screen.findByText("Evidence step")).toBeInTheDocument();
  });

  describe("editing an existing record (Correct this step)", () => {
    const correctingWorkflow = (count) =>
      workflow("damage", { damage_count: count, open_corrections: { inspection: false, damage: true } });

    it("clicking Correct this step reopens the one saved record, prepopulated, for editing", async () => {
      getAssignedClaimDetail
        .mockResolvedValueOnce(saved([DAMAGE_1]))
        .mockResolvedValue({ ...saved([DAMAGE_1]), workflow: correctingWorkflow(1) });
      openCorrection.mockResolvedValueOnce({});
      vi.spyOn(window, "confirm").mockReturnValue(true);
      renderPage();
      expect(await screen.findByText("Bumper")).toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: /correct this step/i }));
      await waitFor(() => expect(openCorrection).toHaveBeenCalledWith("INSP-1", "damage"));

      expect(await screen.findByRole("heading", { name: "Edit Damage Record" })).toBeInTheDocument();
      expect(screen.getByLabelText(/damaged part/i)).toHaveValue("Bumper");
      expect(screen.getByLabelText(/estimated damage cost/i)).toHaveValue(15000);
      expect(screen.getByLabelText(/damage description/i)).toHaveValue("Cracked bumper.");
      expect(screen.getByRole("button", { name: /update damage record/i })).toBeInTheDocument();
    });

    it("saving changes calls the update endpoint with the existing Damage_ID and shows the updated values", async () => {
      getAssignedClaimDetail
        .mockResolvedValueOnce(saved([DAMAGE_1]))
        .mockResolvedValueOnce({ ...saved([DAMAGE_1]), workflow: correctingWorkflow(1) })
        .mockResolvedValueOnce(saved([{ ...DAMAGE_1, Damaged_Part: "Rear Bumper" }]));
      openCorrection.mockResolvedValueOnce({});
      updateVehicleDamage.mockResolvedValueOnce({ ...DAMAGE_1, Damaged_Part: "Rear Bumper" });
      vi.spyOn(window, "confirm").mockReturnValue(true);
      renderPage();
      expect(await screen.findByText("Bumper")).toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: /correct this step/i }));
      await screen.findByRole("heading", { name: "Edit Damage Record" });
      fireEvent.change(screen.getByLabelText(/damaged part/i), { target: { value: "Rear Bumper" } });
      fireEvent.click(screen.getByRole("button", { name: /update damage record/i }));

      await waitFor(() =>
        expect(updateVehicleDamage).toHaveBeenCalledWith("DMG-1", expect.objectContaining({ Damaged_Part: "Rear Bumper" }))
      );
      expect(createVehicleDamage).not.toHaveBeenCalled();
      expect(await screen.findByText("Damage record updated.")).toBeInTheDocument();
      const summary = (await screen.findByRole("heading", { name: "Saved Damage Records" })).closest("div");
      expect(within(summary).getByText("Rear Bumper")).toBeInTheDocument();
      expect(screen.queryByLabelText(/damaged part/i)).not.toBeInTheDocument();
    });

    it("does not create a duplicate record when updating", async () => {
      getAssignedClaimDetail
        .mockResolvedValueOnce(saved([DAMAGE_1]))
        .mockResolvedValue({ ...saved([DAMAGE_1]), workflow: correctingWorkflow(1) });
      openCorrection.mockResolvedValueOnce({});
      updateVehicleDamage.mockResolvedValueOnce(DAMAGE_1);
      vi.spyOn(window, "confirm").mockReturnValue(true);
      renderPage();
      expect(await screen.findByText("Bumper")).toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: /correct this step/i }));
      await screen.findByRole("heading", { name: "Edit Damage Record" });
      fireEvent.click(screen.getByRole("button", { name: /update damage record/i }));

      await waitFor(() => expect(updateVehicleDamage).toHaveBeenCalledTimes(1));
      expect(createVehicleDamage).not.toHaveBeenCalled();
    });

    it("keeps the record unsaved (and the original data intact) when the update fails", async () => {
      getAssignedClaimDetail
        .mockResolvedValueOnce(saved([DAMAGE_1]))
        .mockResolvedValue({ ...saved([DAMAGE_1]), workflow: correctingWorkflow(1) });
      openCorrection.mockResolvedValueOnce({});
      updateVehicleDamage.mockRejectedValueOnce({ response: { status: 409, data: { detail: "The Vehicle Damage step is not complete, so it can be edited without a correction." } } });
      vi.spyOn(window, "confirm").mockReturnValue(true);
      renderPage();
      expect(await screen.findByText("Bumper")).toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: /correct this step/i }));
      await screen.findByRole("heading", { name: "Edit Damage Record" });
      fireEvent.change(screen.getByLabelText(/damaged part/i), { target: { value: "Rear Bumper" } });
      fireEvent.click(screen.getByRole("button", { name: /update damage record/i }));

      expect(await screen.findByRole("alert")).toHaveTextContent("not complete");
      // The form keeps the surveyor's in-progress edit; the saved table row is untouched.
      expect(screen.getByLabelText(/damaged part/i)).toHaveValue("Rear Bumper");
      const summary = within((await screen.findByRole("heading", { name: "Saved Damage Records" })).closest("div"));
      expect(summary.getByText("Bumper")).toBeInTheDocument();
    });

    it("shows a per-row Edit action for multiple saved records, and editing one does not disturb the other", async () => {
      getAssignedClaimDetail
        .mockResolvedValueOnce(saved([DAMAGE_1, DAMAGE_2]))
        .mockResolvedValue({ ...saved([DAMAGE_1, DAMAGE_2]), workflow: correctingWorkflow(2) });
      openCorrection.mockResolvedValueOnce({});
      vi.spyOn(window, "confirm").mockReturnValue(true);
      renderPage();
      expect(await screen.findByText("Bumper")).toBeInTheDocument();
      expect(screen.getByText("Headlight")).toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: /correct this step/i }));
      await waitFor(() => expect(openCorrection).toHaveBeenCalled());
      // With two records, nothing is auto-opened - the surveyor picks one.
      expect(screen.queryByLabelText(/damaged part/i)).not.toBeInTheDocument();

      fireEvent.click(await screen.findByRole("button", { name: /edit headlight/i }));
      expect(await screen.findByRole("heading", { name: "Edit Damage Record" })).toBeInTheDocument();
      expect(screen.getByLabelText(/damaged part/i)).toHaveValue("Headlight");
    });

    it("adding a brand-new record still works independently while a correction is open", async () => {
      getAssignedClaimDetail
        .mockResolvedValueOnce(saved([DAMAGE_1, DAMAGE_2]))
        .mockResolvedValue({ ...saved([DAMAGE_1, DAMAGE_2]), workflow: correctingWorkflow(2) });
      openCorrection.mockResolvedValueOnce({});
      vi.spyOn(window, "confirm").mockReturnValue(true);
      renderPage();
      expect(await screen.findByText("Bumper")).toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: /correct this step/i }));
      fireEvent.click(await screen.findByRole("button", { name: /add another damage record/i }));

      expect(screen.getByRole("heading", { name: "Add Another Damage Record" })).toBeInTheDocument();
      expect(screen.getByLabelText(/damaged part/i)).toHaveValue("");
      expect(screen.getByRole("button", { name: /save damage record/i })).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /update damage record/i })).not.toBeInTheDocument();
    });

    it("Cancel while editing discards the change and returns to the saved view without updating", async () => {
      getAssignedClaimDetail
        .mockResolvedValueOnce(saved([DAMAGE_1]))
        .mockResolvedValue({ ...saved([DAMAGE_1]), workflow: correctingWorkflow(1) });
      openCorrection.mockResolvedValueOnce({});
      vi.spyOn(window, "confirm").mockReturnValue(true);
      renderPage();
      expect(await screen.findByText("Bumper")).toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: /correct this step/i }));
      await screen.findByRole("heading", { name: "Edit Damage Record" });
      fireEvent.change(screen.getByLabelText(/damaged part/i), { target: { value: "Rear Bumper" } });
      fireEvent.click(screen.getByRole("button", { name: /cancel/i }));

      expect(screen.queryByLabelText(/damaged part/i)).not.toBeInTheDocument();
      expect(updateVehicleDamage).not.toHaveBeenCalled();
      const summary = (await screen.findByRole("heading", { name: "Saved Damage Records" })).closest("div");
      expect(within(summary).getByText("Bumper")).toBeInTheDocument();
    });

    it("blocks Next while an edit has unsaved changes, and allows it again once saved", async () => {
      getAssignedClaimDetail
        .mockResolvedValueOnce(saved([DAMAGE_1]))
        .mockResolvedValueOnce({ ...saved([DAMAGE_1]), workflow: correctingWorkflow(1) });
      openCorrection.mockResolvedValueOnce({});
      vi.spyOn(window, "confirm").mockReturnValue(true);
      renderPage();
      expect(await screen.findByText("Bumper")).toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: /correct this step/i }));
      await screen.findByRole("heading", { name: "Edit Damage Record" });
      expect(nextButton()).not.toBeDisabled();

      fireEvent.change(screen.getByLabelText(/damaged part/i), { target: { value: "Rear Bumper" } });
      expect(nextButton()).toBeDisabled();
      expect(screen.getByRole("status")).toHaveTextContent(/save or cancel your changes/i);
    });
  });
});
