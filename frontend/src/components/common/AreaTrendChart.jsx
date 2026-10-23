import { colors } from "../../styles/tokens";

/**
 * Small area chart for a monthly count series. points: [{ key, label,
 * count }] - the same series the dashboards already compute. Only the
 * month labels are rendered as text, as with the previous bar version.
 */
export default function AreaTrendChart({ points }) {
  const max = Math.max(1, ...points.map((p) => p.count));
  const width = 100;
  const height = 40;
  const step = points.length > 1 ? width / (points.length - 1) : width;
  const coords = points.map((p, i) => [i * step, height - (p.count / max) * (height - 4)]);
  const line = coords.map(([x, y], i) => `${i ? "L" : "M"}${x},${y}`).join(" ");
  const area = `${line} L${width},${height} L0,${height} Z`;

  return (
    <div>
      <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className="h-32 w-full" aria-hidden="true">
        <defs>
          <linearGradient id="area-trend-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={colors.brand[500]} stopOpacity="0.35" />
            <stop offset="100%" stopColor={colors.brand[500]} stopOpacity="0.02" />
          </linearGradient>
        </defs>
        <path d={area} fill="url(#area-trend-fill)" />
        <path d={line} fill="none" stroke={colors.brand[600]} strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="mt-1.5 flex justify-between">
        {points.map((point) => (
          <span key={point.key} className="text-xs text-muted">
            {point.label}
          </span>
        ))}
      </div>
    </div>
  );
}
