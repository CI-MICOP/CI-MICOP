// Display text for an evidence row's capture record (written by the server
// for photos taken with the in-app camera - see
// backend/app/services/evidence_capture.py). Device-reported values are
// labelled as such; nothing is called verified that the server did not check.

const LOCATION_STATUS = {
  captured: "GPS verified",
  map_selected: "Map-selected — GPS not verified",
  unavailable: "Location unavailable",
  accuracy_insufficient: "GPS accuracy insufficient",
};

const CLIENT_TIME_STATUS = {
  consistent: "matches server time",
  inconsistent: "does not match server time",
  missing: "not reported",
  invalid: "not readable",
};

function formatDateTime(value) {
  if (!value) return "Not available";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Kolkata" }) + " IST";
}

export function captureMethodText(capture) {
  return capture ? "In-app camera" : "No in-app capture record (uploaded)";
}

export function locationText(capture) {
  const client = capture?.client;
  if (!capture) return "Not available";
  if (client?.latitude == null) return `Not available (${(client?.error ?? "not provided").replaceAll("_", " ")})`;
  const coords = `${Number(client.latitude).toFixed(6)}, ${Number(client.longitude).toFixed(6)}`;
  // A map-selected point has no GPS accuracy figure - never fabricated.
  if (client.accuracy_m == null) {
    return client.address_label ? `${coords} (${client.address_label})` : coords;
  }
  return `${coords} (±${Math.round(client.accuracy_m)} m)`;
}

export function locationStatusText(capture) {
  if (!capture) return "Not checked";
  return LOCATION_STATUS[capture.checks?.location_status] ?? "Not checked";
}

export function deviceTimeText(capture) {
  if (!capture) return "Not available";
  const status = CLIENT_TIME_STATUS[capture.checks?.client_time_status] ?? "not checked";
  return `${formatDateTime(capture.client?.captured_at)} (${status})`;
}

export function serverTimeText(capture) {
  return capture ? formatDateTime(capture.server?.received_at) : "Not available";
}
