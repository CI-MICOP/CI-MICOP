import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../services/officerService", () => ({
  analyzeClaimDocuments: vi.fn(),
  checkClaimConsistency: vi.fn(),
  submitDecision: vi.fn(),
}));

import { analyzeClaimDocuments, checkClaimConsistency, submitDecision } from "../../../services/officerService";
import ConsistencyFindingsPanel from "../ConsistencyFindingsPanel";

function entity(overrides = {}) {
  return {
    status: "MATCH",
    structured_value: "TN01AB1234",
    extracted_value: "TN01AB1234",
    matched_document_type: "RC",
    matched_document_id: "DOC-RC-1",
    explanation: "The registration number extracted from the RC matches the insured vehicle record.",
    ...overrides,
  };
}

function consistencyResult({ registration = {}, policy = {}, narrative = {} } = {}) {
  return {
    Claim_ID: "CLM-1",
    narrative: {
      document_a: { document_id: "DOC-FIR-1", document_type: "FIR" },
      document_b: { document_id: "DOC-SR-1", document_type: "Survey Report" },
      relationship: "CONSISTENT",
      confidence: null,
      explanation: "The FIR and Survey Report describe the accident as occurring at the same stated location (Gandhipuram).",
      limitations: ["Only the stated accident location is compared."],
      ...narrative,
    },
    deterministic: {
      registration: entity(registration),
      policy: entity({
        structured_value: "POL-000123",
        extracted_value: "POL-000123",
        matched_document_type: "Insurance Policy",
        matched_document_id: "DOC-POL-1",
        explanation: "The policy number extracted from the Insurance Policy matches the policy record.",
        ...policy,
      }),
    },
  };
}

function analysisResult(overrides = {}) {
  return {
    Claim_ID: "CLM-1",
    documents_analyzed: 2,
    documents: [
      { Document_ID: "DOC-FIR-1", Document_Type: "FIR", extraction_status: "extracted_native", limitations: [] },
      {
        Document_ID: "DOC-IMG-1",
        Document_Type: "Survey Report",
        extraction_status: "unavailable",
        limitations: ["Tesseract OCR engine is not installed/available on this server."],
      },
    ],
    completeness: {
      available: true,
      required_document_types: ["FIR", "Survey Report", "RC"],
      present_document_types: ["FIR", "Survey Report"],
      missing_document_types: ["RC"],
      completeness_ratio: 0.6667,
      explanation: "2 of 3 required document types are present.",
    },
    consistency: consistencyResult().deterministic,
    ...overrides,
  };
}

function clickCheck() {
  fireEvent.click(screen.getByRole("button", { name: /check consistency/i }));
}

