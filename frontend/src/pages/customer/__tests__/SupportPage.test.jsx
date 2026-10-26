import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import SupportPage from "../SupportPage";

function renderPage() {
  return render(
    <MemoryRouter>
      <SupportPage />
    </MemoryRouter>
  );
}

describe("Customer SupportPage", () => {
  it("says RC, licence and policy copies are required with every claim, even when the insurer holds records", () => {
    renderPage();
    expect(screen.getByText("What should I submit for this claim?")).toBeInTheDocument();
    expect(screen.getByText(/with every claim: a copy of the driving licence/i)).toBeInTheDocument();
    expect(screen.getByText(/still required even if the insurer holds the details/i)).toBeInTheDocument();
    expect(screen.getByText(/is read for the check and is not kept/i)).toBeInTheDocument();
    expect(screen.queryByText(/if you provided it/i)).not.toBeInTheDocument();
  });

  it("explains camera-only accident photos, that upload is not verification, and missing records", () => {
    renderPage();
    expect(screen.getByText("Why can't I choose accident photos from my gallery?")).toBeInTheDocument();
    expect(screen.getByText("Does uploading a document mean it has been verified?")).toBeInTheDocument();
    expect(screen.getByText(/different from a record your insurer doesn't hold/i)).toBeInTheDocument();
    expect(screen.getByText(/nothing is decided automatically/i)).toBeInTheDocument();
  });

  it("does not refer to the removed sidebar", () => {
    renderPage();
    expect(screen.queryByText(/sidebar/i)).not.toBeInTheDocument();
  });
});
