import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../services/claimService", () => ({
  getClaimById: vi.fn(),
}));
vi.mock("../../../services/surveyorService", () => ({
  getAssignedClaimDetail: vi.fn(),
  createEvidence: vi.fn(),
}));

import { getClaimById } from "../../../services/claimService";
import { createEvidence, getAssignedClaimDetail } from "../../../services/surveyorService";
import EvidencePage from "../EvidencePage";

const CLAIM = { Claim_ID: "CLM-1", Claim_Number: "CLM-2026-AAAA" };

const PENDING_EVIDENCE = {
  Evidence_ID: "EVD-1",
  Claim_ID: "CLM-1",
  Evidence_Type: "Damage Photo",
  File_Name: "damage.jpg",
  Evidence_Date: "2026-09-10",
  Evidence_Source: "Surveyor",
  Image_Quality: 0,
  Vehicle_Damage_Detected: false,
  Damage_Severity: "Pending",
  Location_Match: false,
  Duplicate_Evidence_Indicator: false,
  Evidence_Confidence_Score: 0,
  Verification_Status: "Pending",
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/surveyor/claims/CLM-1/evidence"]}>
      <Routes>
        <Route path="/surveyor/claims/:claimId/evidence" element={<EvidencePage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("EvidencePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getClaimById.mockResolvedValue(CLAIM);
  });

  it("loads and displays existing evidence", async () => {
    getAssignedClaimDetail.mockResolvedValue({ evidence: [PENDING_EVIDENCE] });
    renderPage();
    expect(await screen.findByText("damage.jpg")).toBeInTheDocument();
  });

  it("shows the Add Evidence form when the button is clicked", async () => {
    getAssignedClaimDetail.mockResolvedValue({ evidence: [] });
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /add evidence/i }));
    expect(screen.getByRole("button", { name: /upload evidence/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/file \(jpg or png\)/i)).toBeInTheDocument();
  });

  it("valid multipart upload calls the API with the selected file and refreshes the list", async () => {
    getAssignedClaimDetail
      .mockResolvedValueOnce({ evidence: [] })
      .mockResolvedValueOnce({ evidence: [PENDING_EVIDENCE] });
    createEvidence.mockResolvedValueOnce(PENDING_EVIDENCE);
    const file = new File(["\xff\xd8\xff"], "damage.jpg", { type: "image/jpeg" });

    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /add evidence/i }));
    fireEvent.change(screen.getByLabelText(/file \(jpg or png\)/i), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: /upload evidence/i }));

    await waitFor(() =>
      expect(createEvidence).toHaveBeenCalledWith(
        "CLM-1",
        expect.objectContaining({ evidenceSource: "Surveyor", file })
      )
    );
    expect(await screen.findByText(/uploaded successfully/i)).toBeInTheDocument();
    expect(await screen.findByText("damage.jpg")).toBeInTheDocument();
  });

  it("displays the actual API error when upload fails", async () => {
    getAssignedClaimDetail.mockResolvedValue({ evidence: [] });
    createEvidence.mockRejectedValueOnce({ response: { status: 400, data: { detail: "Unsupported file type." } } });
    const file = new File(["x"], "photo.jpg", { type: "image/jpeg" });

    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /add evidence/i }));
    fireEvent.change(screen.getByLabelText(/file \(jpg or png\)/i), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: /upload evidence/i }));

    expect(await screen.findByText(/something went wrong while loading this data\./i)).toBeInTheDocument();
  });

  it("does not present pending AI-analysis fields as completed analysis", async () => {
    getAssignedClaimDetail.mockResolvedValue({ evidence: [PENDING_EVIDENCE] });
    renderPage();

    expect(await screen.findByText(/ai analysis pending/i)).toBeInTheDocument();
    expect(screen.queryByText("Image Quality")).not.toBeInTheDocument();
    expect(screen.queryByText("Confidence Score")).not.toBeInTheDocument();
  });

  it("shows completed analysis fields once verification is no longer pending", async () => {
    getAssignedClaimDetail.mockResolvedValue({
      evidence: [{ ...PENDING_EVIDENCE, Verification_Status: "Verified", Image_Quality: 0.82 }],
    });
    renderPage();

    expect(await screen.findByText("Image Quality")).toBeInTheDocument();
    expect(screen.queryByText(/ai analysis pending/i)).not.toBeInTheDocument();
  });
});
