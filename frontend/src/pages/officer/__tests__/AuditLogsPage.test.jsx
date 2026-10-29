import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../services/officerService", () => ({
  listClaimsForProcessing: vi.fn(),
  getClaimProcessingDetail: vi.fn(),
}));

const auth = { role: "Claims Officer" };
vi.mock("../../../hooks/useAuth", () => ({ useAuth: () => auth }));

import { listClaimsForProcessing } from "../../../services/officerService";
import AuditLogsPage from "../AuditLogsPage";

function renderPage() {
  return render(
    <MemoryRouter>
      <AuditLogsPage />
    </MemoryRouter>
  );
}

// AuditLogsPage is mounted at both /officer/audit-logs and
// /admin/audit-logs (routes/AppRoutes.jsx, pre-existing sharing) - this
// task's Back button must appear for the Claims Officer only, never for
// Admin, so it must not change anything about the Admin dashboard.
describe("AuditLogsPage - Back button is Claims Officer only", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listClaimsForProcessing.mockResolvedValue([]);
  });

  it("shows a single Back button for the Claims Officer", async () => {
    auth.role = "Claims Officer";
    renderPage();
    await screen.findByText("Audit Logs");
    expect(screen.getAllByRole("button", { name: /back/i })).toHaveLength(1);
  });

  it("shows no Back button for Admin, viewing the same shared page", async () => {
    auth.role = "Admin";
    renderPage();
    await screen.findByText("Audit Logs");
    expect(screen.queryByRole("button", { name: /back/i })).not.toBeInTheDocument();
  });
});
