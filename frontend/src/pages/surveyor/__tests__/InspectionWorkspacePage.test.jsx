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
  startInspection: vi.fn(),
  openCorrection: vi.fn(),
  closeCorrection: vi.fn(),
}));

import { COMPLETE_INSPECTION, NEW_INSPECTION, schedule, workflow } from "../../../components/surveyor/__tests__/workflowFixture";
import { getClaimById } from "../../../services/claimService";
import { closeCorrection, getAssignedClaimDetail, openCorrection, startInspection, updateInspection } from "../../../services/surveyorService";
import InspectionWorkspacePage from "../InspectionWorkspacePage";

const CLAIM = { Claim_ID: "CLM-1", Claim_Number: "CLM-2026-AAAA", Claim_Type: "Own Damage", Claim_Status: "Under Review" };

const detail = (inspection = NEW_INSPECTION, wf = workflow("new")) => ({
  accidents: [],
  inspections: inspection ? [inspection] : [],
  workflow: inspection ? wf : null,
});

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/surveyor/claims/CLM-1/inspection"]}>
      <Routes>
        <Route path="/surveyor/claims/:claimId/inspection" element={<InspectionWorkspacePage />} />
        <Route path="/surveyor/claims/:claimId/damage" element={<p>Vehicle Damage step</p>} />
      </Routes>
    </MemoryRouter>
  );
}

const next = () => screen.getByRole("button", { name: /next/i });

