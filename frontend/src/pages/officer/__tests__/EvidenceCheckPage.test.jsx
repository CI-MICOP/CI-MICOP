import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../services/officerService", () => ({
  getClaimWorkspaceData: vi.fn(),
  checkEvidenceDuplication: vi.fn(),
  checkPhotoQuality: vi.fn(),
  getClaimEvidenceLocations: vi.fn(),
}));

import {
  checkEvidenceDuplication,
  checkPhotoQuality,
  getClaimEvidenceLocations,
  getClaimWorkspaceData,
} from "../../../services/officerService";
import EvidenceCheckPage from "../EvidenceCheckPage";

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/officer/claims/CLM-1/evidence"]}>
      <Routes>
        <Route path="/officer/claims/:claimId/evidence" element={<EvidenceCheckPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("EvidenceCheckPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getClaimWorkspaceData.mockResolvedValue({ claim: { Claim_ID: "CLM-1", Claim_Number: "CLM-2026-AAAA" } });
    getClaimEvidenceLocations.mockResolvedValue({ Claim_ID: "CLM-1", evidence: [] });
  });

  it("shows the claim's Evidence Check tab with the photo panel", async () => {
    renderPage();
    expect(await screen.findByText("Evidence Check — CLM-2026-AAAA")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Evidence Check" })).toHaveAttribute("href", "/officer/claims/CLM-1/evidence");
    expect(screen.getByRole("button", { name: /check photos/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /check quality/i })).toBeInTheDocument();
  });

  it("shows the Evidence Location panel so the officer can see GPS vs map-selected sources", async () => {
    renderPage();
    expect(await screen.findByText("Evidence Location")).toBeInTheDocument();
    expect(getClaimEvidenceLocations).toHaveBeenCalledWith("CLM-1");
  });

  it("does not run either photo check automatically on page load", async () => {
    renderPage();
    await screen.findByText("Evidence Photo Check");
    expect(screen.getByText("Photo Quality")).toBeInTheDocument();
    expect(checkEvidenceDuplication).not.toHaveBeenCalled();
    expect(checkPhotoQuality).not.toHaveBeenCalled();
  });

  it("shows a single Back button below the breadcrumb/tabs", async () => {
    renderPage();
    await screen.findByText("Evidence Photo Check");
    expect(screen.getAllByRole("button", { name: /back/i })).toHaveLength(1);
  });
});
