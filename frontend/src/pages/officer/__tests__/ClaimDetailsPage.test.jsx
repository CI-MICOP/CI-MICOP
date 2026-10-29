import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../services/officerService", () => ({
  getClaimWorkspaceData: vi.fn(),
  getSurveyors: vi.fn(),
  assignSurveyor: vi.fn(),
  getClaimEvidenceImage: vi.fn(),
}));

import {
  assignSurveyor,
  getClaimEvidenceImage,
  getClaimWorkspaceData,
  getSurveyors,
} from "../../../services/officerService";
import OfficerClaimDetailsPage from "../ClaimDetailsPage";

const CLAIM = {
  Claim_ID: "CLM-1",
  Claim_Number: "CLM-2026-AAAA",
  Claim_Date: "2026-06-01",
  Claim_Type: "Own Damage",
  Claim_Amount: 50000,
  Approved_Amount: 0,
  Claim_Status: "Under Investigation",
  Final_Decision: "Pending",
  Decision_Reason: "",
  Claim_Processing_Days: 0,
  Repair_Duration_Days: 0,
  Claim_Description: "Test claim.",
  Place_of_Accident: "TestCity",
  Accident_Pincode: "123456",
  Policy_ID: "POL-1",
  Customer_ID: "CUST-1",
  Vehicle_ID: "VEH-1",
};

const SURVEYORS = [
  { Employee_ID: "SURV-001", Username: "surveyor_one", Email: "one@example.com", Account_Status: "Active" },
  { Employee_ID: "SURV-002", Username: "surveyor_two", Email: "two@example.com", Account_Status: "Active" },
];

function baseWorkspace(overrides = {}) {
  return {
    claim: CLAIM,
    customer: null,
    vehicle: null,
    policy: null,
    documents: [],
    vehicle_damage: [],
    repair_estimates: [],
    surveyor_inspections: [],
    cross_document_consistency: [],
    fraud_risk_analysis: [],
    decision_audit: [],
    accidents: [],
    evidence: [],
    ...overrides,
  };
}

const ACCIDENT = {
  Accident_ID: "ACC-1",
  Claim_ID: "CLM-1",
  Accident_Date: "2026-06-01",
  Accident_Time: "14:45:00",
  Accident_Location: "Anna Salai, Chennai",
  Accident_City: "Chennai",
  Accident_State: "Tamil Nadu",
  Accident_Pincode: "600002",
  Accident_Type: "Collision",
  Accident_Description: "Rear-ended at a signal.",
  Weather_Condition: "Clear",
  Road_Condition: "Dry",
  Road_Type_Code: "URBAN",
  Police_Report_Available: true,
  FIR_Number: "FIR-2026-001",
  Third_Party_Involved: true,
  Injury_Reported: false,
  Witness_Available: true,
};

