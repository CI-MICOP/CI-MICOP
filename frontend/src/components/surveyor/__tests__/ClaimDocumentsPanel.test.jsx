import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../services/surveyorService", () => ({
  listClaimDocuments: vi.fn(),
  getClaimDocumentContent: vi.fn(),
}));

import { getClaimDocumentContent, listClaimDocuments } from "../../../services/surveyorService";
import ClaimDocumentsPanel from "../ClaimDocumentsPanel";

const UNLOCKED = { workflow: true, scheduleReached: true };
const LOCKED_SCHEDULED = { workflow: true, scheduleReached: false, schedule: { scheduled_date: "2026-11-01" } };

// The real API (backend/app/services/surveyor_documents.py) never returns
// anything but these three types - FIR, Repair Estimate, Survey Report and
// accident photos are excluded server-side before this component ever sees
// a response. RC/Driving Licence/Insurance Policy copies are now stored as
// real files on upload (services/document_upload.py), so a fresh one comes
// back "available"; a row with no file (e.g. one uploaded before copies
// were kept) comes back "unavailable" - never falsely "available".
const ALLOWED_TYPES_RESPONSE = {
  claim_id: "CLM-1",
  documents: [
    { document_id: "DOC-RC", document_type: "RC", submitted_date: "2026-10-01", availability: "available", media_type: "application/pdf", verification_status: "Pending" },
    { document_id: null, document_type: "Driving Licence", submitted_date: null, availability: "not_uploaded", media_type: null, verification_status: null },
    { document_id: "DOC-POL", document_type: "Insurance Policy", submitted_date: "2026-10-02", availability: "available", media_type: "application/pdf", verification_status: "Verified" },
  ],
};

const LEGACY_NO_FILE_RESPONSE = {
  claim_id: "CLM-1",
  documents: [
    {
      document_id: "DOC-OLD-RC",
      document_type: "RC",
      submitted_date: "2026-01-05",
      availability: "unavailable",
      media_type: null,
      verification_status: "Pending",
    },
    { document_id: null, document_type: "Driving Licence", submitted_date: null, availability: "not_uploaded", media_type: null, verification_status: null },
    { document_id: null, document_type: "Insurance Policy", submitted_date: null, availability: "not_uploaded", media_type: null, verification_status: null },
  ],
};

function renderPanel(progress = UNLOCKED) {
  return render(<ClaimDocumentsPanel claimId="CLM-1" progress={progress} />);
}

describe("ClaimDocumentsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("stays locked and never requests documents before the scheduled date", () => {
    renderPanel(LOCKED_SCHEDULED);
    expect(screen.getByText(/become accessible on the scheduled inspection date/i)).toBeInTheDocument();
    expect(listClaimDocuments).not.toHaveBeenCalled();
  });

  it("lists only RC, Driving Licence and Insurance Policy - never FIR, Repair Estimate or any other type", async () => {
    listClaimDocuments.mockResolvedValue(ALLOWED_TYPES_RESPONSE);
    renderPanel();
    const list = await screen.findByRole("list", { name: "Claim documents" });
    expect(within(list).getByText("Registration Certificate (RC)")).toBeInTheDocument();
    expect(within(list).getByText("Driving Licence (DL)")).toBeInTheDocument();
    expect(within(list).getByText("Insurance Policy")).toBeInTheDocument();
    expect(within(list).getAllByRole("listitem")).toHaveLength(3);
    expect(within(list).queryByText(/^FIR$/)).not.toBeInTheDocument();
    expect(within(list).queryByText(/repair estimate/i)).not.toBeInTheDocument();
    expect(within(list).queryByText(/survey report/i)).not.toBeInTheDocument();
    expect(within(list).queryByText(/accident photo/i)).not.toBeInTheDocument();
  });

  it("does not show a View button for a document with no file behind it, and never says it is available", async () => {
    listClaimDocuments.mockResolvedValue(LEGACY_NO_FILE_RESPONSE);
    renderPanel();
    const list = await screen.findByRole("list", { name: "Claim documents" });
    const rcRow = within(list).getByText("Registration Certificate (RC)").closest("li");
    expect(within(rcRow).getByText("Unavailable")).toBeInTheDocument();
    expect(within(rcRow).queryByRole("button")).not.toBeInTheDocument();
  });

  it("shows RC as available and openable once its file is actually stored", async () => {
    listClaimDocuments.mockResolvedValue(ALLOWED_TYPES_RESPONSE);
    renderPanel();
    const list = await screen.findByRole("list", { name: "Claim documents" });
    const rcRow = within(list).getByText("Registration Certificate (RC)").closest("li");
    expect(within(rcRow).getByText("Available")).toBeInTheDocument();
    expect(within(rcRow).getByRole("button", { name: "View Registration Certificate (RC)" })).toBeInTheDocument();
  });

  it("does not show a View button for a document that was never uploaded", async () => {
    listClaimDocuments.mockResolvedValue(ALLOWED_TYPES_RESPONSE);
    renderPanel();
    const list = await screen.findByRole("list", { name: "Claim documents" });
    const dlRow = within(list).getByText("Driving Licence (DL)").closest("li");
    expect(within(dlRow).getByText("Not uploaded")).toBeInTheDocument();
    expect(within(dlRow).queryByRole("button")).not.toBeInTheDocument();
  });

  it("lets an authorized surveyor open an allowed document that has a real stored file", async () => {
    listClaimDocuments.mockResolvedValue(ALLOWED_TYPES_RESPONSE);
    getClaimDocumentContent.mockResolvedValue(new Blob(["%PDF-1.7"], { type: "application/pdf" }));
    URL.createObjectURL = vi.fn(() => "blob:document");
    URL.revokeObjectURL = vi.fn();
    renderPanel();
    const view = await screen.findByRole("button", { name: "View Insurance Policy" });
    fireEvent.click(view);
    const dialog = await screen.findByRole("dialog", { name: "Insurance Policy" });
    expect(await within(dialog).findByTitle("Insurance Policy")).toHaveAttribute("src", "blob:document");
    expect(getClaimDocumentContent).toHaveBeenCalledWith("CLM-1", "DOC-POL");
  });

  it("never fabricates a download link - no document offers one", async () => {
    listClaimDocuments.mockResolvedValue(ALLOWED_TYPES_RESPONSE);
    renderPanel();
    await screen.findByRole("list", { name: "Claim documents" });
    expect(screen.queryByRole("link", { name: /download/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /download/i })).not.toBeInTheDocument();
  });
});
