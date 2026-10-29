import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../services/officerService", () => ({ listClaimsForProcessing: vi.fn() }));
vi.mock("../../../services/claimService", () => ({ getClaimById: vi.fn() }));
vi.mock("../../../services/customerService", () => ({ getCustomerById: vi.fn() }));
vi.mock("../../../services/vehicleService", () => ({ getVehicleById: vi.fn() }));

import { getClaimById } from "../../../services/claimService";
import { getCustomerById } from "../../../services/customerService";
import { listClaimsForProcessing } from "../../../services/officerService";
import { getVehicleById } from "../../../services/vehicleService";
import WorkQueuePage from "../WorkQueuePage";

// Claim_Status is the real, persisted "still needs review" signal (see
// utils/claimWorkflow.js) - the decision endpoint now sets it to
// "Completed" on approval, so a decided claim's Claim_Status is no longer
// "Under Review". This fixture includes an awaiting-review claim, a
// completed one, and one with a non-"Under Review" status to confirm the
// queue honors the persisted status alone.
const UNDER_REVIEW = { Claim_ID: "CLM-1", Claim_Number: "CLM-2026-0001", Customer_ID: "CUST-1", Vehicle_ID: "VEH-1", Claim_Type: "Own Damage", Claim_Amount: 50000, Claim_Date: "2026-10-01", Claim_Status: "Under Review", Final_Decision: "Pending" };
const COMPLETED = { Claim_ID: "CLM-2", Claim_Number: "CLM-2026-0002", Customer_ID: "CUST-2", Vehicle_ID: "VEH-2", Claim_Type: "Theft", Claim_Amount: 20000, Claim_Date: "2026-10-05", Claim_Status: "Completed", Final_Decision: "Approved" };
const OTHER_STATUS = { Claim_ID: "CLM-3", Claim_Number: "CLM-2026-0003", Customer_ID: "CUST-3", Vehicle_ID: "VEH-3", Claim_Type: "Own Damage", Claim_Amount: 10000, Claim_Date: "2026-10-03", Claim_Status: "Withdrawn", Final_Decision: "Pending" };

function renderPage() {
  return render(
    <MemoryRouter>
      <WorkQueuePage />
    </MemoryRouter>
  );
}

describe("WorkQueuePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getClaimById.mockResolvedValue({ Claim_Processing_Days: 3 });
    getCustomerById.mockResolvedValue({ Customer_Name: "Test Customer" });
    getVehicleById.mockResolvedValue({ Vehicle_Make: "Make", Vehicle_Model: "Model" });
  });

  it("asks the backend for claims with the persisted Under Review status", async () => {
    listClaimsForProcessing.mockResolvedValue([UNDER_REVIEW]);
    renderPage();
    await screen.findByText("CLM-2026-0001");
    expect(listClaimsForProcessing).toHaveBeenCalledWith({ limit: 200, claim_status: "Under Review" });
  });

  it("shows an Under Review claim in the queue", async () => {
    listClaimsForProcessing.mockResolvedValue([UNDER_REVIEW]);
    renderPage();
    expect(await screen.findByText("CLM-2026-0001")).toBeInTheDocument();
  });

  it("excludes a Completed (decided) claim from the active queue, and never duplicates a claim", async () => {
    listClaimsForProcessing.mockResolvedValue([UNDER_REVIEW, COMPLETED]);
    renderPage();
    expect(await screen.findByText("CLM-2026-0001")).toBeInTheDocument();
    expect(screen.queryByText("CLM-2026-0002")).not.toBeInTheDocument();
    expect(screen.getAllByText("CLM-2026-0001")).toHaveLength(1);
  });

  it("excludes a claim whose persisted status is not Under Review, even if undecided", async () => {
    listClaimsForProcessing.mockResolvedValue([UNDER_REVIEW, OTHER_STATUS]);
    renderPage();
    await screen.findByText("CLM-2026-0001");
    expect(screen.queryByText("CLM-2026-0003")).not.toBeInTheDocument();
  });

  it("moves a claim out of the queue once its decision is recorded, after a data refresh", async () => {
    listClaimsForProcessing.mockResolvedValueOnce([UNDER_REVIEW]);
    const { rerender } = renderPage();
    expect(await screen.findByText("CLM-2026-0001")).toBeInTheDocument();

    listClaimsForProcessing.mockResolvedValueOnce([{ ...UNDER_REVIEW, Claim_Status: "Completed", Final_Decision: "Approved" }]);
    rerender(
      <MemoryRouter>
        <WorkQueuePage key="reload" />
      </MemoryRouter>
    );
    await screen.findByText("Your work queue is empty.");
    expect(screen.queryByText("CLM-2026-0001")).not.toBeInTheDocument();
  });

  it("lists every distinct persisted status in the filter dropdown", async () => {
    listClaimsForProcessing.mockResolvedValue([UNDER_REVIEW]);
    renderPage();
    await screen.findByText("CLM-2026-0001");
    const select = screen.getByLabelText("Filter by status");
    expect(within(select).getByRole("option", { name: "Under Review" })).toBeInTheDocument();
  });

  it("shows a single Back button below the page header", async () => {
    listClaimsForProcessing.mockResolvedValue([UNDER_REVIEW]);
    renderPage();
    await screen.findByText("CLM-2026-0001");
    expect(screen.getAllByRole("button", { name: /back/i })).toHaveLength(1);
  });
});