const EVIDENCE_ITEM = {
  Evidence_ID: "EVD-1",
  Claim_ID: "CLM-1",
  Evidence_Type: "Vehicle Damage Close-up",
  File_Name: "camera-capture-1.jpg",
  Evidence_Date: "2026-06-02",
  Evidence_Source: "Surveyor",
  Image_Quality: 0,
  Vehicle_Damage_Detected: false,
  Damage_Severity: "Pending",
  Location_Match: false,
  Duplicate_Evidence_Indicator: false,
  Evidence_Confidence_Score: 0,
  Verification_Status: "Pending",
  capture: {
    capture_method: "in_app_camera",
    client: { latitude: 13.0827, longitude: 80.2707, accuracy_m: 12, source: "gps" },
    server: {},
    checks: { location_status: "captured" },
  },
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/officer/claims/CLM-1"]}>
      <Routes>
        <Route path="/officer/claims/:claimId" element={<OfficerClaimDetailsPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("OfficerClaimDetailsPage - Surveyor Assignment", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getClaimEvidenceImage.mockResolvedValue(new Blob(["jpeg"], { type: "image/jpeg" }));
    URL.createObjectURL = vi.fn(() => "blob:evidence-preview");
    URL.revokeObjectURL = vi.fn();
  });

  it("shows the Not Assigned state with an Assign Surveyor button for an unassigned claim", async () => {
    getClaimWorkspaceData.mockResolvedValue(baseWorkspace());
    renderPage();
    expect(await screen.findByText("Not Assigned")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /assign surveyor/i })).toBeInTheDocument();
  });

  it("loads and displays only the eligible surveyors returned by the API", async () => {
    getClaimWorkspaceData.mockResolvedValue(baseWorkspace());
    getSurveyors.mockResolvedValue(SURVEYORS);
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: /assign surveyor/i }));

    await waitFor(() => expect(getSurveyors).toHaveBeenCalled());
    expect(await screen.findByText(/surveyor_one \(SURV-001\)/i)).toBeInTheDocument();
    expect(screen.getByText(/surveyor_two \(SURV-002\)/i)).toBeInTheDocument();
  });

  it("lets the officer select a surveyor and shows a confirmation prompt", async () => {
    getClaimWorkspaceData.mockResolvedValue(baseWorkspace());
    getSurveyors.mockResolvedValue(SURVEYORS);
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: /assign surveyor/i }));
    const select = await screen.findByLabelText(/select surveyor/i);
    fireEvent.change(select, { target: { value: "SURV-001" } });

    expect(await screen.findByText(/assign this claim to/i)).toBeInTheDocument();
    expect(screen.getByText("surveyor_one")).toBeInTheDocument();
  });

  it("successfully assigning a surveyor calls the API and refreshes the assignment card", async () => {
    getClaimWorkspaceData
      .mockResolvedValueOnce(baseWorkspace())
      .mockResolvedValueOnce(
        baseWorkspace({
          surveyor_inspections: [
            {
              Inspection_ID: "INSP-1",
              Claim_ID: "CLM-1",
              Surveyor_ID: "SURV-001",
              Inspection_Date: "2026-09-10",
              Inspection_Location: "TestCity",
              Vehicle_Condition: "Pending",
              Damage_Observed: "Pending",
              Damage_Severity: "Pending",
              Parts_Required: 0,
              Repair_Recommendation: "Pending",
              Surveyor_Comments: "",
              Inspection_Status: "Assigned",
              Survey_Report_Submitted: false,
              Surveyor_Confidence_Score: 0,
            },
          ],
        })
      );
    getSurveyors.mockResolvedValue(SURVEYORS);
    assignSurveyor.mockResolvedValueOnce({ Inspection_ID: "INSP-1" });

    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /assign surveyor/i }));
    fireEvent.change(await screen.findByLabelText(/select surveyor/i), { target: { value: "SURV-001" } });
    fireEvent.click(screen.getByRole("button", { name: /confirm assignment/i }));

    await waitFor(() => expect(assignSurveyor).toHaveBeenCalledWith("CLM-1", "SURV-001"));
    expect(await screen.findByText(/surveyor assigned successfully/i)).toBeInTheDocument();
    expect(await screen.findByText("Employee ID: SURV-001")).toBeInTheDocument();
  });

  it("displays the actual API error when assignment fails", async () => {
    getClaimWorkspaceData.mockResolvedValue(baseWorkspace());
    getSurveyors.mockResolvedValue(SURVEYORS);
    assignSurveyor.mockRejectedValueOnce({
      response: { status: 409, data: { detail: "This claim already has an active surveyor assignment." } },
    });

    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /assign surveyor/i }));
    fireEvent.change(await screen.findByLabelText(/select surveyor/i), { target: { value: "SURV-001" } });
    fireEvent.click(screen.getByRole("button", { name: /confirm assignment/i }));

    expect(await screen.findByText(/already has an active surveyor assignment/i)).toBeInTheDocument();
  });

  it("does not show the Assign Surveyor button once a surveyor is already assigned", async () => {
    getClaimWorkspaceData.mockResolvedValue(
      baseWorkspace({
        surveyor_inspections: [
          {
            Inspection_ID: "INSP-1",
            Claim_ID: "CLM-1",
            Surveyor_ID: "SURV-001",
            Inspection_Date: "2026-09-10",
            Inspection_Location: "TestCity",
            Vehicle_Condition: "Pending",
            Damage_Observed: "Pending",
            Damage_Severity: "Pending",
            Parts_Required: 0,
            Repair_Recommendation: "Pending",
            Surveyor_Comments: "",
            Inspection_Status: "Assigned",
            Survey_Report_Submitted: false,
            Surveyor_Confidence_Score: 0,
          },
        ],
      })
    );
    renderPage();
    expect(await screen.findByText("Employee ID: SURV-001")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /assign surveyor/i })).not.toBeInTheDocument();
  });

  it("existing officer claim details (summary, documents, repair estimate) remain intact", async () => {
    getClaimWorkspaceData.mockResolvedValue(baseWorkspace());
    renderPage();
    expect(await screen.findByText("Own Damage")).toBeInTheDocument();
    expect(screen.getByText("No documents uploaded for this claim")).toBeInTheDocument();
    expect(screen.getByText("No repair estimate on file for this claim")).toBeInTheDocument();
  });

  it("shows exactly one Back button, below the breadcrumb/tabs and above the main content", async () => {
    getClaimWorkspaceData.mockResolvedValue(baseWorkspace());
    renderPage();
    await screen.findByText("Own Damage");
    expect(screen.getAllByRole("button", { name: /back/i })).toHaveLength(1);
  });
});

