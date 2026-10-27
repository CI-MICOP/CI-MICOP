import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

const auth = { user: null, role: null, logout: vi.fn() };
vi.mock("../../hooks/useAuth", () => ({ useAuth: () => auth }));

import { NAV_CONFIG } from "../../routes/navConfig";
import { getRoleHomePath } from "../../utils/roles";
import AppShell from "../AppShell";

function renderShell(role, path) {
  auth.role = role;
  auth.user = { Username: "dev_user", Email: "dev@example.com", Role: role };
  const base = getRoleHomePath(role);
  return render(
    <MemoryRouter initialEntries={[path ?? base]}>
      <Routes>
        <Route path={base} element={<AppShell />}>
          <Route index element={<p>page content</p>} />
          <Route path="*" element={<p>page content</p>} />
        </Route>
      </Routes>
    </MemoryRouter>
  );
}

const dock = () => screen.getByRole("navigation", { name: "Primary" });
const moreButton = () => within(dock()).queryByRole("button", { name: "More" });
const openProfileMenu = () => fireEvent.click(screen.getByRole("button", { name: /dev_user/ }));
const dockName = (item) => item.dockLabel ?? item.label;
const hrefOf = (role, path) => (path ? `${getRoleHomePath(role)}/${path}` : getRoleHomePath(role));

describe("AppShell floating dock", () => {
  it.each(Object.keys(NAV_CONFIG))("keeps every %s nav destination reachable", (role) => {
    renderShell(role);
    const items = NAV_CONFIG[role];
    const dockItems = items.filter((item) => item.dock);
    const overflow = items.filter((item) => !item.dock && !item.account && !item.hidden);

    // Every dock item shows its label as visible text under the icon.
    for (const item of dockItems) {
      const link = within(dock()).getByRole("link", { name: dockName(item) });
      expect(link).toHaveAttribute("href", hrefOf(role, item.path));
      expect(link).toHaveAttribute("title", item.label);
      expect(within(link).getByText(dockName(item))).toBeVisible();
    }

    if (overflow.length) fireEvent.click(moreButton());
    for (const item of overflow) {
      expect(within(dock()).getByRole("link", { name: item.label })).toHaveAttribute("href", hrefOf(role, item.path));
    }
    expect(within(dock()).getAllByRole("link")).toHaveLength(dockItems.length + overflow.length);

    const account = items.filter((item) => item.account);
    if (account.length) {
      openProfileMenu();
      for (const item of account) {
        expect(screen.getByRole("menuitem", { name: item.label })).toHaveAttribute("href", hrefOf(role, item.path));
      }
    }
  });

  it.each(["Customer", "Admin"])("has no More button for %s - every route fits on the dock", (role) => {
    renderShell(role);
    expect(moreButton()).not.toBeInTheDocument();
  });

  it("gives customers a short dock: Home, Claims, Docs, Policies", () => {
    renderShell("Customer");
    const names = within(dock()).getAllByRole("link").map((link) => link.textContent);
    expect(names).toEqual(["Home", "Claims", "Docs", "Policies"]);
    // Home keeps the original dashboard route.
    expect(within(dock()).getByRole("link", { name: "Home" })).toHaveAttribute("href", "/customer");
    for (const removed of ["Dashboard", "New Claim", "Vehicles", "Support"]) {
      expect(within(dock()).queryByRole("link", { name: removed })).not.toBeInTheDocument();
    }
    // Only Notifications (the header bell) and Settings (no page yet) are off every menu.
    expect(NAV_CONFIG.Customer.filter((item) => item.hidden).map((item) => item.label)).toEqual([
      "Notifications",
      "Settings",
    ]);
  });

  it("shows only dock items until More is opened (Claims Officer)", () => {
    renderShell("Claims Officer");
    expect(within(dock()).getByRole("link", { name: "Queue" })).toBeInTheDocument();
    expect(within(dock()).queryByRole("link", { name: "Escalations" })).not.toBeInTheDocument();

    fireEvent.click(moreButton());
    expect(within(dock()).getByRole("link", { name: "Escalations" })).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(within(dock()).queryByRole("link", { name: "Escalations" })).not.toBeInTheDocument();
  });

  it("keeps Claims active while filing a new claim, without also activating Home", () => {
    renderShell("Customer", "/customer/claims/new");
    expect(within(dock()).getByRole("link", { name: "Claims" })).toHaveAttribute("aria-current", "page");
    expect(within(dock()).getByRole("link", { name: "Home" })).not.toHaveAttribute("aria-current");
  });

  it("activates Survey Reports, not Home, on the surveyor's report history page", () => {
    renderShell("Surveyor", "/surveyor/history");
    expect(within(dock()).getByRole("link", { name: "Survey Reports" })).toHaveAttribute("aria-current", "page");
    expect(within(dock()).getByRole("link", { name: "Home" })).not.toHaveAttribute("aria-current");
  });

  it("gives the surveyor Home, Inspections and Survey Reports on the dock, with no More menu", () => {
    renderShell("Surveyor");
    const links = within(dock()).getAllByRole("link");
    expect(links.map((link) => link.textContent)).toEqual(["Home", "Inspections", "Survey Reports"]);
    expect(within(dock()).getByRole("link", { name: "Inspections" })).toHaveAttribute("href", "/surveyor/claims");
    expect(within(dock()).getByRole("link", { name: "Survey Reports" })).toHaveAttribute("href", "/surveyor/history");
    expect(moreButton()).not.toBeInTheDocument();
    for (const removed of ["Dashboard", "Claims", "Documents", "Alerts", "History", "Profile", "Support"]) {
      expect(within(dock()).queryByRole("link", { name: removed })).not.toBeInTheDocument();
    }
  });

  it("keeps Inspections active on a claim's inspection sub-pages (Surveyor)", () => {
    renderShell("Surveyor", "/surveyor/claims/CLM-1/inspection");
    expect(within(dock()).getByRole("link", { name: "Inspections" })).toHaveAttribute("aria-current", "page");
    expect(within(dock()).getByRole("link", { name: "Home" })).not.toHaveAttribute("aria-current");
  });

  it("keeps a section active on its sub-pages", () => {
    renderShell("Customer", "/customer/documents/upload");
    expect(within(dock()).getByRole("link", { name: "Docs" })).toHaveAttribute("aria-current", "page");
  });

  it("highlights More when the current page lives in the overflow menu", () => {
    renderShell("Claims Officer", "/officer/escalations");
    expect(moreButton().querySelector(".bg-brand-600")).not.toBeNull();
  });
});

