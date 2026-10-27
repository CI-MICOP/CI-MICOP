import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../services/surveyorService", () => ({ getActiveInspections: vi.fn() }));

import { schedule } from "../../../components/surveyor/__tests__/workflowFixture";
import { getActiveInspections } from "../../../services/surveyorService";
import SurveyorClaimsListPage from "../ClaimsListPage";

const ROW = {
  inspection: { Inspection_ID: "INSP-1", Claim_ID: "DEV-CLAIM-001", Inspection_Date: "2026-10-28", Inspection_Status: "Scheduled" },
  claim: {
    Claim_ID: "DEV-CLAIM-001",
    Claim_Number: "DEV-CLAIM-001",
    Customer_ID: "DEV-CUST-001",
    Vehicle_ID: "DEV-VEH-001",
    Claim_Date: "2026-08-20",
    Claim_Type: "Own Damage",
    Claim_Amount: 125000,
    Claim_Status: "Under Review",
  },
  schedule: schedule({ reached: false }),
};

function renderPage() {
  return render(
    <MemoryRouter>
      <SurveyorClaimsListPage />
    </MemoryRouter>
  );
}

describe("SurveyorClaimsListPage (active inspections)", () => {
  beforeEach(() => {
    getActiveInspections.mockResolvedValue([ROW]);
  });

  it("lists the server's active inspections with View Details as a button-styled link", async () => {
    renderPage();
    const link = await screen.findByRole("link", { name: "View Details" });
    expect(link).toHaveAttribute("href", "/surveyor/claims/DEV-CLAIM-001");
    expect(link).toHaveClass("bg-brand-600", "text-white", "rounded-lg");
    expect(screen.getByRole("heading", { name: "Assigned Inspections" })).toBeInTheDocument();
    expect(screen.getByText("Not open yet")).toBeInTheDocument();
    expect(getActiveInspections).toHaveBeenCalledTimes(1);
  });

  it("centres every header over its value so both rows line up", async () => {
    renderPage();
    await screen.findByRole("link", { name: "View Details" });
    const headers = screen.getAllByRole("columnheader");
    expect(headers).toHaveLength(8);
    headers.forEach((header) => expect(header).toHaveClass("text-center", "align-middle"));
    screen.getAllByRole("cell").forEach((cell) => expect(cell).toHaveClass("sm:text-center", "align-middle"));
  });

  it("shows an empty state when there is no active work (submitted claims are not listed)", async () => {
    getActiveInspections.mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText("You have no active inspections.")).toBeInTheDocument();
  });

  it("shows an error with a retry when loading fails", async () => {
    getActiveInspections.mockRejectedValue({ response: { status: 500 } });
    renderPage();
    expect(await screen.findByText("Something went wrong while loading this data.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry|try again/i })).toBeInTheDocument();
  });
});
