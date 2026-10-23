import { MoreHorizontal } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { NavLink, matchPath, useLocation } from "react-router-dom";

/**
 * Floating bottom dock - the app's primary navigation.
 *
 * items: [{ label, dockLabel?, path, icon, dock?, account?, hidden? }] (see
 * routes/navConfig.js). `dock` items are shown on the dock as an icon with a
 * small label underneath (`dockLabel`, or `label` when no short form is
 * set; the full `label` is the hover title). Items with no placement flag
 * go in the overflow menu, which only appears when there are any. basePath
 * is the role's route namespace, e.g. "/customer".
 */

function itemTo(basePath, path) {
  return path ? `${basePath}/${path}` : basePath;
}

// Exact-match whenever another nav item's path is a child of this one (e.g.
// "claims" vs "claims/new") - otherwise both would highlight together. A
// path with no such sibling (e.g. "documents", whose only child page
// "documents/upload" isn't itself a nav item) stays non-exact so it keeps
// highlighting on its own sub-pages.
function isExactMatch(items, path) {
  return path === "" || items.some((other) => other.path !== path && other.path.startsWith(`${path}/`));
}

function isItemActive(items, item, basePath, pathname) {
  return Boolean(
    matchPath({ path: itemTo(basePath, item.path), end: isExactMatch(items, item.path) }, pathname)
  );
}

const buttonBase =
  "group flex min-w-[2.75rem] flex-col items-center gap-0.5 rounded-2xl px-1 py-1.5 transition-all " +
  "duration-200 ease-out hover:-translate-y-0.5 focus-visible:outline focus-visible:outline-2 " +
  "focus-visible:outline-offset-2 focus-visible:outline-brand-600 motion-reduce:transition-none " +
  "motion-reduce:hover:translate-y-0 sm:min-w-[3.75rem] sm:px-2";

const iconBase = "flex h-8 w-8 items-center justify-center rounded-full transition-colors duration-200";
const activeIcon = "bg-brand-600 text-white shadow-md shadow-brand-600/30";
const idleIcon = "text-muted group-hover:bg-brand-50 group-hover:text-brand-700";
const labelBase = "whitespace-nowrap text-[10px] font-medium leading-tight sm:text-[11px]";

function DockItemContent({ icon: Icon, text, isActive }) {
  return (
    <>
      <span className={`${iconBase} ${isActive ? activeIcon : idleIcon}`}>
        <Icon className="h-[18px] w-[18px]" aria-hidden="true" />
      </span>
      <span className={`${labelBase} ${isActive ? "text-brand-700" : "text-muted group-hover:text-ink"}`}>{text}</span>
    </>
  );
}

export default function FloatingDock({ items, basePath }) {
  const { pathname } = useLocation();
  // The overflow menu remembers the page it was opened on, so navigating
  // anywhere closes it without an extra effect.
  const [moreOpenedAt, setMoreOpenedAt] = useState(null);
  const isMoreOpen = moreOpenedAt === pathname;
  const moreRef = useRef(null);

  const dockItems = items.filter((item) => item.dock);
  const moreItems = items.filter((item) => !item.dock && !item.account && !item.hidden);
  const isMoreActive = moreItems.some((item) => isItemActive(items, item, basePath, pathname));

  // Close the overflow menu on outside click and Escape.
  useEffect(() => {
    if (!isMoreOpen) return undefined;
    const onPointerDown = (event) => {
      if (moreRef.current && !moreRef.current.contains(event.target)) setMoreOpenedAt(null);
    };
    const onKeyDown = (event) => {
      if (event.key === "Escape") setMoreOpenedAt(null);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [isMoreOpen]);

  return (
    <nav
      aria-label="Primary"
      className="fixed left-1/2 z-30 max-w-[calc(100vw-1rem)] -translate-x-1/2"
      style={{ bottom: "calc(24px + env(safe-area-inset-bottom, 0px))" }}
    >
      <ul
        className="flex items-center rounded-full border border-white/70 bg-white/85 px-1.5 py-1 sm:px-2
          shadow-[0_8px_30px_rgb(15_23_42/0.12)] ring-1 ring-slate-900/5 backdrop-blur-md sm:gap-1"
      >
        {dockItems.map(({ label, dockLabel, path, icon }) => (
          <li key={label}>
            <NavLink to={itemTo(basePath, path)} end={isExactMatch(items, path)} title={label} className={buttonBase}>
              {({ isActive }) => <DockItemContent icon={icon} text={dockLabel ?? label} isActive={isActive} />}
            </NavLink>
          </li>
        ))}

        {moreItems.length > 0 && (
          <li ref={moreRef} className="relative">
            <button
              type="button"
              aria-haspopup="true"
              aria-expanded={isMoreOpen}
              onClick={() => setMoreOpenedAt(isMoreOpen ? null : pathname)}
              className={buttonBase}
            >
              <DockItemContent icon={MoreHorizontal} text="More" isActive={isMoreActive} />
            </button>

            {isMoreOpen && (
              <ul
                className="absolute bottom-full right-0 mb-3 max-h-[60vh] w-60 overflow-y-auto rounded-card
                  border border-border bg-card p-1.5 shadow-[0_8px_30px_rgb(15_23_42/0.12)]"
              >
                {moreItems.map(({ label, path, icon: Icon }) => (
                  <li key={label}>
                    <NavLink
                      to={itemTo(basePath, path)}
                      end={isExactMatch(items, path)}
                      className={({ isActive }) =>
                        `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                          isActive ? "bg-brand-100 text-brand-800" : "text-ink hover:bg-surface"
                        }`
                      }
                    >
                      <Icon className="h-4 w-4" aria-hidden="true" />
                      {label}
                    </NavLink>
                  </li>
                ))}
              </ul>
            )}
          </li>
        )}
      </ul>
    </nav>
  );
}
