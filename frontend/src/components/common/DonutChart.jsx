import { colors } from "../../styles/tokens";

const PALETTE = [colors.brand[500], colors.info, colors.warning, colors.danger, colors.brand[800], colors.muted];

/**
 * Donut chart with a legend. rows: [[label, count], ...] - the same shape
 * the status-overview bar lists use, so it renders exactly the labels and
 * counts it is given and nothing else.
 */
export default function DonutChart({ rows }) {
  const total = rows.reduce((sum, [, count]) => sum + count, 0) || 1;
  const radius = 15.915; // circumference ~= 100, so dash lengths are percentages
  const shares = rows.map(([, count]) => (count / total) * 100);
  const offsets = shares.map((_, index) => shares.slice(0, index).reduce((sum, share) => sum + share, 0));

  return (
    <div className="flex flex-col items-center gap-5 sm:flex-row lg:flex-col xl:flex-row">
      <svg viewBox="0 0 42 42" className="h-32 w-32 shrink-0 -rotate-90" aria-hidden="true">
        <circle cx="21" cy="21" r={radius} fill="none" stroke={colors.surface} strokeWidth="6" />
        {rows.map(([label], index) => (
          <circle
            key={label}
            cx="21"
            cy="21"
            r={radius}
            fill="none"
            stroke={PALETTE[index % PALETTE.length]}
            strokeWidth="6"
            strokeDasharray={`${shares[index]} ${100 - shares[index]}`}
            strokeDashoffset={-offsets[index]}
          />
        ))}
      </svg>

      <ul className="w-full min-w-0 space-y-2">
        {rows.map(([label, count], index) => (
          <li key={label} className="flex items-center justify-between gap-3 text-sm">
            <span className="flex min-w-0 items-center gap-2">
              <span
                aria-hidden="true"
                className="h-2.5 w-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: PALETTE[index % PALETTE.length] }}
              />
              <span className="truncate text-ink">{label}</span>
            </span>
            <span className="text-muted">{count}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
