import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import ClaimStepNav from "../ClaimStepNav";

const BASE = "/surveyor/claims/CLM-1";

function renderStep(current) {
  render(
    <MemoryRouter>
      <ClaimStepNav claimId="CLM-1" current={current} />
    </MemoryRouter>
  );
  return within(screen.getByRole("navigation", { name: "Claim steps" }));
}

describe("ClaimStepNav", () => {
  it("shows only Next on Claim Details", () => {
    const nav = renderStep("details");
    expect(nav.queryByRole("link", { name: /back/i })).not.toBeInTheDocument();
    expect(nav.getByRole("link", { name: /next/i })).toHaveAttribute("href", `${BASE}/inspection`);
  });

  it.each([
    ["inspection", BASE, `${BASE}/damage`],
    ["damage", `${BASE}/inspection`, `${BASE}/evidence`],
    ["evidence", `${BASE}/damage`, `${BASE}/report`],
  ])("shows Back and Next on %s", (current, back, next) => {
    const nav = renderStep(current);
    expect(nav.getByRole("link", { name: /back/i })).toHaveAttribute("href", back);
    expect(nav.getByRole("link", { name: /next/i })).toHaveAttribute("href", next);
  });

  it("shows only Back on Survey Report, the last section", () => {
    const nav = renderStep("report");
    expect(nav.getByRole("link", { name: /back/i })).toHaveAttribute("href", `${BASE}/evidence`);
    expect(nav.queryByRole("link", { name: /next/i })).not.toBeInTheDocument();
  });

  it("styles Next as the primary button and Back as the secondary one", () => {
    const nav = renderStep("inspection");
    expect(nav.getByRole("link", { name: /next/i })).toHaveClass("bg-brand-600", "text-white");
    expect(nav.getByRole("link", { name: /back/i })).toHaveClass("border", "bg-white");
  });
});
