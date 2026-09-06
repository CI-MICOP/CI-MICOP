import { useState } from "react";
import { Outlet } from "react-router-dom";

import Sidebar from "../components/common/Sidebar";
import TopHeader from "../components/common/TopHeader";
import { useAuth } from "../hooks/useAuth";

/**
 * Shared desktop-first shell for every role: a fixed sidebar (role-scoped
 * navigation from navConfig.js) plus a top header and scrollable content
 * area. Individual pages render their own PageHeader inside the outlet.
 */
export default function AppShell() {
  const { user, role } = useAuth();
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-surface">
      <Sidebar isOpen={isSidebarOpen} onClose={() => setIsSidebarOpen(false)} />

      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader
          title={`Welcome back, ${user?.Username ?? ""}`}
          subtitle={role}
          onMenuClick={() => setIsSidebarOpen(true)}
        />
        <main className="flex-1 p-4 sm:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
