import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../services/adminService", () => ({
  listAllUsers: vi.fn(),
  getUserById: vi.fn(),
}));
vi.mock("../../../services/officerService", () => ({
  listClaimsForProcessing: vi.fn(),
}));
vi.mock("../../../hooks/useAuth", () => ({
  useAuth: () => ({ user: { Username: "dev_admin", User_ID: "U-ADMIN", Role: "Admin", Account_Status: "Active" } }),
}));

import { getUserById, listAllUsers } from "../../../services/adminService";
import { listClaimsForProcessing } from "../../../services/officerService";
import AdminDashboardPage from "../DashboardPage";
import RolesPermissionsPage from "../RolesPermissionsPage";
import SystemReportsPage from "../SystemReportsPage";
import UserDetailsPage from "../UserDetailsPage";
import UsersPage from "../UsersPage";

function user(index, overrides = {}) {
  return {
    User_ID: `U-${index}`,
    Username: `user_${index}`,
    Role: "Customer",
    Customer_ID: `CUST-${index}`,
    Employee_ID: null,
    Email: `user_${index}@example.com`,
    Phone: "9990000000",
    Account_Status: "Active",
    Login_Status: "Active",
    Last_Login: null,
    Created_Date: "2025-01-01",
    Failed_Login_Count: 0,
    Permission_Level: 1,
    ...overrides,
  };
}

const USERS = [
  user(1),
  user(2, { Account_Status: "Suspended", Failed_Login_Count: 3 }),
  user(3, { Username: "surveyor_a", Role: "Surveyor", Customer_ID: null, Employee_ID: "EMP-3" }),
  user(4, { Username: "officer_a", Role: "Claims Officer", Customer_ID: null, Employee_ID: "EMP-4" }),
  user(5, { Username: "dev_admin", Role: "Admin", Customer_ID: null }),
];

const CLAIMS = [
  { Claim_ID: "C1", Claim_Status: "Under Review", Final_Decision: "Pending", Claim_Type: "Own Damage", Claim_Amount: "50000.00" },
  { Claim_ID: "C2", Claim_Status: "Under Review", Final_Decision: "Approved", Claim_Type: "Own Damage", Claim_Amount: "25000.00" },
  { Claim_ID: "C3", Claim_Status: "Closed", Final_Decision: "Rejected", Claim_Type: "Third Party", Claim_Amount: "10000.00" },
];

function renderAt(path, routePath, element) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path={routePath} element={element} />
      </Routes>
    </MemoryRouter>
  );
}

function card(title) {
  return within(screen.getByRole("heading", { name: title }).closest("div"));
}