describe("InspectionWorkspacePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getClaimById.mockResolvedValue(CLAIM);
  });
  afterEach(() => vi.restoreAllMocks());

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

  it("shows Start Inspection when the surveyor has no inspection yet, and starts it", async () => {
    getAssignedClaimDetail
      .mockResolvedValueOnce(detail(null))
      .mockResolvedValueOnce(detail(NEW_INSPECTION));
    startInspection.mockResolvedValueOnce(NEW_INSPECTION);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /start inspection/i }));
    await waitFor(() => expect(startInspection).toHaveBeenCalledWith("CLM-1"));
    expect(await screen.findByRole("button", { name: /save inspection/i })).toBeInTheDocument();
  });

  // ---------------------------------------------------------------- schedule

  it("before the scheduled date: shows the schedule, disables the form and Next", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail(NEW_INSPECTION, workflow("new", { schedule: schedule({ reached: false }) })));
    renderPage();
    expect(await screen.findByRole("heading", { name: "Inspection not open yet" })).toBeInTheDocument();
    expect(screen.getAllByText(/will become available on 28 October 2026/i).length).toBeGreaterThan(0);
    expect(screen.getByLabelText(/vehicle condition/i)).toBeDisabled();
    expect(screen.queryByRole("button", { name: /save inspection/i })).not.toBeInTheDocument();
    expect(next()).toBeDisabled();
    expect(updateInspection).not.toHaveBeenCalled();
  });

  // ---------------------------------------------------------------- the form

  it("loads existing inspection values and keeps date and location read-only", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail({ ...NEW_INSPECTION, Vehicle_Condition: "Good", Parts_Required: 3 }));
    renderPage();
    expect(await screen.findByDisplayValue("Good")).toBeInTheDocument();
    expect(screen.getByDisplayValue("3")).toBeInTheDocument();
    expect(screen.getByText("Chennai")).toBeInTheDocument();
    expect(screen.queryByDisplayValue("Chennai")).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/inspection status/i)).not.toBeInTheDocument(); // server-managed
  });

  it("disables Next while required fields are missing and names them", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail());
    renderPage();
    await screen.findByRole("heading", { name: "Inspection Details" });
    expect(next()).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent(/vehicle condition, damage observed, repair recommendation/i);
  });

  it("requires Damage Severity once damage is observed", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail({ ...NEW_INSPECTION, Vehicle_Condition: "Fair", Repair_Recommendation: "Repair", Damage_Observed: "Yes" }));
    renderPage();
    await screen.findByRole("heading", { name: "Inspection Details" });
    expect(next()).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent(/damage severity/i);
    fireEvent.change(screen.getByLabelText(/damage severity/i), { target: { value: "Minor" } });
    expect(next()).toBeEnabled();
  });

  it("rejects invalid values: a non-whole parts count and an invalid stored option", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail({ ...COMPLETE_INSPECTION, Vehicle_Condition: "Damaged" }));
    renderPage();
    expect(await screen.findByRole("option", { name: "Damaged (not a valid option)" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/parts required/i), { target: { value: "2.5" } });
    fireEvent.click(screen.getByRole("button", { name: /save inspection/i }));
    expect(await screen.findByText(/"Damaged" is not a valid vehicle condition/i)).toBeInTheDocument();
    expect(screen.getByText(/whole number/i)).toBeInTheDocument();
    expect(updateInspection).not.toHaveBeenCalled();
    expect(next()).toBeDisabled();
  });

  it("Save Inspection sends the editable fields only - never date, location or status", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail());
    updateInspection.mockResolvedValueOnce({ ...NEW_INSPECTION, Vehicle_Condition: "Good" });
    renderPage();
    fireEvent.change(await screen.findByLabelText(/vehicle condition/i), { target: { value: "Good" } });
    fireEvent.click(screen.getByRole("button", { name: /save inspection/i }));
    await waitFor(() => expect(updateInspection).toHaveBeenCalled());
    const [id, payload] = updateInspection.mock.calls[0];
    expect(id).toBe("INSP-1");
    expect(payload).toMatchObject({ Vehicle_Condition: "Good", Parts_Required: 0 });
    for (const protectedField of ["Inspection_Date", "Inspection_Location", "Inspection_Status", "Survey_Report_Submitted"]) {
      expect(payload).not.toHaveProperty(protectedField);
    }
    expect(await screen.findByText(/updated successfully/i)).toBeInTheDocument();
  });

  it("saves valid input once when Next is clicked, then continues to Vehicle Damage", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail({ ...COMPLETE_INSPECTION, Repair_Recommendation: "Pending", Inspection_Status: "In Progress" }));
    let finishSave;
    updateInspection.mockReturnValueOnce(new Promise((resolve) => (finishSave = resolve)));
    renderPage();
    fireEvent.change(await screen.findByLabelText(/repair recommendation/i), { target: { value: "Replace" } });

    fireEvent.click(next());
    fireEvent.click(next()); // repeated click while saving
    await waitFor(() => expect(updateInspection).toHaveBeenCalledTimes(1));
    expect(updateInspection).toHaveBeenCalledWith("INSP-1", expect.objectContaining({ Repair_Recommendation: "Replace" }));
    finishSave({ ...COMPLETE_INSPECTION, Repair_Recommendation: "Replace" });
    expect(await screen.findByText("Vehicle Damage step")).toBeInTheDocument();
  });

  it("stays on Inspection with the input kept and the server's reason when the save fails", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail({ ...COMPLETE_INSPECTION, Repair_Recommendation: "Pending" }));
    updateInspection.mockRejectedValueOnce({ response: { status: 409, data: { detail: "This inspection is will become available on 28 October 2026." } } });
    renderPage();
    fireEvent.change(await screen.findByLabelText(/repair recommendation/i), { target: { value: "Replace" } });
    fireEvent.click(next());

    expect(await screen.findByText(/could not be saved, so you cannot continue/i)).toBeInTheDocument();
    expect(screen.getAllByText(/will become available on 28 October 2026/i).length).toBeGreaterThan(0);
    expect(screen.queryByText("Vehicle Damage step")).not.toBeInTheDocument();
    expect(screen.getByLabelText(/repair recommendation/i)).toHaveValue("Replace");
  });

  // ---------------------------------------------------------------- completed, correction, submitted

  it("shows a completed step read-only and moves on without saving again", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail(COMPLETE_INSPECTION, workflow("inspection")));
    renderPage();
    expect(await screen.findByText(/inspection details are complete and saved/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/vehicle condition/i)).toBeDisabled();
    expect(screen.queryByRole("button", { name: /save inspection/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^edit/i })).not.toBeInTheDocument();
    fireEvent.click(next());
    expect(await screen.findByText("Vehicle Damage step")).toBeInTheDocument();
    expect(updateInspection).not.toHaveBeenCalled();
  });

  it("reopens a completed step only through a correction the server records", async () => {
    const locked = workflow("damage", { locked_steps: { inspection: true, damage: false }, open_corrections: { inspection: false, damage: false } });
    const correcting = { ...locked, open_corrections: { inspection: true, damage: false } };
    getAssignedClaimDetail
      .mockResolvedValueOnce(detail(COMPLETE_INSPECTION, locked))
      .mockResolvedValueOnce(detail(COMPLETE_INSPECTION, correcting))
      .mockResolvedValue(detail({ ...COMPLETE_INSPECTION, Damage_Severity: "Severe" }, locked));
    openCorrection.mockResolvedValueOnce(correcting);
    updateInspection.mockResolvedValueOnce({ ...COMPLETE_INSPECTION, Damage_Severity: "Severe" });
    const confirm = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValue(true);
    renderPage();
    const correct = await screen.findByRole("button", { name: /correct this step/i });

    fireEvent.click(correct);
    expect(confirm).toHaveBeenCalledWith(expect.stringMatching(/later steps will be checked again/i));
    expect(openCorrection).not.toHaveBeenCalled(); // cancelled
    expect(screen.getByLabelText(/damage severity/i)).toBeDisabled();

    fireEvent.click(correct);
    await waitFor(() => expect(openCorrection).toHaveBeenCalledWith("INSP-1", "inspection"));
    // Editable only once the server reports the correction as open.
    await waitFor(() => expect(screen.getByLabelText(/damage severity/i)).toBeEnabled());
    fireEvent.change(screen.getByLabelText(/damage severity/i), { target: { value: "Severe" } });
    fireEvent.click(screen.getByRole("button", { name: /save inspection/i }));
    await waitFor(() => expect(updateInspection).toHaveBeenCalledWith("INSP-1", expect.objectContaining({ Damage_Severity: "Severe" })));
    // The server ended the correction with the save: read-only again.
    await waitFor(() => expect(screen.getByLabelText(/damage severity/i)).toBeDisabled());
  });

  it("shows the server's refusal when a correction cannot be opened", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail(COMPLETE_INSPECTION, workflow("damage")));
    openCorrection.mockRejectedValueOnce({ response: { status: 409, data: { detail: "This survey report has already been submitted." } } });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /correct this step/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("This survey report has already been submitted.");
    expect(screen.getByLabelText(/damage severity/i)).toBeDisabled();
  });

  it("closes an open correction on request without saving", async () => {
    const correcting = workflow("damage", { open_corrections: { inspection: true, damage: false } });
    getAssignedClaimDetail.mockResolvedValueOnce(detail(COMPLETE_INSPECTION, correcting)).mockResolvedValue(detail(COMPLETE_INSPECTION, workflow("damage")));
    closeCorrection.mockResolvedValueOnce({});
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /done correcting/i }));
    await waitFor(() => expect(closeCorrection).toHaveBeenCalledWith("INSP-1", "inspection"));
    expect(updateInspection).not.toHaveBeenCalled();
  });

  it("is read-only once the survey report has been submitted", async () => {
    getAssignedClaimDetail.mockResolvedValue(
      detail({ ...COMPLETE_INSPECTION, Vehicle_Condition: "Damaged", Survey_Report_Submitted: true, Inspection_Status: "Completed" }, workflow("submitted"))
    );
    renderPage();
    expect(await screen.findByText(/can no longer be changed/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/vehicle condition/i)).toBeDisabled();
    expect(screen.queryByRole("button", { name: /save inspection/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /correct this step/i })).not.toBeInTheDocument();
    fireEvent.click(next());
    expect(await screen.findByText("Vehicle Damage step")).toBeInTheDocument();
  });
});
