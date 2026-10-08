import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../services/officerService", () => ({
  checkRepairEstimates: vi.fn(),
  submitDecision: vi.fn(),
}));

import { checkRepairEstimates, submitDecision } from "../../../services/officerService";
import RepairEstimateChecksPanel from "../RepairEstimateChecksPanel";

function item(check, status, explanation) {
  return { check, status, value: null, reference: null, explanation };
}

function estimate(overrides = {}) {
  return {
    estimate_id: "EST-1",
    garage_id: "GAR-0001",
    estimate_date: "2026-08-22",
    repair_estimate: "40000.00",
    status: "NO_POINTS_FOUND",
    checks: [
      item("ESTIMATE_DATE", "NOT_FLAGGED", "The estimate is dated 2 day(s) after the recorded accident date."),
      item("COST_VS_ESTIMATE", "INFO", "The repair cost is INR 2,000.00 (5.0%) above the repair estimate."),
      item("REPAIR_DAYS", "UNAVAILABLE", "The actual repair days have not been recorded yet."),
    ],
    ...overrides,
  };
}

function checksResult(results, quoteComparison = null) {
  return {
    Claim_ID: "CLM-1",
    estimates_checked: results.length,
    results,
    quote_comparison: quoteComparison,
    limitations: ["These are plain comparisons between this claim's own records, not an AI model."],
  };
}

async function runCheck(result) {
  checkRepairEstimates.mockResolvedValue(result);
  render(<RepairEstimateChecksPanel claimId="CLM-1" />);
  fireEvent.click(screen.getByRole("button", { name: /check estimates/i }));
}

describe("RepairEstimateChecksPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does not run until the officer clicks the button", () => {
    render(<RepairEstimateChecksPanel claimId="CLM-1" />);
    expect(checkRepairEstimates).not.toHaveBeenCalled();
  });

  it("shows an estimate with each check, its status and the limitations", async () => {
    await runCheck(checksResult([estimate()]));
    expect(await screen.findByText("No points found")).toBeInTheDocument();
    expect(checkRepairEstimates).toHaveBeenCalledWith("CLM-1");
    expect(screen.getByText("Estimate date")).toBeInTheDocument();
    expect(screen.getByText("No point found")).toBeInTheDocument();
    expect(screen.getByText("For information")).toBeInTheDocument();
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
    expect(screen.getByText(/not an AI model/i)).toBeInTheDocument();
  });

  it("marks an estimate with a flagged check as having points to review", async () => {
    await runCheck(
      checksResult([
        estimate({
          status: "POINTS_TO_REVIEW",
          checks: [item("ESTIMATE_DATE", "FLAGGED", "The estimate is dated 1 day(s) before the recorded accident date.")],
        }),
      ])
    );
    const row = (await screen.findByText("EST-1")).closest("li");
    expect(within(row).getByText("Points to review")).toBeInTheDocument();
    expect(within(row).getByText("Review")).toBeInTheDocument();
    expect(within(row).getByText(/1 day\(s\) before/i)).toBeInTheDocument();
  });

  it("shows the side-by-side comparison only when there is one", async () => {
    await runCheck(
      checksResult([estimate(), estimate({ estimate_id: "EST-2", garage_id: "GAR-0002" })], {
        explanation: "2 estimates are on file from 2 garage(s): lowest INR 50,000.00 (EST-1), highest INR 70,000.00 (EST-2).",
      })
    );
    expect(await screen.findByText("Estimates side by side")).toBeInTheDocument();
    expect(screen.getByText(/2 estimates are on file/i)).toBeInTheDocument();
  });

  it("does not show a comparison for a single estimate", async () => {
    await runCheck(checksResult([estimate()]));
    await screen.findByText("EST-1");
    expect(screen.queryByText("Estimates side by side")).not.toBeInTheDocument();
  });

  it("explains when the claim has no estimates", async () => {
    await runCheck(checksResult([]));
    expect(await screen.findByText(/no repair estimates to check yet/i)).toBeInTheDocument();
  });

  it("shows an error message when the check fails", async () => {
    checkRepairEstimates.mockRejectedValue({ response: { status: 403 } });
    render(<RepairEstimateChecksPanel claimId="CLM-1" />);
    fireEvent.click(screen.getByRole("button", { name: /check estimates/i }));
    expect(await screen.findByText(/estimate check failed/i)).toBeInTheDocument();
  });

  it("never shows the word 'fraud' and never calls the decision workflow", async () => {
    await runCheck(checksResult([estimate({ status: "POINTS_TO_REVIEW" })]));
    await screen.findByText("Points to review");
    expect(document.body.textContent.toLowerCase()).not.toContain("fraud");
    expect(submitDecision).not.toHaveBeenCalled();
  });
});
