// Device camera and location helpers shared by the customer and surveyor
// photo capture. Photos come only from a live camera stream - there is no
// file or gallery path anywhere.

// Prefer the rear camera on phones; desktops use whatever camera exists.
export const CAMERA_CONSTRAINTS = {
  video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } },
  audio: false,
};

// Mirrors MAX_LOCATION_ACCURACY_M in backend/app/services/evidence_capture.py
// (the backend re-checks every reading).
export const MAX_LOCATION_ACCURACY_M = 100;

const LOCATION_OPTIONS = { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 };
const GEO_ERRORS = { 1: "permission_denied", 2: "position_unavailable", 3: "timeout" };

export const CAMERA_UNSUPPORTED_MESSAGE =
  "This browser cannot open the camera. Use a current browser on a device with a camera (the portal must be opened over HTTPS or on localhost).";

export function cameraSupported() {
  return Boolean(navigator.mediaDevices?.getUserMedia);
}

export function cameraErrorMessage(error) {
  switch (error?.name) {
    case "NotAllowedError":
    case "SecurityError":
      return "Camera access was blocked. Allow camera access for this site in your browser settings, then try again.";
    case "NotFoundError":
    case "OverconstrainedError":
      return "No camera was found on this device. A device with a camera is required to capture photos.";
    case "NotReadableError":
      return "The camera is being used by another application. Close it and try again.";
    default:
      return "The camera could not be started. Please try again.";
  }
}

/** One location reading, resolved (never rejected) with its status. */
export function getLocation() {
  return new Promise((resolve) => {
    if (!navigator.geolocation) {
      resolve({ status: "unsupported" });
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude, accuracy } = position.coords;
        resolve({
          status: accuracy <= MAX_LOCATION_ACCURACY_M ? "captured" : "accuracy_insufficient",
          latitude,
          longitude,
          accuracy,
        });
      },
      (geoError) => resolve({ status: GEO_ERRORS[geoError.code] ?? "position_unavailable" }),
      LOCATION_OPTIONS
    );
  });
}

export function locationMessage(location) {
  switch (location?.status) {
    case "locating":
      return "Getting your location...";
    case "captured":
      return `Location captured (±${Math.round(location.accuracy)} m).`;
    case "accuracy_insufficient":
      return `Location accuracy is ±${Math.round(location.accuracy)} m - not precise enough (±${MAX_LOCATION_ACCURACY_M} m or better is needed). Move to an open area and retry.`;
    case "permission_denied":
      return "Location access is blocked. Allow location access for this site in your browser settings, then retry.";
    case "unsupported":
      return "This browser cannot provide your location.";
    case "position_unavailable":
    case "timeout":
      return "Your location could not be determined. Check that location services are on, then retry.";
    default:
      return "";
  }
}

/** Today's date in India Standard Time, as YYYY-MM-DD. */
export function todayIst() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).format(
    new Date()
  );
}
