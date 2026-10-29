import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../hooks/useAuth", () => ({ useAuth: () => ({ user: { Employee_ID: "EMP-1" } }) }));
vi.mock("../../../services/claimService", () => ({
  getClaimById: vi.fn().mockResolvedValue({
    Claim_ID: "DEV-CLAIM-001",
    Claim_Number: "DEV-CLAIM-001",
    Claim_Date: "2026-08-20",
    Claim_Status: "Under Review",
    Claim_Type: "Own Damage",
    Claim_Amount: 125000,
    Customer_ID: "DEV-CUST-001",
    Vehicle_ID: "DEV-VEH-001",
    Policy_ID: "DEV-POL-001",
  }),
}));
vi.mock("../../../services/surveyorService", () => ({
  getAssignedClaimDetail: vi.fn(),
  listClaimDocuments: vi.fn(),
  getClaimDocumentContent: vi.fn(),
}));

const DETAIL = {
    accidents: [
      {
        Accident_Date: "2026-08-19",
        Accident_Time: "10:30:00",
        Accident_Location: "Anna Salai",
        Accident_City: "Chennai",
        Accident_State: "Tamil Nadu",
        Accident_Type: "Collision",
        Weather_Condition: "Clear",
        Road_Condition: "Dry",
        Police_Report_Available: false,
        FIR_Number: null,
        Third_Party_Involved: false,
        Injury_Reported: false,
        Witness_Available: true,
        Accident_Description: "Rear-ended at a signal.",
      },
    ],
    evidence: [],
    repair_estimates: [],
    inspections: [NEW_INSPECTION],
    workflow: workflow("new"),
};
vi.mock("../../../services/documentService", () => ({ listDocumentsByClaim: vi.fn() }));

import { NEW_INSPECTION, schedule, workflow } from "../../../components/surveyor/__tests__/workflowFixture";
import { listDocumentsByClaim } from "../../../services/documentService";
import { getAssignedClaimDetail, getClaimDocumentContent, listClaimDocuments } from "../../../services/surveyorService";
import SurveyorClaimDetailsPage from "../ClaimDetailsPage";

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/surveyor/claims/DEV-CLAIM-001"]}>
      <Routes>
        <Route path="/surveyor/claims/:claimId" element={<SurveyorClaimDetailsPage />} />
      </Routes>
    </MemoryRouter>
  );
}

// Only RC, Driving Licence and Insurance Policy are ever returned by the
// real API (services/surveyor_documents.py) - FIR and Repair Estimate are
// excluded server-side, so this fixture never includes them.
const DOCUMENTS = {
  claim_id: "DEV-CLAIM-001",
  documents: [
    { document_id: "DOC-RC", document_type: "RC", submitted_date: "2026-08-20", availability: "available", media_type: "application/pdf", verification_status: "Pending" },
    { document_id: null, document_type: "Driving Licence", submitted_date: null, availability: "not_uploaded", media_type: null, verification_status: null },
    { document_id: "DOC-POL", document_type: "Insurance Policy", submitted_date: "2026-08-20", availability: "available", media_type: "image/png", verification_status: "Verified" },
  ],
};

const documentsPanel = () => screen.getByRole("heading", { name: "Claim Documents" }).closest("div.rounded-card");

