import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../services/officerService", () => ({
  getClaimWorkspaceData: vi.fn(),
  getSurveyors: vi.fn(),
  assignSurveyor: vi.fn(),
}));

import {
  assignSurveyor,
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
    ...overrides,
  };
}

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
});
