import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";

import Card from "./Card";

/**
 * Generic KPI tile. Renders whatever value/trend it is given - it never
 * invents figures itself, so it stays safe to use before real data
 * (claims, risk scores, etc.) is wired up in later steps.
 */
export default function StatCard({
  label,
  value,
  icon: Icon,
  trend,
  tone = "neutral",
  actionLabel,
  to,
}) {
  const trendColor =
    tone === "success" ? "text-success" : tone === "danger" ? "text-danger" : "text-muted";

  return (
    <Card className="flex flex-col justify-between">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-muted">{label}</p>
          <p className="mt-1 text-2xl font-semibold text-ink">{value}</p>
          {trend && <p className={`mt-1 text-xs ${trendColor}`}>{trend}</p>}
        </div>
        {Icon && (
          <span className="rounded-lg bg-brand-50 p-2 text-brand-600">
            <Icon className="h-5 w-5" aria-hidden="true" />
          </span>
        )}
      </div>
      {actionLabel && to && (
        <Link
          to={to}
          className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:text-brand-700"
        >
          {actionLabel}
          <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      )}
    </Card>
  );
}
