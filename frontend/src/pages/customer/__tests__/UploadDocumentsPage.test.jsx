import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../services/claimService", () => ({
  listClaims: vi.fn(),
}));
vi.mock("../../../services/documentService", () => ({
  uploadDocument: vi.fn(),
}));

import { listClaims } from "../../../services/claimService";
import { uploadDocument } from "../../../services/documentService";
import UploadDocumentsPage from "../UploadDocumentsPage";

const CLAIM = { Claim_ID: "CLM-1", Claim_Number: "CLAIM-0001", Claim_Type: "Own Damage" };

function renderPage() {
  return render(
    <MemoryRouter>
      <UploadDocumentsPage />
    </MemoryRouter>
  );
}

function pdf(name) {
  return new File(["%PDF-1.4"], name, { type: "application/pdf" });
}

async function chooseClaimAndFile(categoryLabel, file) {
  fireEvent.change(await screen.findByLabelText(/^claim/i), { target: { value: "CLM-1" } });
  fireEvent.change(screen.getByLabelText(new RegExp(categoryLabel, "i")), { target: { files: [file] } });
}

describe("UploadDocumentsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listClaims.mockResolvedValue([CLAIM]);
  });

  it("keeps the upload button disabled until a claim and a file are chosen", async () => {
    renderPage();
    const button = await screen.findByRole("button", { name: /upload selected documents/i });
    expect(button).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/^claim/i), { target: { value: "CLM-1" } });
    expect(button).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/fir copy/i), { target: { files: [pdf("fir.pdf")] } });
    expect(button).toBeEnabled();
  });

  it("uploads the selected file to the chosen existing claim and reports success", async () => {
    uploadDocument.mockResolvedValue({ Document_ID: "DOC-1" });
    renderPage();
    const file = pdf("fir.pdf");
    await chooseClaimAndFile("fir copy", file);

    fireEvent.click(screen.getByRole("button", { name: /upload selected documents/i }));

    expect(await screen.findByText(/all 1 document uploaded/i)).toBeInTheDocument();
    expect(uploadDocument).toHaveBeenCalledWith("CLM-1", "fir_copy", file);
    expect(screen.getByText("Uploaded")).toBeInTheDocument();
    expect(screen.queryByText(/not yet connected/i)).not.toBeInTheDocument();
  });

  it("uploads several documents one after another to the same claim", async () => {
    uploadDocument.mockResolvedValue({});
    renderPage();
    await chooseClaimAndFile("fir copy", pdf("fir.pdf"));
    fireEvent.change(screen.getByLabelText(/survey report/i), { target: { files: [pdf("survey.pdf")] } });

    fireEvent.click(screen.getByRole("button", { name: /upload selected documents/i }));

    expect(await screen.findByText(/all 2 documents uploaded/i)).toBeInTheDocument();
    expect(uploadDocument.mock.calls.map((call) => call.slice(0, 2))).toEqual([
      ["CLM-1", "fir_copy"],
      ["CLM-1", "survey_report"],
    ]);
  });

  it("shows the backend's reason when an upload fails and lets the customer retry", async () => {
    uploadDocument
      .mockRejectedValueOnce({ response: { status: 400, data: { detail: "Unsupported file type." } } })
      .mockResolvedValueOnce({});
    renderPage();
    await chooseClaimAndFile("fir copy", pdf("fir.pdf"));

    fireEvent.click(screen.getByRole("button", { name: /upload selected documents/i }));

    expect(await screen.findByText("Unsupported file type.")).toBeInTheDocument();
    expect(screen.getByText(/0 of 1 uploaded\. 1 failed/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(await screen.findByText(/all 1 document uploaded/i)).toBeInTheDocument();
    expect(uploadDocument).toHaveBeenCalledTimes(2);
  });

  it("starts a fresh selection after 'Upload More Documents'", async () => {
    uploadDocument.mockResolvedValue({});
    renderPage();
    await chooseClaimAndFile("fir copy", pdf("fir.pdf"));
    fireEvent.click(screen.getByRole("button", { name: /upload selected documents/i }));
    await screen.findByText(/all 1 document uploaded/i);

    fireEvent.click(screen.getByRole("button", { name: /upload more documents/i }));

    await waitFor(() => expect(screen.getByRole("button", { name: /upload selected documents/i })).toBeDisabled());
    expect(screen.queryByText("Uploaded")).not.toBeInTheDocument();
  });

  it("explains that a claim is needed when the customer has none", async () => {
    listClaims.mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText(/no claims to attach documents to/i)).toBeInTheDocument();
  });
});
