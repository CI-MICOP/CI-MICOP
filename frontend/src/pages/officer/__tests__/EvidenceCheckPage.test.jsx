import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../services/officerService", () => ({
  getClaimWorkspaceData: vi.fn(),
  checkEvidenceDuplication: vi.fn(),
}));

import { checkEvidenceDuplication, getClaimWorkspaceData } from "../../../services/officerService";
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
  });

  it("shows the claim's Evidence Check tab with the photo panel", async () => {
    renderPage();
    expect(await screen.findByText("Evidence Check — CLM-2026-AAAA")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Evidence Check" })).toHaveAttribute("href", "/officer/claims/CLM-1/evidence");
    expect(screen.getByRole("button", { name: /check photos/i })).toBeInTheDocument();
  });

  it("does not run the photo check automatically on page load", async () => {
    renderPage();
    await screen.findByText("Evidence Photo Check");
    expect(checkEvidenceDuplication).not.toHaveBeenCalled();
  });
});
