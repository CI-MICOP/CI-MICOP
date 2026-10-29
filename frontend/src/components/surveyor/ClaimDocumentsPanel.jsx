import { Eye, FileText, Lock } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { useFetch } from "../../hooks/useFetch";
import { getClaimDocumentContent, listClaimDocuments } from "../../services/surveyorService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatDate } from "../../utils/format";
import Button from "../common/Button";
import Card from "../common/Card";
import ErrorState from "../common/ErrorState";
import LoadingState from "../common/LoadingState";
import Modal from "../common/Modal";
import StatusBadge from "../common/StatusBadge";

const LABELS = { RC: "Registration Certificate (RC)", "Driving Licence": "Driving Licence (DL)" };

// What the server reports about each document (services/surveyor_documents.py).
const AVAILABILITY = {
  available: { label: "Available", tone: "success" },
  not_uploaded: { label: "Not uploaded", tone: "neutral" },
  unavailable: {
    label: "Unavailable",
    tone: "danger",
    note: "The file could not be found. If this copy was submitted before files were kept for this document type, ask the customer to upload it again.",
  },
  unsupported: { label: "Cannot be previewed", tone: "warning", note: "This file type is not shown in the browser." },
};

function verificationBadge(status) {
  if (!status) return null;
  // Reported as recorded - opening a document never marks it verified.
  if (status === "Pending") return <StatusBadge label="Verification pending" tone="warning" />;
  return <StatusBadge label={`Verification: ${status}`} tone={status === "Verified" ? "success" : "neutral"} />;
}

/**
 * Claim Documents on the Claim Details step: the customer's RC, driving
 * licence and insurance policy copies only, read-only, for the assigned
 * surveyor from the scheduled inspection date. FIR, Repair Estimate, Survey
 * Report and customer accident photos are never part of it - the server
 * (services/surveyor_documents.py) enforces this, not just this panel.
 * Every list and view request is authorised by the server; documents can
 * be reopened as often as needed.
 */
export default function ClaimDocumentsPanel({ claimId, progress }) {
  const unlocked = Boolean(progress.workflow) && progress.scheduleReached;
  if (!unlocked) return <LockedPanel progress={progress} />;
  return <UnlockedPanel claimId={claimId} />;
}

function LockedPanel({ progress }) {
  const date = progress.schedule?.scheduled_date;
  return (
    <Card>
      <h3 className="mb-3 text-sm font-semibold text-ink">Claim Documents</h3>
      <p className="flex items-start gap-2 rounded-card bg-surface p-3 text-sm text-muted">
        <Lock className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
        {progress.workflow
          ? `The customer's documents become accessible on the scheduled inspection date${date ? `, ${formatDate(date)}` : ""}.`
          : "Customer documents are available only to the surveyor assigned to this inspection."}
      </p>
    </Card>
  );
}

function UnlockedPanel({ claimId }) {
  const fetchDocuments = useCallback(() => listClaimDocuments(claimId), [claimId]);
  const { data, isLoading, error, reload } = useFetch(fetchDocuments, [fetchDocuments]);
  const [viewing, setViewing] = useState(null);

  return (
    <Card>
      <h3 className="mb-1 text-sm font-semibold text-ink">Claim Documents</h3>
      <p className="mb-4 text-xs text-muted">Read-only. Open a document as often as you need during the inspection.</p>
      {isLoading ? (
        <LoadingState label="Loading claim documents..." />
      ) : error ? (
        <ErrorState title="Unable to load the claim documents" message={getApiErrorMessage(error)} onRetry={reload} />
      ) : (
        <ul className="divide-y divide-border" aria-label="Claim documents">
          {data.documents.map((doc) => {
            const availability = AVAILABILITY[doc.availability] ?? AVAILABILITY.unavailable;
            const label = LABELS[doc.document_type] ?? doc.document_type;
            return (
              <li key={doc.document_id ?? doc.document_type} className="flex flex-col gap-2 py-3 text-sm sm:flex-row sm:items-center sm:justify-between">
                <div className="flex min-w-0 items-start gap-2">
                  <FileText className="mt-0.5 h-4 w-4 shrink-0 text-muted" aria-hidden="true" />
                  <div className="min-w-0">
                    <p className="font-medium text-ink">{label}</p>
                    <p className="text-xs text-muted">
                      {doc.submitted_date ? `Submitted ${formatDate(doc.submitted_date)}` : "No document submitted"}
                      {availability.note ? ` · ${availability.note}` : ""}
                    </p>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2 sm:justify-end">
                  <StatusBadge label={availability.label} tone={availability.tone} />
                  {verificationBadge(doc.verification_status)}
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
      {viewing && <DocumentViewer claimId={claimId} document={viewing} onClose={() => setViewing(null)} />}
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
    // Errors for a Blob request arrive as a Blob holding the JSON body.
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

/** The document, fetched with the session token and shown from memory. */
function DocumentViewer({ claimId, document, onClose }) {
  const [state, setState] = useState({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    let url = null;
    getClaimDocumentContent(claimId, document.document_id)
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
  }, [claimId, document.document_id]);

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
          Back to Claim Details
        </Button>
      </div>
    </Modal>
  );
}
