const TONE_CLASSES = {
  success: "bg-green-50 text-success ring-1 ring-inset ring-green-200",
  warning: "bg-amber-50 text-warning ring-1 ring-inset ring-amber-200",
  danger: "bg-red-50 text-danger ring-1 ring-inset ring-red-200",
  info: "bg-blue-50 text-info ring-1 ring-inset ring-blue-200",
  neutral: "bg-slate-100 text-muted ring-1 ring-inset ring-slate-200",
};

/** `tone` picks the color; `label` is the visible text (e.g. a claim status). */
export default function StatusBadge({ label, tone = "neutral" }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${TONE_CLASSES[tone]}`}
    >
      {label}
    </span>
  );
}
