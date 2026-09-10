// Maps the Step 5.4 risk-fusion signal_name values (see
// ai_ml/risk_fusion/signal_schema.py) to officer-facing labels and a
// simple 3-level status vocabulary, so the UI never shows an internal
// identifier like "repair_estimate_anomaly" or a raw feature index.

export const SIGNAL_LABELS = {
  document_consistency_mismatch: "Document Consistency",
  repair_estimate_anomaly: "Repair Estimate",
  evidence_duplication: "Evidence Duplication",
  fraud_screening_rule_score: "Fraud Screening",
  claim_pattern_anomaly: "Claim Pattern",
  document_completeness: "Document Completeness",
  information_quality: "Information Quality",
};

export function signalLabel(signalName) {
  return SIGNAL_LABELS[signalName] ?? signalName;
}

/** "Elevated" / "Moderate" / "Low" - never a raw 0-1 number in the UI. */
export function contributionLevel(signalValue) {
  if (signalValue === null || signalValue === undefined) return null;
  if (signalValue >= 0.7) return "Elevated";
  if (signalValue >= 0.4) return "Moderate";
  return "Low";
}

/** "Warning" / "Elevated" / "Normal" / "Not Available". */
export function signalStatus(signal) {
  if (signal.availability !== "available" || signal.signal_value === null) return "Not Available";
  const level = contributionLevel(signal.signal_value);
  if (level === "Elevated") return "Warning";
  if (level === "Moderate") return "Elevated";
  return "Normal";
}

export const STATUS_TONE = {
  Warning: "danger",
  Elevated: "warning",
  Normal: "success",
  "Not Available": "neutral",
};
