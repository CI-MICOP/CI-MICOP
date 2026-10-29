import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../hooks/useAuth", () => ({
  useAuth: () => ({ user: { Username: "ravi.sv", Employee_ID: "EMP-1" } }),
}));
vi.mock("../../../services/claimService", () => ({ listClaims: vi.fn() }));
vi.mock("../../../services/surveyorService", () => ({ getMyInspections: vi.fn() }));

import { listClaims } from "../../../services/claimService";
import { getMyInspections } from "../../../services/surveyorService";
import SurveyorDashboardPage from "../DashboardPage";

const CLAIMS = [
  { Claim_ID: "CLM-1", Claim_Number: "CLM-2026-0001", Claim_Date: "2026-09-01", Claim_Type: "Own Damage", Claim_Status: "Under Review" },
  { Claim_ID: "CLM-2", Claim_Number: "CLM-2026-0002", Claim_Date: "2026-09-05", Claim_Type: "Theft", Claim_Status: "Approved" },
];
const INSPECTIONS = [
  { Inspection_ID: "INSP-1", Claim_ID: "CLM-1", Inspection_Date: "2026-09-03", Inspection_Status: "Completed", Survey_Report_Submitted: true },
  { Inspection_ID: "INSP-2", Claim_ID: "CLM-2", Inspection_Date: "2026-09-07", Inspection_Status: "In Progress", Survey_Report_Submitted: false },
  { Inspection_ID: "INSP-3", Claim_ID: "CLM-3", Inspection_Date: "2026-09-08", Inspection_Status: "Assigned", Survey_Report_Submitted: false },
];

function renderPage() {
  return render(
    <MemoryRouter>
      <SurveyorDashboardPage />
    </MemoryRouter>
  );
}

function statValue(label) {
  return screen.getByText(label).nextElementSibling.textContent;
}

describe("SurveyorDashboardPage (Home)", () => {
  beforeEach(() => {
    listClaims.mockResolvedValue(CLAIMS);
    getMyInspections.mockResolvedValue(INSPECTIONS);
  });

  it("keeps the three statistic cards with their computed values", async () => {
    renderPage();
    await screen.findByText("Total Inspections");
    expect(statValue("Total Inspections")).toBe("3");
    expect(statValue("Reports Submitted")).toBe("1");
    expect(statValue("Reports Pending")).toBe("2");
  });

  it("removes Quick Actions, Inspection Overview and the Assigned Claims summary card", async () => {
    renderPage();
    await screen.findByText("Total Inspections");
    expect(screen.queryByText("Quick Actions")).not.toBeInTheDocument();
    expect(screen.queryByText("Inspection Overview")).not.toBeInTheDocument();
    expect(screen.queryByText("Assigned Claims")).not.toBeInTheDocument();
    expect(screen.queryByText("My Assigned Claims")).not.toBeInTheDocument();
  });

  it("shows My Inspections with the existing records, statuses and links", async () => {
    renderPage();
    const panel = (await screen.findByRole("heading", { name: "My Inspections" })).closest("div").parentElement;
    expect(within(panel).getByText("CLM-2026-0001")).toBeInTheDocument();
    expect(within(panel).getByText("CLM-2026-0002")).toBeInTheDocument();
    expect(within(panel).getByText("In Progress")).toBeInTheDocument();
    expect(within(panel).getByRole("link", { name: "View all" })).toHaveAttribute("href", "/surveyor/claims");
    expect(within(panel).getAllByRole("link", { name: "View" })[0]).toHaveAttribute("href", "/surveyor/claims/CLM-2");
  });

  it("keeps Recent Activity", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { name: "Recent Activity" })).toBeInTheDocument();
    expect(screen.getByText("Inspection completed for claim CLM-1 — report submitted")).toBeInTheDocument();
  });

  it("says no inspections are assigned when there are none", async () => {
    listClaims.mockResolvedValue([]);
    getMyInspections.mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText("No inspections assigned yet.")).toBeInTheDocument();
    expect(statValue("Total Inspections")).toBe("0");
  });

  it("does not add a Back button - this task's Back button is Claims Officer only", async () => {
    renderPage();
    await screen.findByText("Total Inspections");
    expect(screen.queryByRole("button", { name: /back/i })).not.toBeInTheDocument();
  });
});
