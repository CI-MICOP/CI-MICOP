// Maps a raw Axios error into a user-facing message. Never surfaces
// backend stack traces or raw HTTP detail to the UI.
export function getAuthErrorMessage(error) {
  if (!error?.response) {
    return "Unable to connect to the CI-MICOP server. Please try again.";
  }

  switch (error.response.status) {
    case 401:
      return "Invalid username or password.";
    case 403:
      return "Your account is inactive. Please contact an administrator.";
    case 429:
      return "Too many failed login attempts. Please wait a few minutes and try again.";
    default:
      return "Something went wrong. Please try again.";
  }
}

/** For a failed document upload (POST /documents). */
export function getUploadErrorMessage(error) {
  if (!error?.response) {
    return "Unable to connect to the CI-MICOP server.";
  }
  // The backend's validation messages here (unsupported type, oversized
  // file, ...) are already written to be shown directly to the customer.
  return error.response.data?.detail || "This document could not be uploaded. Please try again.";
}

/** Same idea as getAuthErrorMessage, for general data-fetching calls. */
export function getApiErrorMessage(error) {
  if (!error?.response) {
    return "Unable to connect to the CI-MICOP server. Please try again.";
  }

  switch (error.response.status) {
    case 403:
      return "You don't have access to this record.";
    case 404:
      return "The requested record could not be found.";
    default:
      return "Something went wrong while loading this data.";
  }
}
