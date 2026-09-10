import { NavLink } from "react-router-dom";

const TABS = [
  { key: "details", label: "Claim Details", path: "" },
  { key: "inspection", label: "Inspection", path: "inspection" },
  { key: "damage", label: "Vehicle Damage", path: "damage" },
  { key: "evidence", label: "Evidence", path: "evidence" },
  { key: "repair-estimate", label: "Repair Estimate", path: "repair-estimate" },
  { key: "report", label: "Survey Report", path: "report" },
];

/** Horizontal tab strip for moving between the five views of one claim. */
export default function ClaimTabs({ claimId }) {
  const base = `/surveyor/claims/${claimId}`;
  return (
    <nav className="mb-6 flex gap-1 overflow-x-auto border-b border-border" aria-label="Claim sections">
      {TABS.map((tab) => (
        <NavLink
          key={tab.key}
          to={tab.path ? `${base}/${tab.path}` : base}
          end
          className={({ isActive }) =>
            `shrink-0 border-b-2 px-3 py-2 text-sm font-medium ${
              isActive ? "border-brand-600 text-brand-700" : "border-transparent text-muted hover:text-ink"
            }`
          }
        >
          {tab.label}
        </NavLink>
      ))}
    </nav>
  );
}
