import { AlertTriangle, Info, ShieldQuestion } from "lucide-react";

// Step 5.4/5.5 human-in-the-loop wording is fixed and must appear on
// every AI Insights surface (see docs/project_documentation/
// AI_OFFICER_INTEGRATION.md, Section 10). Never edit these strings to
// sound more conclusive - "high risk" must never read as "confirmed".
const VARIANTS = {
  default: {
    icon: Info,
    tone: "border-brand-200 bg-brand-50 text-brand-800",
    iconTone: "text-brand-600",
    message: "AI-assisted analysis only. Final claim decision remains with the Claims Officer.",
  },
  highRiskLowConfidence: {
    icon: AlertTriangle,
    tone: "border-amber-200 bg-amber-50 text-amber-900",
    iconTone: "text-warning",
    message: "High risk does not mean fraud. Additional human investigation is required.",
  },
  insufficientEvidence: {
    icon: ShieldQuestion,
    tone: "border-slate-300 bg-slate-50 text-ink",
    iconTone: "text-muted",
    message: "Insufficient evidence for a reliable AI assessment.",
  },
};

/**
 * Fixed human-in-the-loop disclaimer banner. `variant` only changes which
 * of the three pre-approved messages is shown - the underlying principle
 * (AI never decides) is identical in every variant.
 */
export default function HumanReviewNotice({ variant = "default", className = "" }) {
  const config = VARIANTS[variant] ?? VARIANTS.default;
  const Icon = config.icon;
  return (
    <p className={`flex items-start gap-2 rounded-card border p-3 text-sm ${config.tone} ${className}`}>
      <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${config.iconTone}`} aria-hidden="true" />
      <span>{config.message}</span>
    </p>
  );
}
