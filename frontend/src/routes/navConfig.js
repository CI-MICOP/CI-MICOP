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
  ArrowUpCircle,
  BarChart3,
  Bell,
  Calculator,
  CheckCircle2,
  ClipboardCheck,
  Clock,
  FileBarChart,
  FileCheck2,
  FileText,
  FolderOpen,
  History,
  House,
  KeyRound,
  LayoutDashboard,
  LifeBuoy,
  ListChecks,
  MessageCircle,
  Radar,
  Search,
  Settings,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  UserCircle,
  UserPlus,
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
    { label: "Dashboard", path: "", icon: LayoutDashboard, dock: true },
    { label: "Assigned Claims", dockLabel: "Claims", path: "claims", icon: FileText, dock: true },
    { label: "Inspections", path: "inspections", icon: ClipboardCheck },
    { label: "Documents", path: "documents", icon: FolderOpen },
    { label: "Survey Reports", path: "reports", icon: FileBarChart },
    { label: "History", path: "history", icon: History, dock: true },
    { label: "Notifications", dockLabel: "Alerts", path: "notifications", icon: Bell, dock: true },
    { label: "Profile", path: "profile", icon: UserCircle },
    { label: "Support", path: "support", icon: LifeBuoy, dock: true },
  ],
  "Claims Officer": [
    { label: "Dashboard", path: "", icon: LayoutDashboard, dock: true },
    { label: "My Work Queue", dockLabel: "Queue", path: "queue", icon: ListChecks, dock: true },
    { label: "All Claims", dockLabel: "Claims", path: "claims", icon: FileText, dock: true },
    { label: "Claim Search", dockLabel: "Search", path: "search", icon: Search, dock: true },
    { label: "Assign Surveyor", path: "assign-surveyor", icon: UserPlus },
    { label: "Track Claims", path: "track", icon: Radar },
    { label: "Fraud Risk Panel", path: "fraud-risk", icon: ShieldAlert },
    { label: "AI Risk Insights", path: "ai-insights", icon: Sparkles },
    { label: "Document Consistency", path: "document-consistency", icon: FileCheck2 },
    { label: "Estimate Analysis", path: "estimate-analysis", icon: Calculator },
    { label: "Make Decision", path: "decision", icon: CheckCircle2 },
    { label: "Escalations", path: "escalations", icon: ArrowUpCircle },
    { label: "RFI / Clarifications", path: "rfi", icon: MessageCircle },
    { label: "Performance Reports", dockLabel: "Reports", path: "performance-reports", icon: TrendingUp, dock: true },
    { label: "SLA Reports", path: "sla-reports", icon: Clock },
    { label: "Audit Logs", dockLabel: "Audit", path: "audit-logs", icon: History, dock: true },
    { label: "Notifications", path: "notifications", icon: Bell },
    { label: "Profile Settings", path: "profile", icon: UserCircle },
    { label: "Help & Support", path: "support", icon: LifeBuoy },
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
