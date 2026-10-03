import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../services/officerService", () => ({
  checkPhotoQuality: vi.fn(),
  submitDecision: vi.fn(),
}));

import { checkPhotoQuality, submitDecision } from "../../../services/officerService";
import PhotoQualityPanel from "../PhotoQualityPanel";

const MEASUREMENTS = { width: 640, height: 480, brightness: 140.2, contrast: 35.1, reblur_ratio: 0.21 };

function photo(overrides = {}) {
  return {
    evidence_id: "EVD-1",
    evidence_type: "Damage Photo",
    file_name: "front.jpg",
    status: "NO_ISSUES_FOUND",
    flags: [],
    measurements: MEASUREMENTS,
    explanation: "No size, brightness, contrast or blur issue was found in this photo.",
    ...overrides,
  };
}

function qualityResult(results) {
  return {
    Claim_ID: "CLM-1",
    photos_checked: results.length,
    results,
    limitations: ["A photo of a plain, featureless surface may be flagged as blurry even when it is in focus."],
  };
}

async function runCheck(result) {
  checkPhotoQuality.mockResolvedValue(result);
  render(<PhotoQualityPanel claimId="CLM-1" />);
  fireEvent.click(screen.getByRole("button", { name: /check quality/i }));
}

describe("PhotoQualityPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does not run until the officer clicks the button", () => {
    render(<PhotoQualityPanel claimId="CLM-1" />);
    expect(checkPhotoQuality).not.toHaveBeenCalled();
  });

  it("shows a clear photo with its measurements and the limitations", async () => {
    await runCheck(qualityResult([photo()]));
    expect(await screen.findByText("No issues found")).toBeInTheDocument();
    expect(checkPhotoQuality).toHaveBeenCalledWith("CLM-1");
    expect(screen.getByText("640 × 480")).toBeInTheDocument();
    expect(screen.getByText("140.2 / 255")).toBeInTheDocument();
    expect(screen.getByText(/featureless surface/i)).toBeInTheDocument();
  });

  it("shows each flag of a problem photo as its own badge", async () => {
    await runCheck(
      qualityResult([
        photo({
          status: "ISSUES_FOUND",
          flags: ["TOO_DARK", "BLURRY"],
          measurements: { ...MEASUREMENTS, brightness: 38.5, reblur_ratio: 0.91 },
          explanation: "This photo may be hard to rely on: too dark, blurry. Consider requesting a clearer photo.",
        }),
      ])
    );
    const item = (await screen.findByText("front.jpg")).closest("li");
    expect(within(item).getByText("Quality issues")).toBeInTheDocument();
    expect(within(item).getByText("Too dark")).toBeInTheDocument();
    expect(within(item).getByText("Blurry")).toBeInTheDocument();
    expect(within(item).getByText(/consider requesting a clearer photo/i)).toBeInTheDocument();
  });

  it("shows an unreadable photo as unavailable without measurements", async () => {
    await runCheck(
      qualityResult([
        photo({ status: "UNAVAILABLE", measurements: null, explanation: "The stored file could not be decoded as an image." }),
      ])
    );
    expect(await screen.findByText("Unavailable")).toBeInTheDocument();
    expect(screen.queryByText("Brightness")).not.toBeInTheDocument();
  });

  it("explains when the claim has no photos", async () => {
    await runCheck(qualityResult([]));
    expect(await screen.findByText(/no evidence photos to check yet/i)).toBeInTheDocument();
  });

  it("shows an error message when the check fails", async () => {
    checkPhotoQuality.mockRejectedValue({ response: { status: 403 } });
    render(<PhotoQualityPanel claimId="CLM-1" />);
    fireEvent.click(screen.getByRole("button", { name: /check quality/i }));
    expect(await screen.findByText(/quality check failed/i)).toBeInTheDocument();
  });

  it("never shows the word 'fraud' and never calls the decision workflow", async () => {
    await runCheck(qualityResult([photo({ status: "ISSUES_FOUND", flags: ["LOW_RESOLUTION"] })]));
    await screen.findByText("Low resolution");
    expect(document.body.textContent.toLowerCase()).not.toContain("fraud");
    expect(submitDecision).not.toHaveBeenCalled();
  });
});
