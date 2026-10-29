import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../hooks/useAuth", () => ({
  useAuth: () => ({ user: { Username: "priya.r", Customer_ID: "TEST-CUST-002" } }),
}));
vi.mock("../../../services/claimService", () => ({ listClaims: vi.fn() }));
vi.mock("../../../services/vehicleService", () => ({ getMyVehicles: vi.fn() }));
vi.mock("../../../services/policyService", () => ({ getMyPolicies: vi.fn() }));
vi.mock("../../../services/documentService", () => ({ listMyDocuments: vi.fn() }));

import { listClaims } from "../../../services/claimService";
import { listMyDocuments } from "../../../services/documentService";
import { getMyPolicies } from "../../../services/policyService";
import { getMyVehicles } from "../../../services/vehicleService";
import CustomerDashboardPage from "../DashboardPage";

function renderPage() {
  return render(
    <MemoryRouter>
      <CustomerDashboardPage />
    </MemoryRouter>
  );
}

describe("CustomerDashboardPage (Home)", () => {
  beforeEach(() => {
    listClaims.mockResolvedValue([]);
    getMyVehicles.mockResolvedValue([]);
    getMyPolicies.mockResolvedValue([]);
    listMyDocuments.mockResolvedValue([]);
  });

  it("shows a 'File a New Claim' action that links to the existing New Claim page", async () => {
    renderPage();
    const link = await screen.findByRole("link", { name: /file a new claim/i });
    expect(link).toHaveAttribute("href", "/customer/claims/new");
  });

  it("the action is visible alongside the dashboard stats, not instead of them", async () => {
    renderPage();
    await screen.findByRole("link", { name: /file a new claim/i });
    expect(screen.getByText("Total Claims")).toBeInTheDocument();
  });

  it("does not add a Back button - this task's Back button is Claims Officer only", async () => {
    renderPage();
    await screen.findByText("Total Claims");
    expect(screen.queryByRole("button", { name: /back/i })).not.toBeInTheDocument();
  });
});
