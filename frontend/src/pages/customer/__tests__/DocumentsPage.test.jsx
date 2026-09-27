import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../services/documentService", () => ({
  listMyDocuments: vi.fn(),
  analyzeDocument: vi.fn(),
}));

import { analyzeDocument, listMyDocuments } from "../../../services/documentService";
import DocumentsPage from "../DocumentsPage";

const DOCUMENT = {
  Document_ID: "DOC-1",
  Document_Type: "FIR",
  Document_Name: "fir.pdf",
  Claim_Number: "CLM-2026-AAAA",
  Document_Submitted_Date: "2026-01-01",
  Document_Status: "Submitted",
  Verification_Status: "Pending",
  Document_Completeness: "0.0000",
};

function partialAnalysis(overrides = {}) {
  return {
    Document_ID: "DOC-1",
    Document_Type: "FIR",
    extraction_status: "extracted_native",
    extracted_text: "FIR details here.",
    ocr_confidence: 1.0,
    mismatch_indicator: false,
    completeness: {
      available: true,
      required_document_types: ["Accident Photos", "Driving Licence", "FIR", "Insurance Policy", "RC"],
      present_document_types: ["FIR"],
      missing_document_types: ["Accident Photos", "Driving Licence", "Insurance Policy", "RC"],
      completeness_ratio: 0.2,
      explanation: "1 of 5 required document type(s) are present for this 'Third Party' claim.",
    },
    entities: {
      status: "extracted",
      entities: [
        {
          entity_type: "registration_number",
          value: "TN01AB0001",
          normalized_value: "TN01AB0001",
          confidence: 0.9,
          source: "regex_strict_format",
          reason: "Matches the Indian motor-vehicle registration format.",
        },
      ],
      limitations: [
        "This is a deterministic, regex/rule-based extractor - not an NLP model, not a general "
          + "information-extraction system, and not a fraud or consistency detector.",
      ],
    },
    limitations: [],
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <DocumentsPage />
    </MemoryRouter>
  );
}

async function openDocumentModal() {
  listMyDocuments.mockResolvedValue([DOCUMENT]);
  renderPage();
  fireEvent.click(await screen.findByText("View"));
  await screen.findByText("Document Analysis");
}

describe("DocumentsPage - Step 5.8.12 analyze action", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the Analyze action inside the document detail modal", async () => {
    await openDocumentModal();
    expect(screen.getByRole("button", { name: /analyze/i })).toBeInTheDocument();
  });

  it("shows a loading state while analysis is in flight", async () => {
    await openDocumentModal();
    let resolveFn;
    analyzeDocument.mockReturnValueOnce(new Promise((resolve) => { resolveFn = resolve; }));

    fireEvent.click(screen.getByRole("button", { name: /analyze/i }));
    await waitFor(() => expect(screen.getByRole("button", { name: /analyze/i })).toBeDisabled());
    resolveFn(partialAnalysis());
    await waitFor(() => expect(screen.getByRole("button", { name: /analyze/i })).not.toBeDisabled());
  });

  it("renders a successful analysis result honestly, including missing document types", async () => {
    await openDocumentModal();
    analyzeDocument.mockResolvedValueOnce(partialAnalysis());

    fireEvent.click(screen.getByRole("button", { name: /analyze/i }));

    expect(await screen.findByText("Text extracted (native)")).toBeInTheDocument();
    expect(screen.getByText("1.00")).toBeInTheDocument();
    expect(screen.getByText("Yes")).toBeInTheDocument();
    expect(screen.getByText(/20% \(1\/5 required types\)/)).toBeInTheDocument();
    expect(screen.getByText(/Accident Photos, Driving Licence, Insurance Policy, RC/)).toBeInTheDocument();
  });

  it("renders an honest unavailable OCR state without fabricating confidence", async () => {
    await openDocumentModal();
    analyzeDocument.mockResolvedValueOnce(
      partialAnalysis({
        extraction_status: "unavailable",
        extracted_text: "",
        ocr_confidence: 0.0,
        limitations: ["Tesseract OCR engine is not installed/available on this server."],
      })
    );

    fireEvent.click(screen.getByRole("button", { name: /analyze/i }));

    expect(await screen.findByText("Unavailable")).toBeInTheDocument();
    expect(screen.getByText("0.00")).toBeInTheDocument();
    expect(screen.getByText("No")).toBeInTheDocument();
    expect(screen.getByText(/tesseract ocr engine is not installed/i)).toBeInTheDocument();
  });

  it("renders an honest unavailable completeness state for a zero-document claim", async () => {
    await openDocumentModal();
    analyzeDocument.mockResolvedValueOnce(
      partialAnalysis({
        completeness: {
          available: false,
          required_document_types: [],
          present_document_types: [],
          missing_document_types: [],
          completeness_ratio: null,
          explanation: "No documents have been uploaded for this claim yet.",
        },
      })
    );

    fireEvent.click(screen.getByRole("button", { name: /analyze/i }));

    expect(await screen.findByText("Unavailable - no documents to assess yet")).toBeInTheDocument();
  });

  it("renders extracted entities as best-effort, not a consistency verdict", async () => {
    await openDocumentModal();
    analyzeDocument.mockResolvedValueOnce(partialAnalysis());

    fireEvent.click(screen.getByRole("button", { name: /analyze/i }));

    expect(await screen.findByText("Extracted Entities")).toBeInTheDocument();
    expect(screen.getByText(/best-effort extraction/i)).toBeInTheDocument();
    expect(screen.getByText(/not yet used for consistency decisions/i)).toBeInTheDocument();
    expect(screen.getByText("Registration Number")).toBeInTheDocument();
    expect(screen.getByText("TN01AB0001 (90%)")).toBeInTheDocument();
  });

  it("shows 'No entities found' when extraction finds nothing", async () => {
    await openDocumentModal();
    analyzeDocument.mockResolvedValueOnce(
      partialAnalysis({ entities: { status: "no_candidates", entities: [], limitations: [] } })
    );

    fireEvent.click(screen.getByRole("button", { name: /analyze/i }));

    expect(await screen.findByText("No entities found.")).toBeInTheDocument();
  });

  it("shows an error message when analysis fails", async () => {
    await openDocumentModal();
    analyzeDocument.mockRejectedValueOnce({ response: { status: 500, data: { detail: "Analysis failed." } } });

    fireEvent.click(screen.getByRole("button", { name: /analyze/i }));

    expect(await screen.findByText("Something went wrong while loading this data.")).toBeInTheDocument();
  });

  it("resets analysis state when a different document is opened", async () => {
    const secondDocument = { ...DOCUMENT, Document_ID: "DOC-2", Document_Name: "rc.pdf" };
    listMyDocuments.mockResolvedValue([DOCUMENT, secondDocument]);
    renderPage();

    fireEvent.click((await screen.findAllByText("View"))[0]);
    analyzeDocument.mockResolvedValueOnce(partialAnalysis());
    fireEvent.click(screen.getByRole("button", { name: /analyze/i }));
    await screen.findByText("Text extracted (native)");

    fireEvent.click(screen.getByLabelText("Close dialog"));
    fireEvent.click((await screen.findAllByText("View"))[1]);

    expect(screen.queryByText("Text extracted (native)")).not.toBeInTheDocument();
  });
});
