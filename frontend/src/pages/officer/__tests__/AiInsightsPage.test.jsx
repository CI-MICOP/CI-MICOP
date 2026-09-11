import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../services/officerService", () => ({
  getClaimWorkspaceData: vi.fn(),
  getAiAnalysis: vi.fn(),
  runAiAnalysis: vi.fn(),
}));

import { getAiAnalysis, getClaimWorkspaceData } from "../../../services/officerService";
import AiInsightsPage from "../AiInsightsPage";

const CLAIM = {
  Claim_ID: "CLM-1",
  Claim_Number: "CLM-2026-AAAA",
};

function baseWorkspace(overrides = {}) {
  return { claim: CLAIM, ...overrides };
}

function unavailableAnalysis(overrides = {}) {
  return {
    claim_id: "CLM-1",
    available: false,
    overall_risk: null,
    risk_score: null,
    confidence_score: null,
    confidence_band: null,
    review_priority: null,
    contributing_signal_count: null,
    unavailable_signal_count: null,
    human_review_required: true,
    fraud_analysis: { available: false, message: "No fraud risk analysis has been generated for this claim.", reason_codes: [] },
    consistency_analysis: { available: false, message: "No cross-document consistency analysis has been generated for this claim.", contradictions: [] },
    repair_estimate_analysis: { available: false, message: "No repair estimate has been submitted for this claim yet.", reason_codes: [] },
    reason_codes: [],
    officer_explanations: [],
    signals: [],
    explanation: [],
    limitations: ["No AI risk-fusion result is available for this claim - it is outside the Step 5.4 research-prototype dataset."],
    data_source: "Step 5.4 risk-fusion research prototype",
    ...overrides,
  };
}

function availableAnalysis(overrides = {}) {
  return {
    claim_id: "CLM-1",
    available: true,
    overall_risk: "HIGH",
    risk_score: 0.5657809940385498,
    confidence_score: 0.4940821280979983,
    confidence_band: "LOW_CONFIDENCE",
    review_priority: "HIGH_REVIEW",
    contributing_signal_count: 7,
    unavailable_signal_count: 0,
    human_review_required: true,
    fraud_analysis: { available: false, message: "No fraud risk analysis has been generated for this claim.", reason_codes: [] },
    consistency_analysis: { available: false, message: "No cross-document consistency analysis has been generated for this claim.", contradictions: [] },
    repair_estimate_analysis: { available: false, message: "No repair estimate has been submitted for this claim yet.", reason_codes: [] },
    reason_codes: ["DOCUMENT_INCONSISTENCY"],
    officer_explanations: [],
    signals: [],
    explanation: ["These are AI risk signals for review prioritization, not a fraud determination."],
    limitations: [],
    data_source: "Step 5.4 risk-fusion research prototype",
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/officer/claims/CLM-1/ai-insights"]}>
      <Routes>
        <Route path="/officer/claims/:claimId/ai-insights" element={<AiInsightsPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("AiInsightsPage - live AI analysis", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getClaimWorkspaceData.mockResolvedValue(baseWorkspace());
  });

  it("loads the live AI analysis for the open claim", async () => {
    getAiAnalysis.mockResolvedValue(unavailableAnalysis());
    renderPage();
    await screen.findByText("AI Claim Analysis");
    expect(getAiAnalysis).toHaveBeenCalledWith("CLM-1");
  });

  it("shows a loading state before the AI analysis resolves", async () => {
    let resolveFn;
    getAiAnalysis.mockReturnValueOnce(new Promise((resolve) => { resolveFn = resolve; }));
    renderPage();
    expect(await screen.findByText(/loading ai analysis/i)).toBeInTheDocument();
    resolveFn(unavailableAnalysis());
    await waitFor(() => expect(screen.queryByText(/loading ai analysis/i)).not.toBeInTheDocument());
  });

  it("renders available risk/confidence analysis", async () => {
    getAiAnalysis.mockResolvedValue(availableAnalysis());
    renderPage();
    expect(await screen.findByText("Risk Score")).toBeInTheDocument();
    expect(screen.getByText("HIGH")).toBeInTheDocument();
    expect(screen.getByText("Confidence")).toBeInTheDocument();
  });

  it("renders an honest unavailable state for each component when analysis is missing", async () => {
    getAiAnalysis.mockResolvedValue(unavailableAnalysis());
    renderPage();
    expect(await screen.findByText("No overall AI risk assessment available for this claim")).toBeInTheDocument();
    expect(screen.getByText("Fraud risk analysis unavailable")).toBeInTheDocument();
    expect(screen.getByText("Cross-document consistency analysis unavailable")).toBeInTheDocument();
    expect(screen.getByText("Repair estimate analysis unavailable")).toBeInTheDocument();
    // No fabricated zero score anywhere in the unavailable state.
    expect(screen.queryByText("0 / 100")).not.toBeInTheDocument();
  });

  it("renders the human-review warning notice", async () => {
    getAiAnalysis.mockResolvedValue(availableAnalysis({ overall_risk: "HIGH", confidence_band: "LOW_CONFIDENCE" }));
    renderPage();
    expect(await screen.findByText(/high risk does not mean fraud/i)).toBeInTheDocument();
    expect(screen.getAllByText(/final claim decision remains with the claims officer|final decision remains with claims officer/i).length).toBeGreaterThan(0);
  });

  it("the only button on the page runs live analysis - never a decision control", async () => {
    getAiAnalysis.mockResolvedValue(availableAnalysis());
    renderPage();
    await screen.findByText("AI Claim Analysis");
    const buttons = screen.queryAllByRole("button");
    expect(buttons).toHaveLength(1);
    expect(buttons[0]).toHaveTextContent(/run ai analysis/i);
    expect(screen.queryAllByRole("textbox")).toHaveLength(0);
  });
});
