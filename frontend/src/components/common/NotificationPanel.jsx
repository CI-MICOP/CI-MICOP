import { Bell } from "lucide-react";

import EmptyState from "./EmptyState";

/**
 * Dropdown panel of notifications. Renders whatever `items` it is given
 * (empty by default) - real notification data is wired up in a later step.
 */
export default function NotificationPanel({ items = [], onClose }) {
  return (
    <div
      role="menu"
      aria-label="Notifications"
      className="absolute right-0 top-full z-40 mt-2 w-80 rounded-card border border-border bg-card shadow-soft"
    >
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <p className="text-sm font-semibold text-ink">Notifications</p>
        <button type="button" onClick={onClose} className="text-xs text-muted hover:text-ink">
          Close
        </button>
      </div>
      <div className="max-h-80 overflow-y-auto">
        {items.length === 0 ? (
          <EmptyState icon={Bell} title="You're all caught up" message="No new notifications." />
        ) : (
          <ul>
            {items.map((item) => (
              <li key={item.id} className="border-b border-border px-4 py-3 last:border-0">
                <p className="text-sm text-ink">{item.message}</p>
                {item.timestamp && <p className="mt-0.5 text-xs text-muted">{item.timestamp}</p>}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