describe("ConsistencyFindingsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders both actions and the officer-review notice before anything runs", () => {
    render(<ConsistencyFindingsPanel claimId="CLM-1" />);
    expect(screen.getByRole("button", { name: /analyze documents/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /check consistency/i })).toBeInTheDocument();
    expect(screen.getByText(/final claim decision remains with the claims officer/i)).toBeInTheDocument();
    expect(analyzeClaimDocuments).not.toHaveBeenCalled();
    expect(checkClaimConsistency).not.toHaveBeenCalled();
  });

  it("calls only the consistency endpoint when Check Consistency is clicked", async () => {
    checkClaimConsistency.mockResolvedValueOnce(consistencyResult());
    render(<ConsistencyFindingsPanel claimId="CLM-1" />);
    clickCheck();

    await screen.findByText("Consistent");
    expect(checkClaimConsistency).toHaveBeenCalledWith("CLM-1");
    expect(analyzeClaimDocuments).not.toHaveBeenCalled();
  });

  it("renders MATCH identifiers and a CONSISTENT narrative with their values and explanations", async () => {
    checkClaimConsistency.mockResolvedValueOnce(consistencyResult());
    render(<ConsistencyFindingsPanel claimId="CLM-1" />);
    clickCheck();

    const identifiers = await screen.findByRole("region", { name: /identifier checks/i });
    expect(within(identifiers).getAllByText("Match")).toHaveLength(2);
    expect(within(identifiers).getAllByText("TN01AB1234")).toHaveLength(2);
    expect(within(identifiers).getByText(/Source: RC \(DOC-RC-1\)/)).toBeInTheDocument();

    const narrative = screen.getByRole("region", { name: /narrative check/i });
    expect(within(narrative).getByText("Consistent")).toBeInTheDocument();
    expect(within(narrative).getByText("Research Prototype")).toBeInTheDocument();
    expect(within(narrative).getByText("DOC-FIR-1")).toBeInTheDocument();
    expect(within(narrative).getByText("DOC-SR-1")).toBeInTheDocument();
    expect(within(narrative).getByText(/only the stated accident location is compared/i)).toBeInTheDocument();
  });

  it("keeps a registration MATCH and a narrative CONTRADICTION separate - neither overrides the other", async () => {
    checkClaimConsistency.mockResolvedValueOnce(
      consistencyResult({
        narrative: {
          relationship: "CONTRADICTION",
          explanation:
            "The FIR states Gandhipuram as the accident location, while the Survey Report states Peelamedu. Document inconsistency identified for officer review.",
        },
      })
    );
    render(<ConsistencyFindingsPanel claimId="CLM-1" />);
    clickCheck();

    const narrative = await screen.findByRole("region", { name: /narrative check/i });
    expect(within(narrative).getByText("Contradiction")).toBeInTheDocument();
    expect(within(narrative).queryByText("Match")).not.toBeInTheDocument();

    const identifiers = screen.getByRole("region", { name: /identifier checks/i });
    expect(within(identifiers).getAllByText("Match")).toHaveLength(2);
    expect(within(identifiers).queryByText("Contradiction")).not.toBeInTheDocument();
  });

  it("shows MISMATCH and CONTRADICTION as review findings, not as danger", async () => {
    checkClaimConsistency.mockResolvedValueOnce(
      consistencyResult({
        registration: { status: "MISMATCH", extracted_value: "KA05XY9999" },
        narrative: { relationship: "CONTRADICTION" },
      })
    );
    render(<ConsistencyFindingsPanel claimId="CLM-1" />);
    clickCheck();

    const mismatch = await screen.findByText("Mismatch");
    expect(mismatch.className).toContain("bg-amber-50");
    expect(mismatch.className).not.toContain("bg-red-50");
    expect(screen.getByText("Contradiction").className).toContain("bg-amber-50");
    expect(screen.getByText("KA05XY9999")).toBeInTheDocument();
  });

  it("shows UNAVAILABLE and INCONCLUSIVE neutrally, with missing values rendered honestly", async () => {
    checkClaimConsistency.mockResolvedValueOnce(
      consistencyResult({
        registration: {
          status: "UNAVAILABLE",
          extracted_value: null,
          matched_document_type: null,
          matched_document_id: null,
          explanation: "No RC document with extracted text is available for this claim.",
        },
        narrative: {
          document_b: null,
          relationship: "INCONCLUSIVE",
          explanation: "A Survey Report is required for a narrative comparison but none is available for this claim.",
        },
      })
    );
    render(<ConsistencyFindingsPanel claimId="CLM-1" />);
    clickCheck();

    const unavailable = await screen.findByText("Unavailable");
    expect(unavailable.className).toContain("bg-slate-100");
    expect(screen.getByText("Inconclusive").className).toContain("bg-slate-100");
    expect(screen.getByText(/no rc document with extracted text/i)).toBeInTheDocument();
    expect(screen.getByText("Not available")).toBeInTheDocument();
    expect(screen.queryByText(/Source: null/)).not.toBeInTheDocument();
  });

  it("never uses the word fraud or exposes a confidence value", async () => {
    checkClaimConsistency.mockResolvedValueOnce(consistencyResult({ narrative: { relationship: "CONTRADICTION" } }));
    const { container } = render(<ConsistencyFindingsPanel claimId="CLM-1" />);
    clickCheck();
    await screen.findByText("Contradiction");

    expect(container.textContent).not.toMatch(/fraud/i);
    expect(container.textContent).not.toMatch(/confidence/i);
  });

  it("shows the analysis summary, missing types and per-document extraction reasons", async () => {
    analyzeClaimDocuments.mockResolvedValueOnce(analysisResult());
    render(<ConsistencyFindingsPanel claimId="CLM-1" />);
    fireEvent.click(screen.getByRole("button", { name: /analyze documents/i }));

    expect(await screen.findByText(/2 of 3 required document types are present/i)).toBeInTheDocument();
    expect(analyzeClaimDocuments).toHaveBeenCalledWith("CLM-1");
    expect(checkClaimConsistency).not.toHaveBeenCalled();
    expect(screen.getByText("Missing: RC")).toBeInTheDocument();
    expect(screen.getByText("Text extracted")).toBeInTheDocument();
    expect(screen.getByText("Extraction unavailable")).toBeInTheDocument();
    expect(screen.getByText(/tesseract ocr engine is not installed/i)).toBeInTheDocument();
  });

  it("clears stale consistency findings after documents are re-analyzed", async () => {
    checkClaimConsistency.mockResolvedValueOnce(consistencyResult());
    analyzeClaimDocuments.mockResolvedValueOnce(analysisResult());
    render(<ConsistencyFindingsPanel claimId="CLM-1" />);

    clickCheck();
    await screen.findByText("Consistent");

    fireEvent.click(screen.getByRole("button", { name: /analyze documents/i }));
    await screen.findByText(/2 of 3 required document types are present/i);
    expect(screen.queryByText("Consistent")).not.toBeInTheDocument();
  });

  it("disables both buttons while a request is in flight", async () => {
    let resolveFn;
    checkClaimConsistency.mockReturnValueOnce(new Promise((resolve) => { resolveFn = resolve; }));
    render(<ConsistencyFindingsPanel claimId="CLM-1" />);
    clickCheck();

    expect(screen.getByRole("button", { name: /analyze documents/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /check consistency/i })).toBeDisabled();
    resolveFn(consistencyResult());
    await waitFor(() => expect(screen.getByRole("button", { name: /check consistency/i })).not.toBeDisabled());
  });

  it("shows an API error when the consistency check fails", async () => {
    checkClaimConsistency.mockRejectedValueOnce({ response: { status: 404 } });
    render(<ConsistencyFindingsPanel claimId="CLM-1" />);
    clickCheck();

    expect(await screen.findByText(/consistency check failed: the requested record could not be found/i)).toBeInTheDocument();
  });

  it("shows an API error when document analysis fails", async () => {
    analyzeClaimDocuments.mockRejectedValueOnce({ response: { status: 500 } });
    render(<ConsistencyFindingsPanel claimId="CLM-1" />);
    fireEvent.click(screen.getByRole("button", { name: /analyze documents/i }));

    expect(await screen.findByText(/document analysis failed/i)).toBeInTheDocument();
  });

  it("never touches the human decision workflow", async () => {
    checkClaimConsistency.mockResolvedValueOnce(consistencyResult());
    analyzeClaimDocuments.mockResolvedValueOnce(analysisResult());
    render(<ConsistencyFindingsPanel claimId="CLM-1" />);

    clickCheck();
    await screen.findByText("Consistent");
    fireEvent.click(screen.getByRole("button", { name: /analyze documents/i }));
    await screen.findByText(/2 of 3 required document types are present/i);

    expect(submitDecision).not.toHaveBeenCalled();
  });
});
