import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../../services/officerService", () => ({ listClaimsForProcessing: vi.fn() }));

import { listClaimsForProcessing } from "../../../services/officerService";
import AllClaimsPage from "../AllClaimsPage";

// Claim_Status is the real, persisted completion signal (see
// utils/claimWorkflow.js) - a Completed claim has both Claim_Status and
// Final_Decision agree that it is done.
const UNDER_REVIEW = { Claim_ID: "CLM-1", Claim_Number: "CLM-2026-0001", Customer_ID: "CUST-1", Vehicle_ID: "VEH-1", Policy_ID: "POL-1", Claim_Type: "Own Damage", Claim_Amount: 50000, Claim_Date: "2026-10-01", Claim_Status: "Under Review", Final_Decision: "Pending" };
const COMPLETED = { Claim_ID: "CLM-2", Claim_Number: "CLM-2026-0002", Customer_ID: "CUST-2", Vehicle_ID: "VEH-2", Policy_ID: "POL-2", Claim_Type: "Theft", Claim_Amount: 20000, Claim_Date: "2026-10-05", Claim_Status: "Completed", Final_Decision: "Approved" };

function renderPage() {
  return render(
    <MemoryRouter>
      <AllClaimsPage />
    </MemoryRouter>
  );
}

describe("AllClaimsPage", () => {
  it("asks the backend for claims with the persisted Completed status", async () => {
    listClaimsForProcessing.mockResolvedValue([COMPLETED]);
    renderPage();
    await screen.findByText("CLM-2026-0002");
    expect(listClaimsForProcessing).toHaveBeenCalledWith({ limit: 200, claim_status: "Completed" });
  });

  it("shows a completed, approved claim with its Completed status, not Under Review", async () => {
    listClaimsForProcessing.mockResolvedValue([COMPLETED]);
    renderPage();
    expect(await screen.findByText("CLM-2026-0002")).toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(screen.getByText("Approved")).toBeInTheDocument();
    expect(screen.queryByText("Under Review")).not.toBeInTheDocument();
  });

  it("never shows a claim that is still Under Review, even if the backend response is inconsistent", async () => {
    // Defensive client-side filter: even if the server ever returned a
    // mismatched row, this page must not display it - the bug this task
    // fixes was exactly a claim shown as "Under Review" with an Approved
    // decision.
    listClaimsForProcessing.mockResolvedValue([UNDER_REVIEW, COMPLETED]);
    renderPage();
    await screen.findByText("CLM-2026-0002");
    expect(screen.queryByText("CLM-2026-0001")).not.toBeInTheDocument();
  });

  it("shows no duplicate rows for the same claim", async () => {
    listClaimsForProcessing.mockResolvedValue([COMPLETED]);
    renderPage();
    expect(await screen.findAllByText("CLM-2026-0002")).toHaveLength(1);
  });

  it("shows a single Back button below the page header", async () => {
    listClaimsForProcessing.mockResolvedValue([COMPLETED]);
    renderPage();
    await screen.findByText("CLM-2026-0002");
    expect(screen.getAllByRole("button", { name: /back/i })).toHaveLength(1);
  });
});
