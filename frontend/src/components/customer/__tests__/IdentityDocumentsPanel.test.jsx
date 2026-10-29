import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../services/documentService", () => ({
  listIdentityDocuments: vi.fn(),
  getIdentityDocumentContent: vi.fn(),
}));

import { getIdentityDocumentContent, listIdentityDocuments } from "../../../services/documentService";
import IdentityDocumentsPanel from "../IdentityDocumentsPanel";

function missing(type) {
  return {
    document_id: null,
    document_type: type,
    submitted_date: null,
    expiry_date: null,
    availability: "not_uploaded",
    media_type: null,
    verification_status: null,
  };
}

function present(type, overrides = {}) {
  return {
    document_id: "DOC-1",
    document_type: type,
    submitted_date: "2026-09-01",
    expiry_date: null,
    availability: "available",
    media_type: "application/pdf",
    verification_status: "Pending",
    ...overrides,
  };
}

describe("IdentityDocumentsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows My Documents with a Not Uploaded badge for every type when none exist", async () => {
    listIdentityDocuments.mockResolvedValue({
      customer_id: "CUST-1",
      documents: [missing("RC"), missing("Driving Licence"), missing("Insurance Policy")],
    });
    render(<IdentityDocumentsPanel />);

    await screen.findByText("My Documents");
    expect(screen.getByText("Registration Certificate (RC)")).toBeInTheDocument();
    expect(screen.getByText("Driving Licence (DL)")).toBeInTheDocument();
    expect(screen.getByText("Insurance Policy")).toBeInTheDocument();
    expect(screen.getAllByText("Not Uploaded")).toHaveLength(3);
  });

  it("shows an uploaded document as Available with a View action and expiry date", async () => {
    listIdentityDocuments.mockResolvedValue({
      customer_id: "CUST-1",
      documents: [
        present("RC", { expiry_date: "2027-01-01" }),
        missing("Driving Licence"),
        missing("Insurance Policy"),
      ],
    });
    render(<IdentityDocumentsPanel />);

    await screen.findByText("Registration Certificate (RC)");
    expect(screen.getByText("Available")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /view registration certificate/i })).toBeInTheDocument();
    expect(screen.getByText(/Expires/)).toBeInTheDocument();
  });

  it("never shows a View action for a document that is not available", async () => {
    listIdentityDocuments.mockResolvedValue({
      customer_id: "CUST-1",
      documents: [missing("RC"), missing("Driving Licence"), missing("Insurance Policy")],
    });
    render(<IdentityDocumentsPanel />);

    await screen.findByText("My Documents");
    expect(screen.queryByRole("button", { name: /view/i })).not.toBeInTheDocument();
  });

  it("opens the document viewer and fetches the real content for the selected document", async () => {
    listIdentityDocuments.mockResolvedValue({
      customer_id: "CUST-1",
      documents: [present("Driving Licence"), missing("RC"), missing("Insurance Policy")],
    });
    getIdentityDocumentContent.mockResolvedValue(new Blob(["%PDF-1.4"], { type: "application/pdf" }));
    render(<IdentityDocumentsPanel />);

    fireEvent.click(await screen.findByRole("button", { name: /view driving licence/i }));

    expect(await screen.findByRole("heading", { name: "Driving Licence (DL)" })).toBeInTheDocument();
    expect(getIdentityDocumentContent).toHaveBeenCalledWith("DOC-1");
  });

  it("shows an honest Not Available badge, with no fabricated link, when the file is missing on the server", async () => {
    listIdentityDocuments.mockResolvedValue({
      customer_id: "CUST-1",
      documents: [
        present("RC", { availability: "unavailable", media_type: null }),
        missing("Driving Licence"),
        missing("Insurance Policy"),
      ],
    });
    render(<IdentityDocumentsPanel />);

    await screen.findByText("Not Available");
    expect(screen.queryByRole("button", { name: /view/i })).not.toBeInTheDocument();
  });
});
