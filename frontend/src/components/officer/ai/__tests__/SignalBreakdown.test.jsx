import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import SignalBreakdown from "../SignalBreakdown";

const AVAILABLE_SIGNAL = {
  signal_name: "document_consistency_mismatch",
  availability: "available",
  signal_value: 0.9,
  explanation: "3/3 cross-document consistency checks flagged a mismatch.",
};

const UNAVAILABLE_SIGNAL = {
  signal_name: "evidence_duplication",
  availability: "unavailable",
  signal_value: null,
  explanation: "No evidence items submitted for this claim.",
};

describe("SignalBreakdown", () => {
  it("shows an explicit empty state when no full signal breakdown exists (missing-signal handling)", () => {
    render(<SignalBreakdown signals={null} />);
    expect(screen.getByText(/full signal breakdown not generated for this claim/i)).toBeInTheDocument();
  });

  it("renders each available signal with a human-readable label and status", () => {
    render(<SignalBreakdown signals={[AVAILABLE_SIGNAL]} />);
    expect(screen.getByText("Document Consistency")).toBeInTheDocument();
    expect(screen.getByText("Warning")).toBeInTheDocument();
    expect(screen.getByText(AVAILABLE_SIGNAL.explanation)).toBeInTheDocument();
    // never shows the raw internal signal_name to the officer
    expect(screen.queryByText("document_consistency_mismatch")).not.toBeInTheDocument();
  });

  it("renders an unavailable signal as explicitly Not Available, not a fabricated value", () => {
    render(<SignalBreakdown signals={[UNAVAILABLE_SIGNAL]} />);
    expect(screen.getByText("Evidence Duplication")).toBeInTheDocument();
    expect(screen.getAllByText("Not Available").length).toBeGreaterThan(0);
  });
});
