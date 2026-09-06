import { ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";

/** items: [{ label, to? }] - the last item is rendered as plain text. */
export default function Breadcrumbs({ items }) {
  return (
    <nav aria-label="Breadcrumb">
      <ol className="flex items-center gap-1.5 text-sm text-muted">
        {items.map((item, index) => {
          const isLast = index === items.length - 1;
          return (
            <li key={item.label} className="flex items-center gap-1.5">
              {item.to && !isLast ? (
                <Link to={item.to} className="hover:text-ink">
                  {item.label}
                </Link>
              ) : (
                <span className={isLast ? "font-medium text-ink" : ""}>{item.label}</span>
              )}
              {!isLast && <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
