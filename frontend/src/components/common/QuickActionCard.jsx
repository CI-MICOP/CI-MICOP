import { Link } from "react-router-dom";

export default function QuickActionCard({ label, description, icon: Icon, to, onClick }) {
  const content = (
    <>
      <span className="rounded-lg bg-brand-50 p-2 text-brand-600">
        {Icon && <Icon className="h-5 w-5" aria-hidden="true" />}
      </span>
      <span>
        <span className="block text-sm font-medium text-ink">{label}</span>
        {description && <span className="block text-xs text-muted">{description}</span>}
      </span>
    </>
  );

  const className =
    "flex items-center gap-3 rounded-card border border-border bg-card p-4 text-left shadow-soft " +
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
