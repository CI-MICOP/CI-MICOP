import { apiClient } from "./apiClient";

export async function getMyInspections() {
  const response = await apiClient.get("/surveyor/inspections");
  return response.data;
}

export async function getAssignedClaimDetail(claimId) {
  const response = await apiClient.get(`/surveyor/claims/${claimId}`);
  return response.data;
}

export async function updateInspection(inspectionId, data) {
  const response = await apiClient.patch(`/surveyor/inspections/${inspectionId}`, data);
  return response.data;
}

// Surveyor_ID is never sent - the backend always derives it from the JWT.
export async function startInspection(claimId) {
  const response = await apiClient.post("/surveyor/inspections", { Claim_ID: claimId });
  return response.data;
}

// Vehicle_ID is never sent - the backend derives it from the claim itself.
export async function createVehicleDamage(payload) {
  const response = await apiClient.post("/surveyor/vehicle-damage", payload);
  return response.data;
}

// Edits an existing vehicle-damage record in place ("Correct this step").
// Claim_ID is never sent - the backend keeps the existing record's own
// claim/vehicle association and never accepts a change to it.
export async function updateVehicleDamage(damageId, payload) {
  const response = await apiClient.patch(`/surveyor/vehicle-damage/${damageId}`, payload);
  return response.data;
}

// Vehicle_ID is never sent - the backend derives it from the claim itself.
export async function createRepairEstimate(payload) {
  const response = await apiClient.post("/surveyor/repair-estimates", payload);
  return response.data;
}

// A photo taken with the in-app camera (POST /surveyor/evidence/capture).
// The device-reported capture time and location go with it; the server
// establishes the surveyor, inspection, source and receipt time itself.
export async function createEvidenceCapture(
  claimId,
  {
    evidenceType,
    evidenceDate,
    photo,
    capturedAt,
    latitude,
    longitude,
    accuracy,
    locationSource,
    addressLabel,
    locationError,
  },
  onProgress
) {
  const formData = new FormData();
  formData.append("claim_id", claimId);
  formData.append("evidence_type", evidenceType);
  if (evidenceDate) formData.append("evidence_date", evidenceDate);
  formData.append("photo", photo, "capture.jpg");
  formData.append("captured_at", capturedAt);
  // A map-selected point has coordinates but never an accuracy figure -
  // send lat/lng whenever they exist, accuracy only when it does too.
  if (latitude != null && longitude != null) {
    formData.append("latitude", String(latitude));
    formData.append("longitude", String(longitude));
    if (accuracy != null) formData.append("accuracy_m", String(accuracy));
  }
  if (locationSource) formData.append("location_source", locationSource);
  if (addressLabel) formData.append("address_label", addressLabel);
  if (locationError) formData.append("location_error", locationError);
  const response = await apiClient.post("/surveyor/evidence/capture", formData, {
    onUploadProgress: (event) => {
      if (onProgress && event.total) onProgress(Math.round((event.loaded / event.total) * 100));
    },
  });
  return response.data;
}

// The surveyor's explicit Keep/un-keep decision for one of their own
// already-saved photos, while the survey report is still editable.
export async function setEvidenceKept(evidenceId, kept) {
  const response = await apiClient.patch(`/surveyor/evidence/${evidenceId}`, { kept });
  return response.data;
}

// Removes one of the surveyor's own saved photos before the survey report
// is submitted. The backend re-enforces this - a submitted report refuses
// the request (409), as does another surveyor's or claim's evidence (404).
export async function deleteEvidence(evidenceId) {
  await apiClient.delete(`/surveyor/evidence/${evidenceId}`);
}

// The Claim Documents panel (Claim Details): the claim's customer documents
// with their real availability. The server checks assignment and the
// scheduled date on every call.
export async function listClaimDocuments(claimId) {
  const response = await apiClient.get(`/surveyor/claims/${claimId}/documents`);
  return response.data;
}

// One claim document for the in-dashboard viewer, as a Blob (fetched with
// the bearer token; there is no public URL). Re-authorised on every call.
export async function getClaimDocumentContent(claimId, documentId) {
  const response = await apiClient.get(`/surveyor/claims/${claimId}/documents/${documentId}/content`, {
    responseType: "blob",
  });
  return response.data;
}

// One of the surveyor's own captured photos, as a Blob (for thumbnails -
// an <img> cannot send the bearer token itself).
export async function getEvidenceImage(evidenceId) {
  const response = await apiClient.get(`/surveyor/evidence/${evidenceId}/image`, { responseType: "blob" });
  return response.data;
}

// Deliberately reopen a completed step ("inspection" or "damage"); the
// server records it and only then accepts changes to that step.
export async function openCorrection(inspectionId, step) {
  const response = await apiClient.post(`/surveyor/inspections/${inspectionId}/corrections`, { step });
  return response.data;
}

export async function closeCorrection(inspectionId, step) {
  const response = await apiClient.delete(`/surveyor/inspections/${inspectionId}/corrections/${step}`);
  return response.data;
}

// Active work: inspections whose report has not been submitted.
export async function getActiveInspections() {
  const response = await apiClient.get("/surveyor/active-inspections");
  return response.data;
}

// History: submitted survey reports.
export async function getSurveyReports() {
  const response = await apiClient.get("/surveyor/survey-reports");
  return response.data;
}

export async function getSubmittedSurveyReport(inspectionId) {
  const response = await apiClient.get(`/surveyor/survey-reports/${inspectionId}/report`);
  return response.data;
}

export async function downloadSubmittedSurveyReportPdf(inspectionId, fallbackName = `survey-report-${inspectionId}.pdf`) {
  const response = await apiClient.get(`/surveyor/survey-reports/${inspectionId}/report.pdf`, { responseType: "blob" });
  const disposition = response.headers?.["content-disposition"] ?? "";
  const filename = /filename="([^"]+)"/.exec(disposition)?.[1] ?? fallbackName;
  return { blob: response.data, filename };
}

// The survey report (GET /surveyor/claims/{id}/report): a Draft once the
// workflow is complete, or the submitted report. Read-only.
export async function getSurveyReport(claimId) {
  const response = await apiClient.get(`/surveyor/claims/${claimId}/report`);
  return response.data;
}

// The same report as a PDF, built by the backend from the same data.
// Cross-origin responses only expose Content-Disposition when the backend's
// CORS settings allow it, so the caller passes a fallback file name.
export async function downloadSurveyReportPdf(claimId, fallbackName = `survey-report-${claimId}.pdf`) {
  const response = await apiClient.get(`/surveyor/claims/${claimId}/report.pdf`, { responseType: "blob" });
  const disposition = response.headers?.["content-disposition"] ?? "";
  const filename = /filename="([^"]+)"/.exec(disposition)?.[1] ?? fallbackName;
  return { blob: response.data, filename };
}
