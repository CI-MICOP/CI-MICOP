import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../services/officerService", () => ({
  getClaimWorkspaceData: vi.fn(),
  analyzeClaimDocuments: vi.fn(),
  checkClaimConsistency: vi.fn(),
}));

import { analyzeClaimDocuments, checkClaimConsistency, getClaimWorkspaceData } from "../../../services/officerService";
import DocumentConsistencyPage from "../DocumentConsistencyPage";

const CLAIM = { Claim_ID: "CLM-1", Claim_Number: "CLM-2026-AAAA" };

function workspace(overrides = {}) {
  return { claim: CLAIM, cross_document_consistency: [], ...overrides };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/officer/claims/CLM-1/consistency"]}>
      <Routes>
        <Route path="/officer/claims/:claimId/consistency" element={<DocumentConsistencyPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("DocumentConsistencyPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows the live consistency panel even when no recorded dataset row exists", async () => {
    getClaimWorkspaceData.mockResolvedValue(workspace());
    renderPage();

    expect(await screen.findByText("Live Document Consistency")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /check consistency/i })).toBeInTheDocument();
    expect(screen.getByText("No recorded consistency data for this claim")).toBeInTheDocument();
  });

  it("labels the stored row as synthetic dataset values, separate from the live panel", async () => {
    getClaimWorkspaceData.mockResolvedValue(
      workspace({
        cross_document_consistency: [
          {
            FIR_Match: "Matched",
            Overall_Consistency_Status: "Consistent",
            Document_Consistency_Score: "0.9100",
            Document_Mismatch_Indicator: false,
            Accident_Details_Mismatch_Indicator: false,
            Vehicle_Damage_Mismatch_Indicator: false,
          },
        ],
      })
    );
    renderPage();

    expect(await screen.findByText("Recorded Dataset Values")).toBeInTheDocument();
    expect(screen.getByText(/synthetic research dataset - not computed from this claim's uploaded documents/i)).toBeInTheDocument();
    expect(screen.getByText("Field-Level Matches")).toBeInTheDocument();
    expect(screen.getByText("0.9100")).toBeInTheDocument();
  });

  it("does not run any analysis automatically on page load", async () => {
    getClaimWorkspaceData.mockResolvedValue(workspace());
    renderPage();
    await screen.findByText("Live Document Consistency");

    expect(analyzeClaimDocuments).not.toHaveBeenCalled();
    expect(checkClaimConsistency).not.toHaveBeenCalled();
  });
});
