import { Bell, ChevronDown, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../../hooks/useAuth";
import NotificationPanel from "./NotificationPanel";

function getInitials(name) {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  const initials = parts.length > 1 ? parts[0][0] + parts[1][0] : name.slice(0, 2);
  return initials.toUpperCase();
}

const iconButton = "relative rounded-lg p-2 text-muted hover:bg-surface hover:text-ink";

/**
 * Light top bar: brand, contextual search/help shortcuts, notifications and
 * the profile menu. `shortcuts` and `accountLinks` are existing role nav
 * items ({ label, to, icon }) - e.g. the role's Support page, or Profile in
 * the profile menu - so the header never introduces a destination or label
 * of its own.
 */
export default function TopHeader({ homePath = "/", shortcuts = [], accountLinks = [], hasUnreadNotifications = false }) {
  const { user, role, logout } = useAuth();
  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  return (
    <header className="sticky top-0 z-20 flex items-center gap-2 border-b border-border bg-card/90 px-4 py-3 backdrop-blur-md sm:gap-4 sm:px-6">
      <Link to={homePath} className="flex min-w-0 flex-1 items-center gap-2">
        <span className="shrink-0 rounded-lg bg-brand-600 p-1.5 text-white">
          <ShieldCheck className="h-5 w-5" aria-hidden="true" />
        </span>
        <span className="min-w-0">
          <span className="block text-base font-semibold leading-tight text-ink">CI-MICOP</span>
          <span className="block truncate text-[11px] leading-tight text-muted">Smart Claims. Stronger Trust.</span>
        </span>
      </Link>

      {shortcuts.map(({ label, to, icon: Icon }) => (
        <Link key={to} to={to} aria-label={label} title={label} className={iconButton}>
          <Icon className="h-5 w-5" aria-hidden="true" />
        </Link>
      ))}

      <div className="relative">
        <button
          type="button"
          onClick={() => setIsNotificationsOpen((open) => !open)}
          aria-label="Notifications"
          aria-expanded={isNotificationsOpen}
          className={iconButton}
        >
          <Bell className="h-5 w-5" aria-hidden="true" />
          {hasUnreadNotifications && (
            <span
              aria-hidden="true"
              className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-danger ring-2 ring-card"
            />
          )}
        </button>
        {isNotificationsOpen && (
          <NotificationPanel onClose={() => setIsNotificationsOpen(false)} />
        )}
      </div>

      <div className="relative">
        <button
          type="button"
          onClick={() => setIsProfileOpen((open) => !open)}
          aria-haspopup="menu"
          aria-expanded={isProfileOpen}
          className="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-surface"
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-100 text-xs font-semibold text-brand-700">
            {getInitials(user?.Username)}
          </span>
          <span className="hidden text-left sm:block">
            <span className="block text-sm font-medium text-ink">
              {user?.Username ?? "Account"}
            </span>
            <span className="block text-xs text-muted">{role}</span>
          </span>
          <ChevronDown className="h-4 w-4 text-muted" aria-hidden="true" />
        </button>
        {isProfileOpen && (
          <div
            role="menu"
            className="absolute right-0 top-full z-40 mt-2 w-48 rounded-card border border-border bg-card shadow-soft"
          >
            <div className="border-b border-border px-4 py-3">
              <p className="text-sm font-medium text-ink">{user?.Username}</p>
              <p className="text-xs text-muted">{user?.Email}</p>
            </div>
            {accountLinks.map(({ label, to, icon: Icon }) => (
              <Link
                key={to}
                to={to}
                role="menuitem"
                onClick={() => setIsProfileOpen(false)}
                className="flex items-center gap-2 px-4 py-2.5 text-sm text-ink hover:bg-surface"
              >
                <Icon className="h-4 w-4 text-muted" aria-hidden="true" />
                {label}
              </Link>
            ))}
            <button
              type="button"
              onClick={logout}
              role="menuitem"
              className="w-full px-4 py-2.5 text-left text-sm text-ink hover:bg-surface"
            >
              Log out
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
