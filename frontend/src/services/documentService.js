import { apiClient } from "./apiClient";
import { listClaims } from "./claimService";

export async function listDocumentsByClaim(claimId) {
  const response = await apiClient.get("/documents", { params: { claim_id: claimId } });
  return response.data;
}

export async function getDocumentById(documentId) {
  const response = await apiClient.get(`/documents/${documentId}`);
  return response.data;
}

// multipart/form-data - Content-Type (with its boundary) is left for
// Axios/the browser to set automatically; never set it manually here.
// Customer_ID is never sent - the backend derives it from the JWT.
export async function uploadDocument(claimId, documentType, file) {
  const formData = new FormData();
  formData.append("claim_id", claimId);
  formData.append("document_type", documentType);
  formData.append("file", file);
  const response = await apiClient.post("/documents", formData);
  return response.data;
}

// There is no "my documents" aggregate endpoint on the backend, so this
// composes the two that do exist: the current user's claims, then the
// documents attached to each one. Used by the Documents page and the
// dashboard's "Recent Documents" section.
export async function listMyDocuments() {
  const claims = await listClaims({ limit: 200 });
  const perClaim = await Promise.all(
    claims.map((claim) =>
      listDocumentsByClaim(claim.Claim_ID).then((docs) =>
        docs.map((doc) => ({ ...doc, Claim_Number: claim.Claim_Number }))
      )
    )
  );
  return perClaim.flat();
}