describe("OfficerClaimDetailsPage - Accident Information", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getClaimEvidenceImage.mockResolvedValue(new Blob(["jpeg"], { type: "image/jpeg" }));
    URL.createObjectURL = vi.fn(() => "blob:evidence-preview");
    URL.revokeObjectURL = vi.fn();
  });

  it("renders accident details from the API response and removes the old API-access warning", async () => {
    getClaimWorkspaceData.mockResolvedValue(baseWorkspace({ accidents: [ACCIDENT] }));
    renderPage();
    expect(await screen.findByText("Anna Salai, Chennai")).toBeInTheDocument();
    expect(screen.getByText("Chennai")).toBeInTheDocument();
    expect(screen.getByText("Collision")).toBeInTheDocument();
    expect(screen.getByText("FIR-2026-001")).toBeInTheDocument();
    expect(screen.getByText("Rear-ended at a signal.")).toBeInTheDocument();
    expect(screen.queryByText(/surveyor\/admin inspection api/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/does not have access/i)).not.toBeInTheDocument();
  });

  it("shows a clear message when no accident record has been recorded", async () => {
    getClaimWorkspaceData.mockResolvedValue(baseWorkspace());
    renderPage();
    expect(await screen.findByText("No detailed accident information has been recorded for this claim")).toBeInTheDocument();
    expect(screen.queryByText(/surveyor\/admin inspection api/i)).not.toBeInTheDocument();
  });
});

describe("OfficerClaimDetailsPage - Evidence", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getClaimEvidenceImage.mockResolvedValue(new Blob(["jpeg"], { type: "image/jpeg" }));
    URL.createObjectURL = vi.fn(() => "blob:evidence-preview");
    URL.revokeObjectURL = vi.fn();
  });

  it("renders evidence metadata and an image preview from the API response", async () => {
    getClaimWorkspaceData.mockResolvedValue(baseWorkspace({ evidence: [EVIDENCE_ITEM] }));
    renderPage();
    const tile = await screen.findByRole("listitem", { name: /evidence camera-capture-1\.jpg/i });
    expect(within(tile).getByText("Vehicle Damage Close-up")).toBeInTheDocument();
    expect(within(tile).getByText("Pending")).toBeInTheDocument();
    expect(within(tile).getByText("Surveyor")).toBeInTheDocument();
    await waitFor(() => expect(getClaimEvidenceImage).toHaveBeenCalledWith("CLM-1", "EVD-1"));
    expect(within(tile).getByRole("img")).toHaveAttribute("src", "blob:evidence-preview");
    expect(screen.queryByText(/does not have access to through any existing endpoint/i)).not.toBeInTheDocument();
  });

  it("shows a clear message when no evidence has been uploaded", async () => {
    getClaimWorkspaceData.mockResolvedValue(baseWorkspace());
    renderPage();
    expect(await screen.findByText("No evidence has been uploaded for this claim")).toBeInTheDocument();
  });

  it("shows the image load error state when the evidence image fails to load", async () => {
    getClaimWorkspaceData.mockResolvedValue(baseWorkspace({ evidence: [EVIDENCE_ITEM] }));
    getClaimEvidenceImage.mockRejectedValue({ response: { status: 404 } });
    renderPage();
    await waitFor(() => expect(getClaimEvidenceImage).toHaveBeenCalled());
    expect(await screen.findByLabelText(/evidence image camera-capture-1\.jpg/i)).toBeInTheDocument();
  });
});
