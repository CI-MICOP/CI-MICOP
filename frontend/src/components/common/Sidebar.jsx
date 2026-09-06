import { LogOut, ShieldCheck, X } from "lucide-react";
import { NavLink } from "react-router-dom";

import { useAuth } from "../../hooks/useAuth";
import { NAV_CONFIG } from "../../routes/navConfig";
import { getRoleHomePath } from "../../utils/roles";

export default function Sidebar({ isOpen, onClose }) {
  const { role, logout } = useAuth();
  const items = NAV_CONFIG[role] ?? [];
  const basePath = getRoleHomePath(role);

  return (
    <>
      {isOpen && (
        <button
          type="button"
          aria-label="Close navigation"
          onClick={onClose}
          className="fixed inset-0 z-30 bg-slate-900/40 lg:hidden"
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 shrink-0 flex-col border-r border-border
          bg-card transition-transform lg:static lg:translate-x-0
          ${isOpen ? "translate-x-0" : "-translate-x-full"}`}
      >
        <div className="flex items-center justify-between px-5 py-5">
          <div className="flex items-center gap-2">
            <span className="rounded-lg bg-brand-600 p-1.5 text-white">
              <ShieldCheck className="h-5 w-5" aria-hidden="true" />
            </span>
            <span>
              <span className="block text-base font-semibold leading-tight text-ink">CI-MICOP</span>
              <span className="block text-[11px] leading-tight text-muted">
                Smart Claims. Stronger Trust.
              </span>
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close navigation"
            className="text-muted hover:text-ink lg:hidden"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-2" aria-label="Primary">
          <ul className="space-y-1">
            {items.map(({ label, path, icon: Icon }) => {
              // Exact-match whenever another nav item's path is a child of
              // this one (e.g. "claims" vs "claims/new") - otherwise both
              // would highlight together. A path with no such sibling (e.g.
              // "documents", whose only child page "documents/upload" isn't
              // itself a nav item) stays non-exact so it keeps highlighting
              // on its own sub-pages.
              const hasNavChild = items.some(
                (other) => other.path !== path && other.path.startsWith(`${path}/`)
              );
              return (
              <li key={label}>
                <NavLink
                  to={path ? `${basePath}/${path}` : basePath}
                  end={path === "" || hasNavChild}
                  className={({ isActive }) =>
                    `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                      isActive
                        ? "bg-brand-100 text-brand-800"
                        : "text-ink hover:bg-surface"
                    }`
                  }
                >
                  <Icon className="h-4 w-4" aria-hidden="true" />
                  {label}
                </NavLink>
              </li>
              );
            })}
          </ul>
        </nav>

        <div className="border-t border-border px-3 py-3">
          <button
            type="button"
            onClick={logout}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium
              text-ink hover:bg-surface"
          >
            <LogOut className="h-4 w-4" aria-hidden="true" />
            Log out
          </button>
        </div>
      </aside>
    </>
  );
}
