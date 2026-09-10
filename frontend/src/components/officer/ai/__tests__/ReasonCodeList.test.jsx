import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import ReasonCodeList from "../ReasonCodeList";

describe("ReasonCodeList", () => {
  it("shows an empty state when there are no reason codes", () => {
    render(<ReasonCodeList reasonCodes={[]} />);
    expect(screen.getByText(/no risk signals reached the reporting threshold/i)).toBeInTheDocument();
  });

  it("renders bare codes as badges when no officer explanations are available", () => {
    render(<ReasonCodeList reasonCodes={["DOCUMENT_INCONSISTENCY", "DUPLICATE_EVIDENCE"]} />);
    expect(screen.getByText("DOCUMENT_INCONSISTENCY")).toBeInTheDocument();
    expect(screen.getByText("DUPLICATE_EVIDENCE")).toBeInTheDocument();
  });

  it("prefers officer-facing decision-support wording over a raw code, and never claims fraud is confirmed", () => {
    render(
      <ReasonCodeList
        reasonCodes={["REPAIR_ESTIMATE_ANOMALY"]}
        officerExplanations={[
          {
            code: "REPAIR_ESTIMATE_ANOMALY",
            title: "Repair estimate anomaly detected",
            officer_explanation: "AI risk signal: repair estimate anomaly detected.",
            detail: "The repair estimate contains an unusual cost pattern.",
            severity: "MEDIUM",
          },
        ]}
      />
    );
    expect(screen.getByText("AI risk signal: repair estimate anomaly detected.")).toBeInTheDocument();
    expect(document.body.textContent.toLowerCase()).not.toContain("fraud confirmed");
    expect(document.body.textContent.toLowerCase()).not.toContain("fraud detected");
  });
});
