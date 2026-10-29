import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Pages that render officer claim-workspace data (Fraud Risk, Estimate
// Analysis) and pages that list/inspect claims (Claim Search, Performance
// Reports, SLA Reports) all go through officerService - mocked once here
// for every page in this file.
vi.mock("../../../services/officerService", () => ({
  getClaimWorkspaceData: vi.fn(),
  listClaimsForProcessing: vi.fn(),
  getClaimProcessingDetail: vi.fn(),
}));
vi.mock("../../../hooks/useAuth", () => ({
  useAuth: () => ({ user: { Username: "officer1", Employee_ID: "EMP-1" } }),
}));

import { getClaimWorkspaceData, listClaimsForProcessing } from "../../../services/officerService";
import EscalationsPage from "../EscalationsPage";
import EstimateAnalysisPage from "../EstimateAnalysisPage";
import FraudRiskPage from "../FraudRiskPage";
import NotificationsPage from "../NotificationsPage";
import PerformanceReportsPage from "../PerformanceReportsPage";
import ProfilePage from "../ProfilePage";
import ClaimSearchPage from "../ClaimSearchPage";
import RfiPage from "../RfiPage";
import SlaReportsPage from "../SlaReportsPage";
import SupportPage from "../SupportPage";

function renderStatic(Page) {
  return render(
    <MemoryRouter>
      <Page />
    </MemoryRouter>
  );
}

function renderClaimPage(Page, path, routePath) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path={routePath} element={<Page />} />
      </Routes>
    </MemoryRouter>
  );
}

async function expectSingleBackButton() {
  expect(await screen.findAllByRole("button", { name: /back/i })).toHaveLength(1);
}

describe("Back button coverage - remaining Claims Officer pages", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("Escalations page shows a single Back button", async () => {
    renderStatic(EscalationsPage);
    await screen.findByText("Escalations");
    await expectSingleBackButton();
  });

  it("RFI / Clarifications page shows a single Back button", async () => {
    renderStatic(RfiPage);
    await screen.findByText("RFI / Clarifications");
    await expectSingleBackButton();
  });

  it("Notifications page shows a single Back button", async () => {
    renderStatic(NotificationsPage);
    await screen.findByText("Notifications");
    await expectSingleBackButton();
  });

  it("Profile Settings page shows a single Back button", async () => {
    renderStatic(ProfilePage);
    await screen.findByText("Profile Settings");
    await expectSingleBackButton();
  });

  it("Help & Support page shows a single Back button", async () => {
    renderStatic(SupportPage);
    await screen.findByText("Help & Support");
    await expectSingleBackButton();
  });

  it("Claim Search page shows a single Back button", async () => {
    listClaimsForProcessing.mockResolvedValue([]);
    renderStatic(ClaimSearchPage);
    await screen.findByText("Claim Search");
    await expectSingleBackButton();
  });

  it("Performance Reports page shows a single Back button", async () => {
    listClaimsForProcessing.mockResolvedValue([]);
    renderStatic(PerformanceReportsPage);
    await screen.findByText(/calculated from the 0 claims/i);
    await expectSingleBackButton();
  });

  it("SLA Reports page shows a single Back button", async () => {
    listClaimsForProcessing.mockResolvedValue([]);
    renderStatic(SlaReportsPage);
    await screen.findByText("No claims available to calculate processing-time statistics.");
    await expectSingleBackButton();
  });

  it("Fraud Risk tab shows a single Back button, with a fallback to this claim's details page", async () => {
    getClaimWorkspaceData.mockResolvedValue({ claim: { Claim_ID: "CLM-9", Claim_Number: "CLM-2026-FRAUD" }, fraud_risk_analysis: [] });
    renderClaimPage(FraudRiskPage, "/officer/claims/CLM-9/fraud-risk", "/officer/claims/:claimId/fraud-risk");
    await screen.findByText(/fraud risk — clm-2026-fraud/i);
    expect(await screen.findAllByRole("button", { name: /back/i })).toHaveLength(1);
  });

  it("Estimate Analysis tab shows a single Back button", async () => {
    getClaimWorkspaceData.mockResolvedValue({ claim: { Claim_ID: "CLM-9", Claim_Number: "CLM-2026-EST" }, repair_estimates: [] });
    renderClaimPage(EstimateAnalysisPage, "/officer/claims/CLM-9/estimate", "/officer/claims/:claimId/estimate");
    await screen.findByText(/estimate analysis — clm-2026-est/i);
    await expectSingleBackButton();
  });
});
