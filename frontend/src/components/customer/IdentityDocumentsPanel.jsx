import { Eye, FileText } from "lucide-react";
import { useEffect, useState } from "react";

import { useFetch } from "../../hooks/useFetch";
import { getIdentityDocumentContent, listIdentityDocuments } from "../../services/documentService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatDate } from "../../utils/format";
import Button from "../common/Button";
import Card from "../common/Card";
import ErrorState from "../common/ErrorState";
import LoadingState from "../common/LoadingState";
import Modal from "../common/Modal";
import StatusBadge from "../common/StatusBadge";

const LABELS = { RC: "Registration Certificate (RC)", "Driving Licence": "Driving Licence (DL)", "Insurance Policy": "Insurance Policy" };

// What the server reports about each document (backend/app/services/customer_identity_documents.py).
const AVAILABILITY = {
  available: { label: "Available", tone: "success" },
  not_uploaded: { label: "Not Uploaded", tone: "neutral" },
  unavailable: {
    label: "Not Available",
    tone: "danger",
    note: "The file could not be found. Please contact support if you believe this is an error.",
  },
  unsupported: { label: "Cannot be previewed", tone: "warning", note: "This file type is not shown in the browser." },
};

/**
 * "My Documents" identity section: the customer's own RC, Driving Licence
 * and Insurance Policy documents, however they were imported onto their
 * record (backend/app/services/document_import.py) - distinct from, and
 * additive to, the claim-by-claim document table below it on this page.
 */
export default function IdentityDocumentsPanel() {
  const { data, isLoading, error, reload } = useFetch(listIdentityDocuments, []);
  const [viewing, setViewing] = useState(null);

  return (
    <Card>
      <h3 className="mb-1 text-sm font-semibold text-ink">My Documents</h3>
      <p className="mb-4 text-xs text-muted">Your RC, Driving Licence and Insurance Policy, on file with us.</p>
      {isLoading ? (
        <LoadingState label="Loading your documents..." />
      ) : error ? (
        <ErrorState title="Unable to load your documents" message={getApiErrorMessage(error)} onRetry={reload} />
      ) : (
        <ul className="divide-y divide-border" aria-label="Identity documents">
          {data.documents.map((doc) => {
            const availability = AVAILABILITY[doc.availability] ?? AVAILABILITY.unavailable;
            const label = LABELS[doc.document_type] ?? doc.document_type;
            return (
              <li
                key={doc.document_id ?? doc.document_type}
                className="flex flex-col gap-2 py-3 text-sm sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="flex min-w-0 items-start gap-2">
                  <FileText className="mt-0.5 h-4 w-4 shrink-0 text-muted" aria-hidden="true" />
                  <div className="min-w-0">
                    <p className="font-medium text-ink">{label}</p>
                    <p className="text-xs text-muted">
                      {doc.submitted_date ? `Submitted ${formatDate(doc.submitted_date)}` : "Not uploaded yet"}
                      {doc.expiry_date ? ` · Expires ${formatDate(doc.expiry_date)}` : ""}
                      {availability.note ? ` · ${availability.note}` : ""}
                    </p>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2 sm:justify-end">
                  <StatusBadge label={availability.label} tone={availability.tone} />
                  {doc.availability === "available" && (
                    <Button size="sm" variant="secondary" onClick={() => setViewing({ ...doc, label })} aria-label={`View ${label}`}>
                      <Eye className="h-4 w-4" aria-hidden="true" />
                      View
                    </Button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
      {viewing && <DocumentViewer document={viewing} onClose={() => setViewing(null)} />}
    </Card>
  );
}

function readBlobText(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsText(blob);
  });
}

async function viewerErrorMessage(error) {
  const status = error?.response?.status;
  if (!error?.response) return "Unable to connect to the CI-MICOP server. Please try again.";
  if (status === 401) return "Your session has expired. Please sign in again to view this document.";
  let detail = null;
  const body = error.response.data;
  try {
    const isBlob = typeof body?.size === "number" && typeof body?.type === "string";
    const parsed = isBlob ? JSON.parse(await readBlobText(body)) : body;
    detail = typeof parsed?.detail === "string" ? parsed.detail : null;
  } catch {
    detail = null;
  }
  if (status === 415) return detail ?? "This document cannot be previewed in the browser.";
  if (status === 403 || status === 404) return detail ?? "This document is not available to you.";
  return detail ?? "The document could not be loaded. Please try again.";
}

function DocumentViewer({ document, onClose }) {
  const [state, setState] = useState({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    let url = null;
    getIdentityDocumentContent(document.document_id)
      .then((blob) => {
        if (cancelled) return;
        url = URL.createObjectURL(blob);
        setState({ status: "ready", url, type: blob.type });
      })
      .catch(async (error) => {
        const message = await viewerErrorMessage(error);
        if (!cancelled) setState({ status: "error", message });
      });
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [document.document_id]);

  return (
    <Modal isOpen onClose={onClose} title={document.label} size="xl">
      <div className="flex h-[70vh] items-center justify-center overflow-hidden rounded-card border border-border bg-surface">
        {state.status === "loading" && <LoadingState label="Opening document..." />}
        {state.status === "error" && (
          <p role="alert" className="max-w-md p-4 text-center text-sm text-danger">
            {state.message}
          </p>
        )}
        {state.status === "ready" &&
          (state.type === "application/pdf" ? (
            <iframe src={state.url} title={document.label} className="h-full w-full" />
          ) : state.type.startsWith("image/") ? (
            <img src={state.url} alt={document.label} className="max-h-full max-w-full object-contain" />
          ) : (
            <p className="p-4 text-sm text-muted">This document cannot be previewed in the browser.</p>
          ))}
      </div>
      <div className="mt-4 flex justify-end">
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
      </div>
    </Modal>
  );
}
