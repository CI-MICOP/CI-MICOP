import { fireEvent, render, screen } from "@testing-library/react";
import { Link, MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { describe, expect, it } from "vitest";

import BackButton from "../BackButton";

function PageWithQuery() {
  const location = useLocation();
  return (
    <div>
      <p>Page A{location.search}</p>
      <Link to="/b">Go to B</Link>
    </div>
  );
}

function renderWithRealHistory(fallback = "/fallback") {
  return render(
    <MemoryRouter initialEntries={["/a?claimId=CLM-7&filter=pending"]}>
      <Routes>
        <Route path="/a" element={<PageWithQuery />} />
        <Route
          path="/b"
          element={
            <div>
              <p>Page B</p>
              <BackButton fallback={fallback} />
            </div>
          }
        />
        <Route path="/fallback" element={<p>Fallback Page</p>} />
      </Routes>
    </MemoryRouter>
  );
}

function renderDirectAccess(fallback = "/fallback") {
  return render(
    <MemoryRouter initialEntries={["/b"]}>
      <Routes>
        <Route
          path="/b"
          element={
            <div>
              <p>Page B</p>
              <BackButton fallback={fallback} />
            </div>
          }
        />
        <Route path="/fallback" element={<p>Fallback Page</p>} />
      </Routes>
    </MemoryRouter>
  );
}

describe("BackButton", () => {
  it("renders a compact, labeled Back control with a left arrow", () => {
    renderDirectAccess();
    const button = screen.getByRole("button", { name: /back/i });
    expect(button).toBeInTheDocument();
    expect(button.querySelector("svg")).toBeInTheDocument();
  });

  it("returns to the actual previous in-app page when real navigation history exists", () => {
    renderWithRealHistory();
    fireEvent.click(screen.getByRole("link", { name: "Go to B" }));
    expect(screen.getByText("Page B")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /back/i }));
    expect(screen.getByText(/Page A/)).toBeInTheDocument();
  });

  it("preserves query parameters (e.g. claim ID and filters) when returning via real history", () => {
    renderWithRealHistory();
    fireEvent.click(screen.getByRole("link", { name: "Go to B" }));
    fireEvent.click(screen.getByRole("button", { name: /back/i }));
    expect(screen.getByText("Page A?claimId=CLM-7&filter=pending")).toBeInTheDocument();
  });

  it("uses the safe in-app fallback instead of real history when the page was opened directly", () => {
    renderDirectAccess("/fallback");
    fireEvent.click(screen.getByRole("button", { name: /back/i }));
    expect(screen.getByText("Fallback Page")).toBeInTheDocument();
  });

  it("uses the fallback again after a simulated refresh of a directly-opened page (same history key)", () => {
    const { unmount } = renderDirectAccess("/fallback");
    unmount();
    renderDirectAccess("/fallback");
    fireEvent.click(screen.getByRole("button", { name: /back/i }));
    expect(screen.getByText("Fallback Page")).toBeInTheDocument();
  });
});
