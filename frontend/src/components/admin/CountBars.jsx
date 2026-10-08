import Card from "../common/Card";

/**
 * A titled list of "label - count" rows with a proportional bar.
 * rows: [[label, count], ...]
 */
export default function CountBars({ title, rows, emptyMessage = "No records." }) {
  const total = rows.reduce((sum, [, count]) => sum + count, 0);

  return (
    <Card>
      <h2 className="text-sm font-semibold text-ink">{title}</h2>
      {total === 0 ? (
        <p className="mt-3 text-sm text-muted">{emptyMessage}</p>
      ) : (
        <ul className="mt-3 space-y-3">
          {rows.map(([label, count]) => (
            <li key={label}>
              <div className="flex items-center justify-between text-sm">
                <span className="text-ink">{label}</span>
                <span className="font-medium text-ink">{count}</span>
              </div>
              <div className="mt-1 h-2 rounded-full bg-surface">
                <div className="h-2 rounded-full bg-brand-500" style={{ width: `${(count / total) * 100}%` }} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
