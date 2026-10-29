import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../services/officerService", () => ({
  getClaimWorkspaceData: vi.fn(),
  submitDecision: vi.fn(),
}));

import { getClaimWorkspaceData, submitDecision } from "../../../services/officerService";
import DecisionPage from "../DecisionPage";

const CLAIM = {
  Claim_ID: "CLM-1",
  Claim_Number: "CLM-2026-AAAA",
  Claim_Type: "Own Damage",
  Claim_Amount: 50000,
  Claim_Status: "Under Investigation",
  Final_Decision: "Pending",
  Decision_Date: "2026-08-25",
};

function baseWorkspace(overrides = {}) {
  return {
    claim: CLAIM,
    decision_audit: [],
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/officer/claims/CLM-1/decision"]}>
      <Routes>
        <Route path="/officer/claims/:claimId/decision" element={<DecisionPage />} />
      </Routes>
    </MemoryRouter>
  );
}

function fillReasonAndAmount(reason = "Evidence supports this outcome.", amount = "40000") {
  fireEvent.change(screen.getByLabelText(/decision reason/i), { target: { value: reason } });
  fireEvent.change(screen.getByLabelText(/approved amount/i), { target: { value: amount } });
}

describe("DecisionPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the decision workspace", async () => {
    getClaimWorkspaceData.mockResolvedValue(baseWorkspace());
    renderPage();
    expect(await screen.findByText(/make decision — clm-2026-aaaa/i)).toBeInTheDocument();
  });

  it("renders the real Final_Decision options", async () => {
    getClaimWorkspaceData.mockResolvedValue(baseWorkspace());
    renderPage();
    const select = await screen.findByLabelText(/final decision/i);
    const options = Array.from(select.querySelectorAll("option")).map((o) => o.textContent);
    expect(options).toEqual(expect.arrayContaining(["Approved", "Rejected", "Partially Approved"]));
  });

  it("requires a non-blank decision reason before submission is allowed", async () => {
    getClaimWorkspaceData.mockResolvedValue(baseWorkspace());
    renderPage();
    fireEvent.change(await screen.findByLabelText(/final decision/i), { target: { value: "Approved" } });
    fireEvent.change(screen.getByLabelText(/approved amount/i), { target: { value: "40000" } });
    expect(screen.getByRole("button", { name: /submit decision/i })).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/decision reason/i), { target: { value: "A valid reason." } });
    expect(screen.getByRole("button", { name: /submit decision/i })).not.toBeDisabled();
  });

  it("requires a positive approved amount for an Approved decision", async () => {
    getClaimWorkspaceData.mockResolvedValue(baseWorkspace());
    renderPage();
    fireEvent.change(await screen.findByLabelText(/final decision/i), { target: { value: "Approved" } });
    fireEvent.change(screen.getByLabelText(/decision reason/i), { target: { value: "A valid reason." } });
    fireEvent.change(screen.getByLabelText(/approved amount/i), { target: { value: "0" } });
    expect(screen.getByRole("button", { name: /submit decision/i })).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/approved amount/i), { target: { value: "40000" } });
    expect(screen.getByRole("button", { name: /submit decision/i })).not.toBeDisabled();
  });

  it("submitting a valid decision calls submitDecision with the human-entered fields", async () => {
    getClaimWorkspaceData
      .mockResolvedValueOnce(baseWorkspace())
      .mockResolvedValueOnce(baseWorkspace({ claim: { ...CLAIM, Final_Decision: "Approved" } }));
    submitDecision.mockResolvedValueOnce({ Audit_ID: "AUD-1", Final_Decision: "Approved" });

    renderPage();
    fireEvent.change(await screen.findByLabelText(/final decision/i), { target: { value: "Approved" } });
    fillReasonAndAmount();
    fireEvent.click(screen.getByRole("button", { name: /submit decision/i }));

    await waitFor(() =>
      expect(submitDecision).toHaveBeenCalledWith(
        "CLM-1",
        expect.objectContaining({
          finalDecision: "Approved",
          decisionReason: "Evidence supports this outcome.",
          approvedAmount: "40000",
        })
      )
    );
    expect(await screen.findByText(/decision recorded successfully/i)).toBeInTheDocument();
  });

  it("prevents duplicate submissions while a submission is in progress", async () => {
    getClaimWorkspaceData.mockResolvedValue(baseWorkspace());
    let resolveSubmit;
    submitDecision.mockReturnValueOnce(new Promise((resolve) => { resolveSubmit = resolve; }));

    renderPage();
    fireEvent.change(await screen.findByLabelText(/final decision/i), { target: { value: "Approved" } });
    fillReasonAndAmount();
    const button = screen.getByRole("button", { name: /submit decision/i });
    fireEvent.click(button);
    fireEvent.click(button);
    fireEvent.click(button);

    expect(submitDecision).toHaveBeenCalledTimes(1);
    resolveSubmit({ Audit_ID: "AUD-1" });
    await waitFor(() => expect(submitDecision).toHaveBeenCalledTimes(1));
  });

  it("displays the actual API error when submission fails", async () => {
    getClaimWorkspaceData.mockResolvedValue(baseWorkspace());
    submitDecision.mockRejectedValueOnce({ response: { status: 422, data: { detail: "Invalid decision." } } });

    renderPage();
    fireEvent.change(await screen.findByLabelText(/final decision/i), { target: { value: "Approved" } });
    fillReasonAndAmount();
    fireEvent.click(screen.getByRole("button", { name: /submit decision/i }));

    expect(await screen.findByText("Invalid decision.")).toBeInTheDocument();
  });

  it("displays AI information as supporting recommendation, never as the final decision", async () => {
    getClaimWorkspaceData.mockResolvedValue(
      baseWorkspace({
        decision_audit: [
          {
            Audit_ID: "AUD-1",
            Claim_ID: "CLM-1",
            AI_Recommendation: "Investigate",
            AI_Confidence_Score: 0.72,
            Human_Review_Required: true,
            Final_Decision: "Pending",
            Approved_Amount: 0,
            Decision_Date: "2026-09-01",
            Escalation_Status: "Not Escalated",
          },
        ],
      })
    );
    renderPage();

    expect(await screen.findByText("AI Recommendation (Supporting Information)")).toBeInTheDocument();
    expect(screen.getByText("Investigate")).toBeInTheDocument();
    expect(screen.getByText(/flagged for human review/i)).toBeInTheDocument();
    expect(screen.getByText(/this is a recommendation, not the final decision/i)).toBeInTheDocument();
  });

  it("locks the form and hides the Submit button once a final decision (Approved) is recorded", async () => {
    getClaimWorkspaceData.mockResolvedValue(
      baseWorkspace({
        claim: { ...CLAIM, Final_Decision: "Approved", Decision_Reason: "Fully supported by evidence.", Approved_Amount: 42000 },
        decision_audit: [
          {
            Audit_ID: "AUD-1",
            Claim_ID: "CLM-1",
            AI_Recommendation: "Pending",
            AI_Confidence_Score: 0,
            Human_Review_Required: true,
            Final_Decision: "Approved",
            Decision_Reason: "Fully supported by evidence.",
            Approved_Amount: 42000,
            Officer_Comments: "Standard approval.",
            Decision_Date: "2026-09-01",
            Escalation_Status: "Not Escalated",
          },
        ],
      })
    );
    renderPage();

    expect(await screen.findByText(/final decision recorded\. this claim's decision is locked and cannot be edited\./i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/final decision/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/decision reason/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/approved amount/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/officer comments/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /submit decision/i })).not.toBeInTheDocument();

    // The saved decision is still visible, read-only.
    expect(screen.getByText("Fully supported by evidence.")).toBeInTheDocument();
    expect(screen.getByText("Standard approval.")).toBeInTheDocument();
  });

  it("locks the form once a final decision (Rejected) is recorded", async () => {
    getClaimWorkspaceData.mockResolvedValue(
      baseWorkspace({ claim: { ...CLAIM, Final_Decision: "Rejected", Approved_Amount: 0 } })
    );
    renderPage();

    expect(await screen.findByText(/final decision recorded/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /submit decision/i })).not.toBeInTheDocument();
  });

  it("keeps the claim summary, status and decision history visible while locked", async () => {
    getClaimWorkspaceData.mockResolvedValue(
      baseWorkspace({
        claim: { ...CLAIM, Final_Decision: "Approved" },
        decision_audit: [
          {
            Audit_ID: "AUD-1",
            Claim_ID: "CLM-1",
            AI_Recommendation: "Pending",
            AI_Confidence_Score: 0,
            Human_Review_Required: false,
            Final_Decision: "Approved",
            Approved_Amount: 42000,
            Decision_Date: "2026-09-01",
            Escalation_Status: "Not Escalated",
          },
        ],
      })
    );
    renderPage();

    await screen.findByText(/final decision recorded/i);
    expect(screen.getByText("Claim Summary")).toBeInTheDocument();
    expect(screen.getByText("Under Investigation")).toBeInTheDocument();
    expect(screen.getByText("Decision History")).toBeInTheDocument();
  });

  it("stays locked after the claim is reopened (a fresh fetch returning the same finalized claim)", async () => {
    getClaimWorkspaceData.mockResolvedValue(baseWorkspace({ claim: { ...CLAIM, Final_Decision: "Approved" } }));
    const { unmount } = renderPage();
    await screen.findByText(/final decision recorded/i);
    unmount();

    renderPage();
    expect(await screen.findByText(/final decision recorded/i)).toBeInTheDocument();
  });

  it("does not lock the form for a claim with no final decision yet (Pending)", async () => {
    getClaimWorkspaceData.mockResolvedValue(baseWorkspace());
    renderPage();
    expect(await screen.findByLabelText(/final decision/i)).toBeInTheDocument();
    expect(screen.queryByText(/final decision recorded/i)).not.toBeInTheDocument();
  });

  it("shows a single Back button, and it is unaffected by the decision lock", async () => {
    getClaimWorkspaceData.mockResolvedValue(baseWorkspace({ claim: { ...CLAIM, Final_Decision: "Approved" } }));
    renderPage();
    await screen.findByText(/final decision recorded/i);
    expect(screen.getAllByRole("button", { name: /back/i })).toHaveLength(1);
  });

  it("maps a 409 from the backend (already finalized) to a clear message", async () => {
    getClaimWorkspaceData.mockResolvedValue(baseWorkspace());
    submitDecision.mockRejectedValueOnce({
      response: { status: 409, data: { detail: "This claim's decision has already been finalized and cannot be changed." } },
    });

    renderPage();
    fireEvent.change(await screen.findByLabelText(/final decision/i), { target: { value: "Approved" } });
    fillReasonAndAmount();
    fireEvent.click(screen.getByRole("button", { name: /submit decision/i }));

    expect(await screen.findByText("This claim's decision has already been finalized and cannot be changed.")).toBeInTheDocument();
  });

  it("shows AI information as unavailable when no genuine recommendation exists", async () => {
    getClaimWorkspaceData.mockResolvedValue(
      baseWorkspace({
        decision_audit: [
          {
            Audit_ID: "AUD-SEED",
            Claim_ID: "CLM-1",
            AI_Recommendation: "Pending",
            AI_Confidence_Score: 0,
            Human_Review_Required: true,
            Final_Decision: "Pending",
            Approved_Amount: 0,
            Decision_Date: "2026-08-25",
            Escalation_Status: "Not Escalated",
          },
        ],
      })
    );
    renderPage();

    expect(await screen.findByText(/no ai recommendation is available/i)).toBeInTheDocument();
    expect(screen.queryByText("AI Recommendation")).not.toBeInTheDocument();
  });
});
