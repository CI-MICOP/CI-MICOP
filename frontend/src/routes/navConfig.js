// Centralized, role-based navigation. FloatingDock.jsx renders whichever
// list matches the current user's role - no per-role navigation
// components. Paths are relative to each role's route namespace
// (see src/utils/roles.js and AppRoutes.jsx). A path with no page of its
// own resolves to the shared ComingSoonPage.
//
// Placement (FloatingDock.jsx / TopHeader.jsx):
//   dock: true    - shown on the floating dock, under `dockLabel` if set;
//   account: true - shown in the header's profile menu;
//   hidden: true  - not in any menu (covered elsewhere or no page yet);
//   otherwise     - in the dock's overflow ("More") menu.

import {
  BarChart3,
  Bell,
  ClipboardCheck,
  FileBarChart,
  FileText,
  FolderOpen,
  History,
  House,
  KeyRound,
  LayoutDashboard,
  LifeBuoy,
  ListChecks,
  Settings,
  ShieldCheck,
  TrendingUp,
  UserCircle,
  Users,
} from "lucide-react";

export const NAV_CONFIG = {
  Customer: [
    { label: "Home", path: "", icon: House, dock: true },
    // New claims are started from the "File a New Claim" button on My Claims
    // (route claims/new is unchanged), so there is no separate nav item.
    { label: "My Claims", dockLabel: "Claims", path: "claims", icon: FileText, dock: true },
    { label: "Documents", dockLabel: "Docs", path: "documents", icon: FolderOpen, dock: true },
    { label: "Policies", path: "policies", icon: ShieldCheck, dock: true },
    { label: "Profile", path: "profile", icon: UserCircle, account: true },
    { label: "Support", path: "support", icon: LifeBuoy, account: true },
    // Covered by the header bell; the page itself is still routed.
    { label: "Notifications", path: "notifications", icon: Bell, hidden: true },
    // No page yet (ComingSoonPage), so it is kept off the dock.
    { label: "Settings", path: "settings", icon: Settings, hidden: true },
  ],
  Surveyor: [
    { label: "Home", path: "", icon: House, dock: true },
    // Surveyors work on inspections; the route stays `claims`.
    { label: "Inspections", path: "claims", icon: ClipboardCheck, dock: true },
    // The single entry for the inspection and survey-report history page.
    // (A separate "Survey Reports" item pointed at an unbuilt page.)
    { label: "Survey Reports", path: "history", icon: FileBarChart, dock: true },
    { label: "Profile", path: "profile", icon: UserCircle, account: true },
    { label: "Support", path: "support", icon: LifeBuoy, account: true },
    // Covered by the header bell; the page itself is still routed.
    { label: "Notifications", path: "notifications", icon: Bell, hidden: true },
  ],
  "Claims Officer": [
    { label: "Dashboard", path: "", icon: LayoutDashboard, dock: true },
    { label: "My Work Queue", dockLabel: "Queue", path: "queue", icon: ListChecks, dock: true },
    { label: "All Claims", dockLabel: "Claims", path: "claims", icon: FileText, dock: true },
    { label: "Performance Reports", dockLabel: "Reports", path: "performance-reports", icon: TrendingUp, dock: true },
    { label: "Audit Logs", dockLabel: "Audit", path: "audit-logs", icon: History, dock: true },
    { label: "Profile Settings", path: "profile", icon: UserCircle, account: true },
    // Covered by the header's support shortcut icon; the page itself is still routed.
    { label: "Help & Support", path: "support", icon: LifeBuoy, hidden: true },
    // Covered by the header bell; the page itself is still routed.
    { label: "Notifications", path: "notifications", icon: Bell, hidden: true },
  ],
  Admin: [
    { label: "Dashboard", path: "", icon: LayoutDashboard, dock: true },
    { label: "Users", path: "users", icon: Users, dock: true },
    { label: "Roles & Permissions", dockLabel: "Roles", path: "roles-permissions", icon: KeyRound, dock: true },
    { label: "System Reports", dockLabel: "Reports", path: "system-reports", icon: BarChart3, dock: true },
    { label: "Audit Logs", dockLabel: "Audit", path: "audit-logs", icon: History, dock: true },
    { label: "Profile", path: "profile", icon: UserCircle, dock: true },
  ],
};
