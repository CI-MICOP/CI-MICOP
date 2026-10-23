import { Link } from "react-router-dom";

/** `compact` stacks the icon above the text, for tight grids such as a
 * dashboard's right panel. Same label, description and destination. */
export default function QuickActionCard({ label, description, icon: Icon, to, onClick, compact = false }) {
  const content = (
    <>
      <span className={`rounded-lg bg-brand-50 p-2 text-brand-600 ${compact ? "self-start" : ""}`}>
        {Icon && <Icon className="h-5 w-5" aria-hidden="true" />}
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-medium text-ink">{label}</span>
        {description && <span className="block text-xs text-muted">{description}</span>}
      </span>
    </>
  );

  const className =
    `flex ${compact ? "flex-col items-start gap-2 p-3" : "items-center gap-3 p-4"} ` +
    "rounded-card border border-border bg-card text-left shadow-soft " +
    "transition-colors hover:border-brand-300 hover:bg-brand-50/40 focus-visible:outline " +
    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600";

  if (to) {
    return (
      <Link to={to} className={className}>
        {content}
      </Link>
    );
  }

  return (
    <button type="button" onClick={onClick} className={className}>
      {content}
    </button>
  );
}
