import { NavLink } from "react-router-dom";

const TABS = [
  { key: "details", label: "Claim Details", path: "" },
  { key: "fraud-risk", label: "Fraud Risk", path: "fraud-risk" },
  { key: "ai-insights", label: "AI Insights", path: "ai-insights" },
  { key: "consistency", label: "Document Consistency", path: "consistency" },
  { key: "estimate", label: "Estimate Analysis", path: "estimate" },
  { key: "decision", label: "Make Decision", path: "decision" },
];

/** Horizontal tab strip for moving between the views of one claim. */
export default function ClaimTabs({ claimId }) {
  const base = `/officer/claims/${claimId}`;
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
