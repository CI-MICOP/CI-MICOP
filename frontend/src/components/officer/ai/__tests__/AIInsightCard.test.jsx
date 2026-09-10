import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import AIInsightCard from "../AIInsightCard";

const BASE_INSIGHT = {
  claimId: "CLM-000007",
  overallRiskScore: 0.57,
  riskScoreOn100: 57,
  riskBand: "HIGH",
  confidenceScore: 0.49,
  confidenceOn100: 49,
  confidenceBand: "LOW_CONFIDENCE",
  uncertaintyReasons: ["Includes a model/rule-screening-derived signal..."],
  reviewPriority: "HIGH_REVIEW",
  humanReviewRequired: true,
  evidenceCount: 7,
  contributingSignalCount: 7,
  unavailableSignalCount: 0,
  reasonCodes: ["DOCUMENT_INCONSISTENCY", "DUPLICATE_EVIDENCE"],
  officerExplanations: null,
  signals: null,
  hasFullSignalBreakdown: false,
  plainLanguageExplanation: "These are AI risk signals for review prioritization, not a fraud determination.",
};

describe("AIInsightCard", () => {
  it("renders an explicit empty state for a missing/invalid AI result rather than fabricating one", () => {
    render(<AIInsightCard insight={null} />);
    expect(screen.getByText(/no ai risk assessment available for this claim/i)).toBeInTheDocument();
  });

  it("renders risk score and confidence as two separate, independently labeled values", () => {
    render(<AIInsightCard insight={BASE_INSIGHT} />);
    expect(screen.getByText("Risk Score")).toBeInTheDocument();
    expect(screen.getByText("Confidence")).toBeInTheDocument();
    expect(screen.getByText("57")).toBeInTheDocument();
    expect(screen.getByText("49")).toBeInTheDocument();
    // risk and confidence bands are shown independently - HIGH risk with LOW confidence, not collapsed into one indicator
    expect(screen.getByText("HIGH")).toBeInTheDocument();
    expect(screen.getByText("LOW")).toBeInTheDocument();
  });

  it("shows the high-risk/low-confidence human-review warning for that combination", () => {
    render(<AIInsightCard insight={BASE_INSIGHT} />);
    expect(screen.getByText(/high risk does not mean fraud/i)).toBeInTheDocument();
  });

  it("always states human review is required and never renders a decision action", () => {
    render(<AIInsightCard insight={BASE_INSIGHT} />);
    expect(screen.getByText("YES")).toBeInTheDocument();
    // no automatic decision UI - this component must contain zero buttons
    expect(screen.queryAllByRole("button")).toHaveLength(0);
    expect(screen.queryByText(/approve/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/reject/i)).not.toBeInTheDocument();
  });

  it("falls back to a signal-breakdown-not-available message when no full breakdown was generated", () => {
    render(<AIInsightCard insight={BASE_INSIGHT} />);
    expect(screen.getByText(/full signal breakdown not generated for this claim/i)).toBeInTheDocument();
  });

  it("renders the full signal breakdown when it is available", () => {
    const withSignals = {
      ...BASE_INSIGHT,
      hasFullSignalBreakdown: true,
      signals: [
        { signal_name: "document_consistency_mismatch", availability: "available", signal_value: 0.9, explanation: "Mismatch found." },
      ],
    };
    render(<AIInsightCard insight={withSignals} />);
    expect(screen.getByText("Document Consistency")).toBeInTheDocument();
  });
});
