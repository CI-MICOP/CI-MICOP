import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../services/vehicleService", () => ({
  getMyVehicles: vi.fn(),
}));
vi.mock("../../../services/policyService", () => ({
  getMyPolicies: vi.fn(),
}));
vi.mock("../../../services/claimService", () => ({
  createClaim: vi.fn(),
}));
vi.mock("../../../services/documentService", () => ({
  uploadDocument: vi.fn(),
}));

import { createClaim } from "../../../services/claimService";
import { uploadDocument } from "../../../services/documentService";
import { getMyPolicies } from "../../../services/policyService";
import { getMyVehicles } from "../../../services/vehicleService";
import NewClaimPage from "../NewClaimPage";

const VEHICLE = {
  Vehicle_ID: "VEH-1",
  Make: "Hyundai",
  Model: "i20",
  Registration_Number: "TN01AB0001",
};
const POLICY = {
  Policy_ID: "POL-1",
  Vehicle_ID: "VEH-1",
  Policy_Number: "POLNUM-1",
  Policy_Type: "Comprehensive",
};

function renderPage() {
  return render(
    <MemoryRouter>
      <NewClaimPage />
    </MemoryRouter>
  );
}

async function fillStepOne() {
  fireEvent.change(await screen.findByLabelText(/date of incident/i), { target: { value: "2026-09-01" } });
  fireEvent.change(screen.getByLabelText(/claim type/i), { target: { value: "Own Damage" } });
  fireEvent.change(screen.getByLabelText(/estimated claim amount/i), { target: { value: "45000" } });
  fireEvent.change(screen.getByLabelText(/place of accident/i), { target: { value: "Anna Nagar, Chennai" } });
  fireEvent.change(screen.getByLabelText(/accident pincode/i), { target: { value: "600040" } });
  fireEvent.change(screen.getByLabelText(/description of accident/i), { target: { value: "Minor front collision." } });
  fireEvent.click(screen.getByRole("button", { name: /next/i }));
}

async function fillStepTwo() {
  fireEvent.change(await screen.findByLabelText(/^vehicle/i), { target: { value: "VEH-1" } });
  fireEvent.change(screen.getByLabelText(/^policy/i), { target: { value: "POL-1" } });
  fireEvent.click(screen.getByRole("button", { name: /next/i }));
}

async function reachReviewStep() {
  renderPage();
  await fillStepOne();
  await fillStepTwo();
  // Step 3: Upload Documents - nothing required, go straight to review.
  fireEvent.click(await screen.findByRole("button", { name: /next/i }));
  await screen.findByRole("button", { name: /submit claim/i });
}

async function reachReviewStepWithDocument(categoryLabel, file) {
  renderPage();
  await fillStepOne();
  await fillStepTwo();
  // DocumentUploadGrid's label wraps the file input together with a
  // "Click to select a file" hint, so the accessible name is the whole
  // label text - match on just the category name as a substring.
  const fileInput = await screen.findByLabelText(new RegExp(categoryLabel, "i"));
  fireEvent.change(fileInput, { target: { files: [file] } });
  fireEvent.click(screen.getByRole("button", { name: /next/i }));
  await screen.findByRole("button", { name: /submit claim/i });
}

