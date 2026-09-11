import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../../services/officerService", () => ({
  runAiAnalysis: vi.fn(),
  submitDecision: vi.fn(),
}));

import { runAiAnalysis, submitDecision } from "../../../../services/officerService";
import LiveRunPanel from "../LiveRunPanel";

function partialResult(overrides = {}) {
  return {
    claim_id: "CLM-1",
    available: true,
    status: "partial",
    evidence_summary: { documents: 1, vehicle_damage: 0, evidence: 0, repair_estimates: 1, inspections: 1 },
    overall_risk_score: 0.12,
    risk_band: "LOW",
    confidence_score: 0.28,
    confidence_band: "LOW_CONFIDENCE",
    uncertainty_reasons: ["Only 2/7 signals available."],
    signals: [
      { signal_name: "claim_pattern_anomaly", category: "CLAIM_PATTERN_ANOMALY", signal_value: 0.0, availability: "available", confidence: 1.0, explanation: "Claim filed 231 day(s) after policy start." },
      { signal_name: "repair_estimate_anomaly", category: "REPAIR_ESTIMATE_ANOMALY", signal_value: 0.05, availability: "available", confidence: 1.0, explanation: "Repair-estimate/claim-amount ratio 0.96." },
      { signal_name: "document_consistency_mismatch", category: "DOCUMENT_CONSISTENCY", signal_value: null, availability: "unavailable", confidence: null, explanation: "No cross-document consistency analysis pipeline is connected to live claims yet." },
    ],
    limitations: ["Only 2/7 signal families defined by the Step 5.4 research prototype could be computed live for this claim."],
    methodology_source: "Step 5.4 risk-fusion research prototype",
    ...overrides,
  };
}

function insufficientResult(overrides = {}) {
  return partialResult({
    status: "insufficient_evidence",
    available: false,
    overall_risk_score: null,
    risk_band: null,
    confidence_score: null,
    confidence_band: "INSUFFICIENT_EVIDENCE",
    signals: [
      { signal_name: "claim_pattern_anomaly", category: "CLAIM_PATTERN_ANOMALY", signal_value: 0.0, availability: "available", confidence: 1.0, explanation: "Claim filed 5 day(s) after policy start." },
      { signal_name: "repair_estimate_anomaly", category: "REPAIR_ESTIMATE_ANOMALY", signal_value: null, availability: "unavailable", confidence: null, explanation: "No repair estimate has been submitted for this claim yet." },
    ],
    evidence_summary: { documents: 0, vehicle_damage: 0, evidence: 0, repair_estimates: 0, inspections: 0 },
    ...overrides,
  });
}

describe("LiveRunPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the Run AI Analysis button in the Ready state", () => {
    render(<LiveRunPanel claimId="CLM-1" />);
    expect(screen.getByRole("button", { name: /run ai analysis/i })).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();
  });

  it("shows a Running loading state while the request is in flight", async () => {
    let resolveFn;
    runAiAnalysis.mockReturnValueOnce(new Promise((resolve) => { resolveFn = resolve; }));
    render(<LiveRunPanel claimId="CLM-1" />);
    fireEvent.click(screen.getByRole("button", { name: /run ai analysis/i }));
    expect(await screen.findByText("Running")).toBeInTheDocument();
    resolveFn(partialResult());
    await waitFor(() => expect(screen.queryByText("Running")).not.toBeInTheDocument());
  });

  it("renders the partial/available result after a successful run", async () => {
    runAiAnalysis.mockResolvedValueOnce(partialResult());
    render(<LiveRunPanel claimId="CLM-1" />);
    fireEvent.click(screen.getByRole("button", { name: /run ai analysis/i }));

    expect(await screen.findByText("Partially Available")).toBeInTheDocument();
    expect(screen.getByText("LOW")).toBeInTheDocument();
    expect(screen.getByText("LOW_CONFIDENCE")).toBeInTheDocument();
  });

  it("renders the insufficient evidence state honestly, with no fabricated score", async () => {
    runAiAnalysis.mockResolvedValueOnce(insufficientResult());
    render(<LiveRunPanel claimId="CLM-1" />);
    fireEvent.click(screen.getByRole("button", { name: /run ai analysis/i }));

    expect(await screen.findByText("Insufficient Evidence")).toBeInTheDocument();
    expect(screen.getByText(/not enough live data exists yet/i)).toBeInTheDocument();
    expect(screen.queryByText("Risk Band")).not.toBeInTheDocument();
  });

  it("renders each unavailable component with its specific reason", async () => {
    runAiAnalysis.mockResolvedValueOnce(partialResult());
    render(<LiveRunPanel claimId="CLM-1" />);
    fireEvent.click(screen.getByRole("button", { name: /run ai analysis/i }));

    await screen.findByText("Partially Available");
    expect(screen.getByText(/no cross-document consistency analysis pipeline/i)).toBeInTheDocument();
    expect(screen.getAllByText("Not Available").length).toBeGreaterThan(0);
  });

  it("shows an API error when the run fails", async () => {
    runAiAnalysis.mockRejectedValueOnce({ response: { status: 500 } });
    render(<LiveRunPanel claimId="CLM-1" />);
    fireEvent.click(screen.getByRole("button", { name: /run ai analysis/i }));

    expect(await screen.findByText("Error")).toBeInTheDocument();
  });

  it("calls onAfterRun to refresh the read-only AI panel after a successful run", async () => {
    runAiAnalysis.mockResolvedValueOnce(partialResult());
    const onAfterRun = vi.fn();
    render(<LiveRunPanel claimId="CLM-1" onAfterRun={onAfterRun} />);
    fireEvent.click(screen.getByRole("button", { name: /run ai analysis/i }));

    await waitFor(() => expect(onAfterRun).toHaveBeenCalledTimes(1));
  });

  it("never touches the human decision workflow", async () => {
    runAiAnalysis.mockResolvedValueOnce(partialResult());
    render(<LiveRunPanel claimId="CLM-1" />);
    fireEvent.click(screen.getByRole("button", { name: /run ai analysis/i }));
    await screen.findByText("Partially Available");

    expect(submitDecision).not.toHaveBeenCalled();
    expect(screen.getByText(/final claim decision remains with the claims officer/i)).toBeInTheDocument();
  });
});
