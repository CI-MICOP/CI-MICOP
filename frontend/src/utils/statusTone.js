// Maps a free-text backend status string (Claim_Status, Document_Status,
// Verification_Status, Policy_Status, ...) to a StatusBadge tone. The
// backend does not constrain these columns to a fixed enum, so this is a
// best-effort presentation heuristic, not a business-rule classification.
export function getStatusTone(value) {
  const text = (value ?? "").toLowerCase();
  if (!text) return "neutral";
  if (/(verified|approved|complete|closed|active|resolved|settled)/.test(text)) return "success";
  if (/(pending|progress|review|investigation|awaiting|open)/.test(text)) return "warning";
  if (/(reject|fail|mismatch|denied|inactive|expired|cancel)/.test(text)) return "danger";
  return "neutral";
}
