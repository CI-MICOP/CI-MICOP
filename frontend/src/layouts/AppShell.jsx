import { Outlet } from "react-router-dom";

import FloatingDock from "../components/common/FloatingDock";
import TopHeader from "../components/common/TopHeader";
import { useAuth } from "../hooks/useAuth";
import { NAV_CONFIG } from "../routes/navConfig";
import { getRoleHomePath } from "../utils/roles";

// Nav paths the top header offers as quick search/help shortcuts, when the
// role has them and they are not already on the dock or in the profile menu
// (no duplicates).
const HEADER_SHORTCUT_PATHS = ["search", "support"];

const toLink = (basePath) => ({ label, path, icon }) => ({ label, icon, to: `${basePath}/${path}` });

/**
 * Shared shell for every role: a light top header, a full-width content
 * area, and the floating bottom dock (role-scoped navigation from
 * navConfig.js). Individual pages render their own PageHeader inside the
 * outlet. The bottom padding keeps page content clear of the dock.
 */
export default function AppShell() {
  const { role } = useAuth();
  const items = NAV_CONFIG[role] ?? [];
  const basePath = getRoleHomePath(role);
  const shortcuts = HEADER_SHORTCUT_PATHS.map((path) => items.find((item) => item.path === path))
    .filter((item) => item && !item.dock && !item.account)
    .map(toLink(basePath));
  const accountLinks = items.filter((item) => item.account).map(toLink(basePath));

  return (
    <div className="flex min-h-screen flex-col bg-surface">
      <TopHeader homePath={basePath} shortcuts={shortcuts} accountLinks={accountLinks} />
      <main className="w-full min-w-0 flex-1 px-4 pb-32 pt-4 sm:px-6 sm:pt-6">
        <Outlet />
      </main>
      <FloatingDock items={items} basePath={basePath} />
    </div>
  );
}
