import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../services/officerService", () => ({
  checkEvidenceDuplication: vi.fn(),
  submitDecision: vi.fn(),
}));

import { checkEvidenceDuplication, submitDecision } from "../../../services/officerService";
import EvidenceDuplicationPanel from "../EvidenceDuplicationPanel";

function photo(overrides = {}) {
  return {
    evidence_id: "EVD-1",
    evidence_type: "Damage Photo",
    file_name: "front.jpg",
    status: "NO_MATCH_FOUND",
    matches: [],
    explanation: "No identical or near-identical copy was found among the 3 other stored evidence photo(s).",
    ...overrides,
  };
}

function duplicationResult(results, overrides = {}) {
  return {
    Claim_ID: "CLM-1",
    photos_checked: results.length,
    photos_compared_against: 4,
    results,
    limitations: ["It recognises resized and re-saved copies, but not mirrored, rotated or heavily cropped copies."],
    ...overrides,
  };
}

async function runCheck(result) {
  checkEvidenceDuplication.mockResolvedValue(result);
  render(<EvidenceDuplicationPanel claimId="CLM-1" />);
  fireEvent.click(screen.getByRole("button", { name: /check photos/i }));
  return screen.findByText(/photo\(s\) on this claim checked against/i);
}

describe("EvidenceDuplicationPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does not run the check until the officer clicks the button", () => {
    render(<EvidenceDuplicationPanel claimId="CLM-1" />);
    expect(checkEvidenceDuplication).not.toHaveBeenCalled();
    expect(screen.getByText(/not an accusation of wrongdoing/i)).toBeInTheDocument();
  });

  it("calls the check for this claim and shows the per-photo result", async () => {
    await runCheck(duplicationResult([photo()]));
    expect(checkEvidenceDuplication).toHaveBeenCalledWith("CLM-1");
    expect(screen.getByText("front.jpg")).toBeInTheDocument();
    expect(screen.getByText("No copy found")).toBeInTheDocument();
    expect(screen.getByText(/not mirrored, rotated or heavily cropped/i)).toBeInTheDocument();
  });

  it("shows an exact copy found on another claim, with that claim's ID", async () => {
    await runCheck(
      duplicationResult([
        photo({
          status: "EXACT_DUPLICATE",
          matches: [{ evidence_id: "EVD-9", claim_id: "CLM-OTHER", same_claim: false, match_type: "EXACT", hash_distance: 0 }],
          explanation: "An identical file is also stored as evidence EVD-9 on claim CLM-OTHER.",
        }),
      ])
    );
    const item = screen.getByText("front.jpg").closest("li");
    expect(within(item).getByText("Exact copy found")).toBeInTheDocument();
    expect(within(item).getByText("EVD-9")).toBeInTheDocument();
    expect(within(item).getByText("claim CLM-OTHER")).toBeInTheDocument();
  });

  it("shows a near copy on the same claim with the number of differing fingerprint bits", async () => {
    await runCheck(
      duplicationResult([
        photo({
          status: "NEAR_DUPLICATE",
          matches: [{ evidence_id: "EVD-2", claim_id: "CLM-1", same_claim: true, match_type: "NEAR", hash_distance: 3 }],
          explanation: "A visually near-identical photo is also stored as evidence EVD-2 on this same claim.",
        }),
      ])
    );
    expect(screen.getByText("Near copy found")).toBeInTheDocument();
    expect(screen.getByText("same claim")).toBeInTheDocument();
    expect(screen.getByText(/3 of 64 fingerprint bits differ/i)).toBeInTheDocument();
  });

  it("explains when the claim has no photos", async () => {
    checkEvidenceDuplication.mockResolvedValue(duplicationResult([], { photos_compared_against: 0 }));
    render(<EvidenceDuplicationPanel claimId="CLM-1" />);
    fireEvent.click(screen.getByRole("button", { name: /check photos/i }));
    expect(await screen.findByText(/no evidence photos to check yet/i)).toBeInTheDocument();
  });

  it("shows an error message when the check fails", async () => {
    checkEvidenceDuplication.mockRejectedValue({ response: { status: 403 } });
    render(<EvidenceDuplicationPanel claimId="CLM-1" />);
    fireEvent.click(screen.getByRole("button", { name: /check photos/i }));
    expect(await screen.findByText(/photo check failed/i)).toBeInTheDocument();
  });

  it("never shows the word 'fraud' and never calls the decision workflow", async () => {
    await runCheck(
      duplicationResult([
        photo({ status: "EXACT_DUPLICATE", matches: [{ evidence_id: "EVD-9", claim_id: "CLM-2", same_claim: false, match_type: "EXACT", hash_distance: 0 }] }),
        photo({ evidence_id: "EVD-3", file_name: "missing.jpg", status: "UNAVAILABLE" }),
      ])
    );
    expect(document.body.textContent.toLowerCase()).not.toContain("fraud");
    expect(submitDecision).not.toHaveBeenCalled();
  });
});
