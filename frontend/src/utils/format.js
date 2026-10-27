const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;

export function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  // A date-only value ("2026-10-28") is a calendar date, parsed as UTC
  // midnight - format it in UTC so no time zone shifts it a day earlier.
  const timeZone = typeof value === "string" && DATE_ONLY.test(value) ? "UTC" : undefined;
  return date.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric", timeZone });
}

export function formatCurrency(value) {
  if (value === null || value === undefined || value === "") return "-";
  const amount = Number(value);
  if (Number.isNaN(amount)) return String(value);
  return amount.toLocaleString("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
}

/** "Renault Duster (KA-01-AB-1234)" style label from a VehicleOut record. */
export function formatVehicleLabel(vehicle) {
  if (!vehicle) return "-";
  const name = [vehicle.Make, vehicle.Model].filter(Boolean).join(" ");
  return vehicle.Registration_Number ? `${name} (${vehicle.Registration_Number})` : name || "-";
}
