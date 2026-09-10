import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import HumanReviewNotice from "../HumanReviewNotice";

describe("HumanReviewNotice", () => {
  it("shows the default human-in-the-loop wording", () => {
    render(<HumanReviewNotice />);
    expect(screen.getByText(/final claim decision remains with the claims officer/i)).toBeInTheDocument();
  });

  it("shows the high-risk/low-confidence wording without ever implying fraud is confirmed", () => {
    render(<HumanReviewNotice variant="highRiskLowConfidence" />);
    const text = screen.getByText(/additional human investigation is required/i);
    expect(text).toBeInTheDocument();
    expect(document.body.textContent.toLowerCase()).not.toContain("fraud confirmed");
    expect(document.body.textContent.toLowerCase()).not.toContain("automatically rejected");
  });

  it("shows the insufficient-evidence wording", () => {
    render(<HumanReviewNotice variant="insufficientEvidence" />);
    expect(screen.getByText(/insufficient evidence for a reliable ai assessment/i)).toBeInTheDocument();
  });
});