describe("SurveyorClaimDetailsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getAssignedClaimDetail.mockResolvedValue(DETAIL);
    listClaimDocuments.mockResolvedValue(DOCUMENTS);
    URL.createObjectURL = vi.fn(() => "blob:document");
    URL.revokeObjectURL = vi.fn();
  });


  it("shows only Claim Information and Accident Information, full width", async () => {
    renderPage();
    const claimInfo = await screen.findByRole("heading", { name: "Claim Information" });
    expect(screen.getByRole("heading", { name: "Accident Information" })).toBeInTheDocument();
    expect(screen.getByText("Rear-ended at a signal.")).toBeInTheDocument();
    // No two-column grid with a side column any more.
    expect(claimInfo.closest(".lg\\:col-span-2")).toBeNull();
    expect(claimInfo.closest(".lg\\:grid-cols-3")).toBeNull();
  });

  it("removes the side cards and the Documents section", async () => {
    renderPage();
    await screen.findByRole("heading", { name: "Claim Information" });
    for (const removed of ["Documents", "Inspection", "Vehicle Damage", "Evidence", "Repair Estimate"]) {
      expect(screen.queryByRole("heading", { name: removed })).not.toBeInTheDocument();
    }
    expect(screen.queryByRole("link", { name: /open inspection workspace|view damage assessment|view evidence|view repair estimate/i })).not.toBeInTheDocument();
    expect(listDocumentsByClaim).not.toHaveBeenCalled();
  });

  it("has no Repair Estimate tab and labels the breadcrumb Assigned Inspections", async () => {
    renderPage();
    await screen.findByRole("heading", { name: "Claim Information" });
    const tabs = screen.getByRole("navigation", { name: "Claim sections" });
    expect(tabs).not.toHaveTextContent("Repair Estimate");
    expect(tabs).toHaveTextContent("Survey Report");
    expect(screen.getByRole("link", { name: "Assigned Inspections" })).toHaveAttribute("href", "/surveyor/claims");
  });

  it("ends with a Next button to Inspection and no Back button", async () => {
    renderPage();
    const steps = await screen.findByRole("navigation", { name: "Claim steps" });
    expect(within(steps).getByRole("link", { name: /next/i })).toHaveAttribute("href", "/surveyor/claims/DEV-CLAIM-001/inspection");
    expect(within(steps).queryByRole("link", { name: /back/i })).not.toBeInTheDocument();
  });

  it("before the scheduled date: claim details stay readable, Next is disabled with the schedule", async () => {
    getAssignedClaimDetail.mockResolvedValue({ ...DETAIL, workflow: workflow("new", { schedule: schedule({ reached: false }) }) });
    renderPage();
    expect(await screen.findByText("Rear-ended at a signal.")).toBeInTheDocument();
    const steps = screen.getByRole("navigation", { name: "Claim steps" });
    expect(within(steps).getByRole("button", { name: /next/i })).toBeDisabled();
    expect(within(steps).queryByRole("link", { name: /next/i })).not.toBeInTheDocument();
    expect(screen.getAllByText(/will become available on 28 October 2026/i).length).toBeGreaterThanOrEqual(2); // banner + reason
    const tabs = within(screen.getByRole("navigation", { name: "Claim sections" }));
    expect(tabs.queryByRole("link", { name: "Inspection" })).not.toBeInTheDocument();
  });

  it("has no editable fields - claim details are read-only for the surveyor", async () => {
    const { container } = renderPage();
    await screen.findByRole("heading", { name: "Claim Information" });
    expect(container.querySelectorAll("input, select, textarea")).toHaveLength(0);
  });

  it("keeps Claim Documents locked before the scheduled date and never requests them", async () => {
    getAssignedClaimDetail.mockResolvedValue({ ...DETAIL, workflow: workflow("new", { schedule: schedule({ reached: false }) }) });
    renderPage();
    await screen.findByRole("heading", { name: "Claim Documents" });
    expect(documentsPanel()).toHaveTextContent(/become accessible on the scheduled inspection date/i);
    expect(within(documentsPanel()).queryByRole("button")).not.toBeInTheDocument();
    expect(listClaimDocuments).not.toHaveBeenCalled();
    expect(within(screen.getByRole("navigation", { name: "Claim steps" })).getByRole("button", { name: /next/i })).toBeDisabled();
  });

  it("unlocks Claim Documents when the scheduled start passes, without a reload", async () => {
    const serverTime = new Date();
    const startsAt = new Date(serverTime.getTime() + 150);
    getAssignedClaimDetail.mockResolvedValue({
      ...DETAIL,
      workflow: workflow("new", {
        schedule: schedule({ reached: false, startsAt: startsAt.toISOString(), serverTime: serverTime.toISOString() }),
      }),
    });
    renderPage();
    await screen.findByRole("heading", { name: "Claim Documents" });
    expect(listClaimDocuments).not.toHaveBeenCalled();
    expect(await screen.findByRole("list", { name: "Claim documents" }, { timeout: 2000 })).toBeInTheDocument();
    expect(listClaimDocuments).toHaveBeenCalledWith("DEV-CLAIM-001");
  });

  it("shows each document's real availability and verification status from the server, and excludes FIR/Repair Estimate", async () => {
    renderPage();
    const list = await screen.findByRole("list", { name: "Claim documents" });
    const row = (name) => within(list).getByText(name).closest("li");
    expect(within(row("Registration Certificate (RC)")).getByText("Available")).toBeInTheDocument();
    expect(within(row("Registration Certificate (RC)")).getByText("Verification pending")).toBeInTheDocument();
    expect(within(row("Driving Licence (DL)")).getByText("Not uploaded")).toBeInTheDocument();
    expect(within(row("Insurance Policy")).getByText("Verification: Verified")).toBeInTheDocument();
    // Only documents with a file can be opened; nothing offers a download.
    expect(within(list).getAllByRole("button", { name: /^view /i }).map((b) => b.getAttribute("aria-label"))).toEqual([
      "View Registration Certificate (RC)",
      "View Insurance Policy",
    ]);
    expect(within(list).queryByText(/accident photo/i)).not.toBeInTheDocument();
    expect(within(list).queryByText(/^FIR$/)).not.toBeInTheDocument();
    expect(within(list).queryByText(/repair estimate/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /download/i })).not.toBeInTheDocument();
  });

  it("opens a document in the viewer as often as needed and returns to Claim Details", async () => {
    getClaimDocumentContent.mockResolvedValue(new Blob(["%PDF-1.7"], { type: "application/pdf" }));
    renderPage();
    const view = await screen.findByRole("button", { name: "View Registration Certificate (RC)" });
    for (let opened = 1; opened <= 2; opened += 1) {
      fireEvent.click(view);
      const dialog = await screen.findByRole("dialog", { name: "Registration Certificate (RC)" });
      expect(await within(dialog).findByTitle("Registration Certificate (RC)")).toHaveAttribute("src", "blob:document");
      fireEvent.click(within(dialog).getByRole("button", { name: /back to claim details/i }));
      await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
      expect(getClaimDocumentContent).toHaveBeenCalledTimes(opened);
    }
    expect(getClaimDocumentContent).toHaveBeenCalledWith("DEV-CLAIM-001", "DOC-RC");
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:document");
    expect(screen.getByRole("heading", { name: "Claim Information" })).toBeInTheDocument();
  });

  it("shows an image document as an image", async () => {
    getClaimDocumentContent.mockResolvedValue(new Blob(["png"], { type: "image/png" }));
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "View Insurance Policy" }));
    expect(await within(screen.getByRole("dialog")).findByRole("img", { name: "Insurance Policy" })).toHaveAttribute("src", "blob:document");
  });

  it.each([
    [{ response: { status: 404, data: new Blob([JSON.stringify({ detail: "The file for this document is not available." })]) } }, "The file for this document is not available."],
    [{ response: { status: 401, data: new Blob([]) } }, "Your session has expired. Please sign in again to view this document."],
    [{ response: { status: 415, data: new Blob(["not json"]) } }, "This document cannot be previewed in the browser."],
    [{}, "Unable to connect to the CI-MICOP server. Please try again."],
  ])("explains a document that cannot be shown (%#)", async (error, message) => {
    getClaimDocumentContent.mockRejectedValue(error);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "View Registration Certificate (RC)" }));
    expect(await within(screen.getByRole("dialog")).findByRole("alert")).toHaveTextContent(message);
  });

  it("shows the server's refusal when the documents cannot be listed", async () => {
    listClaimDocuments.mockRejectedValue({ response: { status: 404, data: { detail: "Claim not found" } } });
    renderPage();
    expect(await screen.findByText("Unable to load the claim documents")).toBeInTheDocument();
  });
});