describe("AppShell top header", () => {
  it("shows the brand, notifications and profile, and no sidebar", () => {
    renderShell("Customer");
    expect(screen.getByText("CI-MICOP")).toBeInTheDocument();
    expect(screen.getByText("Smart Claims. Stronger Trust.")).toBeInTheDocument();
    expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
    expect(screen.getByText("page content")).toBeInTheDocument();
  });

  it("opens the notifications popover from the bell", () => {
    renderShell("Customer");
    fireEvent.click(screen.getByRole("button", { name: "Notifications" }));
    expect(screen.getByRole("menu", { name: "Notifications" })).toBeInTheDocument();
    expect(screen.getByText("You're all caught up")).toBeInTheDocument();
  });

  it("puts customer Support in the profile menu only, next to Profile and Log out", () => {
    renderShell("Customer");
    const header = screen.getByRole("banner");
    // Not repeated as a header shortcut icon.
    expect(within(header).queryByRole("link", { name: "Support" })).not.toBeInTheDocument();

    openProfileMenu();
    const items = screen.getAllByRole("menuitem").map((item) => item.textContent);
    expect(items).toEqual(["Profile", "Support", "Log out"]);
    expect(screen.getByRole("menuitem", { name: "Support" })).toHaveAttribute("href", "/customer/support");
  });

  it("puts surveyor Support in the profile menu, next to Profile and Log out, and keeps the bell", () => {
    renderShell("Surveyor");
    const header = screen.getByRole("banner");
    expect(within(header).queryByRole("link", { name: "Support" })).not.toBeInTheDocument();
    expect(within(header).getByRole("button", { name: "Notifications" })).toBeInTheDocument();

    openProfileMenu();
    expect(screen.getAllByRole("menuitem").map((item) => item.textContent)).toEqual(["Profile", "Support", "Log out"]);
    expect(screen.getByRole("menuitem", { name: "Support" })).toHaveAttribute("href", "/surveyor/support");
    expect(screen.getByRole("menuitem", { name: "Profile" })).toHaveAttribute("href", "/surveyor/profile");

    fireEvent.click(within(header).getByRole("button", { name: "Notifications" }));
    expect(screen.getByRole("menu", { name: "Notifications" })).toBeInTheDocument();
  });

  it("offers support as a header shortcut when it is not on the dock (Claims Officer)", () => {
    renderShell("Claims Officer");
    const header = screen.getByRole("banner");
    expect(within(header).getByRole("link", { name: "Help & Support" })).toHaveAttribute("href", "/officer/support");
    // Claim Search is on the officer's dock, so it is not repeated here.
    expect(within(header).queryByRole("link", { name: "Claim Search" })).not.toBeInTheDocument();
  });

  it("has no shortcut the role does not already have (Admin)", () => {
    renderShell("Admin");
    const header = screen.getByRole("banner");
    expect(within(header).getAllByRole("link")).toHaveLength(1); // the brand link home
  });

  it("still logs out from the profile menu", () => {
    renderShell("Surveyor");
    auth.logout.mockClear();
    openProfileMenu();
    expect(auth.logout).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("menuitem", { name: "Log out" }));
    expect(auth.logout).toHaveBeenCalledTimes(1);
  });
});