describe("Admin pages", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listAllUsers.mockResolvedValue(USERS);
    listClaimsForProcessing.mockResolvedValue(CLAIMS);
  });

  it("dashboard counts users and claims from the API", async () => {
    renderAt("/admin", "/admin", <AdminDashboardPage />);
    expect(await screen.findByText("Welcome, dev_admin")).toBeInTheDocument();
    expect(screen.getByText("User Accounts").nextSibling).toHaveTextContent("5");
    expect(screen.getByText("Active Accounts").nextSibling).toHaveTextContent("4");
    expect(screen.getByText("Not Active").nextSibling).toHaveTextContent("1");
    expect(screen.getByText("Claims").nextSibling).toHaveTextContent("3");
    expect(screen.getByRole("link", { name: /view users/i })).toHaveAttribute("href", "/admin/users");
  });

  it("dashboard shows an error instead of numbers when loading fails", async () => {
    listAllUsers.mockRejectedValue({ response: { status: 500 } });
    renderAt("/admin", "/admin", <AdminDashboardPage />);
    expect(await screen.findByText("Something went wrong while loading this data.")).toBeInTheDocument();
    expect(screen.queryByText("User Accounts")).not.toBeInTheDocument();
  });

  it("users page lists accounts and links each to its details", async () => {
    renderAt("/admin/users", "/admin/users", <UsersPage />);
    expect(await screen.findByText("surveyor_a")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "View Details" })[0]).toHaveAttribute("href", "/admin/users/U-1");
    expect(screen.getByText("Suspended")).toBeInTheDocument();
    expect(screen.getByText("Showing 1-5 of 5")).toBeInTheDocument();
  });

  it("users page filters by search text and by role", async () => {
    renderAt("/admin/users", "/admin/users", <UsersPage />);
    await screen.findByText("surveyor_a");

    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "EMP-4" } });
    expect(screen.getByText("officer_a")).toBeInTheDocument();
    expect(screen.queryByText("surveyor_a")).not.toBeInTheDocument();

    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "" } });
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "Surveyor" } });
    expect(screen.getByText("surveyor_a")).toBeInTheDocument();
    expect(screen.queryByText("officer_a")).not.toBeInTheDocument();
    expect(screen.getByText("Showing 1-1 of 1")).toBeInTheDocument();
  });

  it("users page shows 25 accounts per page", async () => {
    listAllUsers.mockResolvedValue(Array.from({ length: 30 }, (_, i) => user(i + 1)));
    renderAt("/admin/users", "/admin/users", <UsersPage />);
    expect(await screen.findByText("Showing 1-25 of 30")).toBeInTheDocument();
    expect(screen.queryByText("user_26")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Showing 26-30 of 30")).toBeInTheDocument();
    expect(screen.getByText("user_26")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  it("user details page shows one account and never offers an edit action", async () => {
    getUserById.mockResolvedValue(USERS[1]);
    renderAt("/admin/users/U-2", "/admin/users/:userId", <UserDetailsPage />);
    expect(await screen.findByRole("heading", { name: "user_2" })).toBeInTheDocument();
    expect(getUserById).toHaveBeenCalledWith("U-2");
    expect(screen.getByText("Suspended")).toBeInTheDocument();
    expect(screen.getByText("Failed Logins in a Row").nextSibling).toHaveTextContent("3");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /back to users/i })).toHaveAttribute("href", "/admin/users");
  });

  it("user details page reports an unknown user", async () => {
    getUserById.mockRejectedValue({ response: { status: 404 } });
    renderAt("/admin/users/NOPE", "/admin/users/:userId", <UserDetailsPage />);
    expect(await screen.findByText("The requested record could not be found.")).toBeInTheDocument();
  });

  it("roles page describes the four roles with their account counts", async () => {
    renderAt("/admin/roles-permissions", "/admin/roles-permissions", <RolesPermissionsPage />);
    expect(await screen.findByText("2 account(s)")).toBeInTheDocument(); // Customer
    for (const role of ["Customer", "Surveyor", "Claims Officer", "Admin"]) {
      expect(screen.getByRole("heading", { name: role })).toBeInTheDocument();
    }
    const roleCard = (role) => within(screen.getByRole("heading", { name: role }).parentElement.parentElement);
    expect(roleCard("Admin").getByText("Record the final decision on a claim (Claims Officer only)")).toBeInTheDocument();
    expect(roleCard("Claims Officer").getByText("Record the final decision on a claim")).toBeInTheDocument();
  });

  it("system reports count users and claims by group", async () => {
    renderAt("/admin/system-reports", "/admin/system-reports", <SystemReportsPage />);
    expect(await screen.findByText("Users by Role")).toBeInTheDocument();
    expect(screen.getByText("Accounts with Failed Logins").nextSibling).toHaveTextContent("1");
    expect(screen.getByText("Total Amount Claimed").nextSibling).toHaveTextContent("85,000");
    expect(card("Claims by Status").getByText("Under Review").nextSibling).toHaveTextContent("2");
    expect(card("Claims by Final Decision").getByText("Pending").nextSibling).toHaveTextContent("1");
    expect(card("Claims by Type").getByText("Third Party").nextSibling).toHaveTextContent("1");
    // Fewer than 200 claims: no "most recent 200 only" caveat.
    expect(screen.queryByText(/most recent 200/)).not.toBeInTheDocument();
  });
});
