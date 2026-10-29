import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../hooks/useAuth", () => ({
  useAuth: () => ({ user: { Username: "officer1" } }),
}));
vi.mock("../../../services/officerService", () => ({
  listClaimsForProcessing: vi.fn(),
}));

import { listClaimsForProcessing } from "../../../services/officerService";
import OfficerDashboardPage from "../DashboardPage";

// Claim_Status is the real, persisted signal (see utils/claimWorkflow.js):
// the decision endpoint sets it to "Completed" once a claim is approved,
// so CLM-1 (still awaiting review) and CLM-2 (approved and completed)
// differ in Claim_Status itself, not just Final_Decision.
const CLAIMS = [
  { Claim_ID: "CLM-1", Claim_Number: "CLM-2026-0001", Customer_ID: "CUST-1", Claim_Type: "Own Damage", Claim_Date: "2026-10-01", Claim_Status: "Under Review", Final_Decision: "Pending" },
  { Claim_ID: "CLM-2", Claim_Number: "CLM-2026-0002", Customer_ID: "CUST-2", Claim_Type: "Theft", Claim_Date: "2026-10-05", Claim_Status: "Completed", Final_Decision: "Approved" },
];

function renderPage() {
  return render(
    <MemoryRouter>
      <OfficerDashboardPage />
    </MemoryRouter>
  );
}

describe("OfficerDashboardPage", () => {
  beforeEach(() => {
    listClaimsForProcessing.mockResolvedValue(CLAIMS);
  });

  it("removes the eight specified sections", async () => {
    renderPage();
    await screen.findByText("My Work Queue");

    for (const heading of [
      "Decisions Today",
      "Fraud Risk Distribution",
      "AI Risk Insights Summary",
      "Fraud Alerts",
      "RFI Pending",
      "Average TAT",
      "Claims Trend (last 6 months)",
      "Claim Status Overview",
    ]) {
      expect(screen.queryByText(heading)).not.toBeInTheDocument();
    }
  });

  it("still shows the remaining dashboard content: stats and the work queue", async () => {
    renderPage();
    expect(await screen.findByText("Pending Claims")).toBeInTheDocument();
    expect(screen.getByText("Overdue Claims")).toBeInTheDocument();
    expect(screen.getByText("My Work Queue")).toBeInTheDocument();
    expect(screen.getByText("CLM-2026-0001")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View all" })).toHaveAttribute("href", "/officer/queue");
  });

  it("counts only claims without a final decision as pending", async () => {
    renderPage();
    const pendingCard = (await screen.findByText("Pending Claims")).closest("div");
    expect(pendingCard).toHaveTextContent("1");
  });

  it("preserves the page header, welcome message and navigation link to the queue", async () => {
    renderPage();
    expect(await screen.findByText(/welcome, officer1/i)).toBeInTheDocument();
    expect(screen.getByText("Claims processing command center.")).toBeInTheDocument();
  });

  it("does not show a Back button on the dashboard, unlike other officer pages", async () => {
    renderPage();
    await screen.findByText("Track Claims");
    expect(screen.queryByRole("button", { name: /back/i })).not.toBeInTheDocument();
  });

  it("shows a Track Claims card with real Under Review and Completed counts, and links to Queue and Claims", async () => {
    renderPage();
    const card = (await screen.findByText("Track Claims")).closest("div");

    const underReview = within(card).getByText("Under Review").closest("div");
    expect(underReview).toHaveTextContent("1");
    expect(within(underReview).getByRole("link", { name: /View Queue/ })).toHaveAttribute("href", "/officer/queue");

    const completed = within(card).getByText("Completed").closest("div");
    expect(completed).toHaveTextContent("1");
    expect(within(completed).getByRole("link", { name: /View Claims/ })).toHaveAttribute("href", "/officer/claims");
  });

  it("never double-counts a claim between the Under Review and Completed buckets", async () => {
    renderPage();
    const card = (await screen.findByText("Track Claims")).closest("div");
    const underReviewCount = Number(within(card).getByText("Under Review").closest("div").querySelector("p.text-2xl").textContent);
    const completedCount = Number(within(card).getByText("Completed").closest("div").querySelector("p.text-2xl").textContent);
    expect(underReviewCount + completedCount).toBe(CLAIMS.length);
  });
});