describe("NewClaimPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getMyVehicles.mockResolvedValue([VEHICLE]);
    getMyPolicies.mockResolvedValue([POLICY]);
  });

  it("no longer shows the old 'not connected to backend' placeholder message", async () => {
    await reachReviewStep();
    fireEvent.click(screen.getByRole("button", { name: /submit claim/i }));
    await waitFor(() => expect(createClaim).toHaveBeenCalled());
    expect(screen.queryByText(/not yet connected to the backend/i)).not.toBeInTheDocument();
  });

  it("successful submission displays the generated Claim_Number and Under Review status", async () => {
    createClaim.mockResolvedValueOnce({
      Claim_ID: "CLM-ABC123",
      Claim_Number: "CLM-2026-DEADBEEF",
      Claim_Status: "Under Review",
      Final_Decision: "Pending",
    });

    await reachReviewStep();
    fireEvent.click(screen.getByRole("button", { name: /submit claim/i }));

    expect(await screen.findByText("CLM-2026-DEADBEEF")).toBeInTheDocument();
    expect(screen.getByText("Under Review")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /view claim/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /back to my claims/i })).toBeInTheDocument();

    expect(createClaim).toHaveBeenCalledTimes(1);
    const submittedPayload = createClaim.mock.calls[0][0];
    expect(submittedPayload.Policy_ID).toBe("POL-1");
    expect(submittedPayload.Vehicle_ID).toBe("VEH-1");
    expect(submittedPayload.Claim_Type).toBe("Own Damage");
  });

  it("failed submission displays an API error and lets the user retry", async () => {
    createClaim.mockRejectedValueOnce({ response: { status: 400 } });

    await reachReviewStep();
    fireEvent.click(screen.getByRole("button", { name: /submit claim/i }));

    expect(await screen.findByText(/does not match the selected policy/i)).toBeInTheDocument();
    // Still on the form (not a fabricated success state).
    expect(screen.getByRole("button", { name: /submit claim/i })).toBeInTheDocument();
  });

  it("prevents duplicate submission while a request is in flight", async () => {
    let resolveCreate;
    createClaim.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveCreate = resolve;
      })
    );

    await reachReviewStep();
    const submitButton = screen.getByRole("button", { name: /submit claim/i });
    fireEvent.click(submitButton);
    fireEvent.click(submitButton);
    fireEvent.click(submitButton);

    expect(createClaim).toHaveBeenCalledTimes(1);

    resolveCreate({ Claim_ID: "CLM-X", Claim_Number: "CLM-2026-X", Claim_Status: "Under Review" });
    await screen.findByText("CLM-2026-X");
  });

  it("uploads the selected document only after the claim has been created", async () => {
    createClaim.mockResolvedValueOnce({
      Claim_ID: "CLM-ABC123",
      Claim_Number: "CLM-2026-DEADBEEF",
      Claim_Status: "Under Review",
    });
    uploadDocument.mockResolvedValueOnce({ Document_ID: "DOC-1" });
    const file = new File(["%PDF-1.4"], "fir.pdf", { type: "application/pdf" });

    await reachReviewStepWithDocument("FIR Copy", file);
    fireEvent.click(screen.getByRole("button", { name: /submit claim/i }));

    await waitFor(() => expect(uploadDocument).toHaveBeenCalledWith("CLM-ABC123", "fir_copy", file));
    expect(createClaim).toHaveBeenCalledTimes(1);
  });

  it("shows a clean success state when the claim and its document both succeed", async () => {
    createClaim.mockResolvedValueOnce({
      Claim_ID: "CLM-1",
      Claim_Number: "CLM-2026-AAAA",
      Claim_Status: "Under Review",
    });
    uploadDocument.mockResolvedValueOnce({ Document_ID: "DOC-1" });
    const file = new File(["%PDF-1.4"], "fir.pdf", { type: "application/pdf" });

    await reachReviewStepWithDocument("FIR Copy", file);
    fireEvent.click(screen.getByRole("button", { name: /submit claim/i }));

    expect(await screen.findByText(/all 1 document uploaded/i)).toBeInTheDocument();
    expect(screen.getByText("Uploaded")).toBeInTheDocument();
    expect(screen.getByText("1 / 1")).toBeInTheDocument();
  });

  it("clearly shows a failed document without ever claiming all documents were uploaded", async () => {
    createClaim.mockResolvedValueOnce({
      Claim_ID: "CLM-1",
      Claim_Number: "CLM-2026-BBBB",
      Claim_Status: "Under Review",
    });
    // DOCUMENT_CATEGORIES order is fir_copy, driving_licence, rc_book, ... -
    // fir_copy uploads first and succeeds, rc_book uploads second and fails.
    uploadDocument.mockResolvedValueOnce({ Document_ID: "DOC-1" });
    uploadDocument.mockRejectedValueOnce({ response: { status: 400, data: { detail: "Unsupported file type." } } });

    renderPage();
    await fillStepOne();
    await fillStepTwo();
    fireEvent.change(await screen.findByLabelText(/FIR Copy/i), {
      target: { files: [new File(["%PDF-1.4"], "fir.pdf", { type: "application/pdf" })] },
    });
    fireEvent.change(screen.getByLabelText(/RC Book/i), {
      target: { files: [new File(["bad"], "rc.exe")] },
    });
    fireEvent.click(screen.getByRole("button", { name: /next/i }));
    await screen.findByRole("button", { name: /submit claim/i });

    fireEvent.click(screen.getByRole("button", { name: /submit claim/i }));

    expect(
      await screen.findByText(/1 of 2 documents uploaded\. 1 document failed and needs retry\./i)
    ).toBeInTheDocument();
    expect(screen.getByText("Unsupported file type.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    expect(screen.queryByText(/all 2 documents uploaded/i)).not.toBeInTheDocument();
  });
});
