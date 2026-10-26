import { ScanSearch, UploadCloud } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import Button from "../../components/common/Button";
import Card from "../../components/common/Card";
import DataTable from "../../components/common/DataTable";
import ErrorState from "../../components/common/ErrorState";
import Modal from "../../components/common/Modal";
import PageHeader from "../../components/common/PageHeader";
import SearchInput from "../../components/common/SearchInput";
import StatusBadge from "../../components/common/StatusBadge";
import { useFetch } from "../../hooks/useFetch";
import { analyzeDocument, listMyDocuments } from "../../services/documentService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatDate } from "../../utils/format";
import { getStatusTone } from "../../utils/statusTone";

// Step 5.8.12: extraction_status values the live analyze endpoint can
// return - see backend/app/services/document_analysis.py.
const EXTRACTION_STATUS_LABEL = {
  extracted_native: "Text extracted (native)",
  extracted_ocr: "Text extracted (OCR)",
  extracted_ocr_no_confidence: "Text extracted (confidence unavailable)",
  partial: "Partially extracted",
  empty: "No text found",
  unavailable: "Unavailable",
  copy_not_retained: "Copy not kept - saved details shown",
};

export default function DocumentsPage() {
  const [search, setSearch] = useState("");
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [analysis, setAnalysis] = useState({ status: "idle", result: null, message: "" });

  const { data: documents, isLoading, error, reload } = useFetch(listMyDocuments, []);

  function openDocument(doc) {
    setSelectedDocument(doc);
    setAnalysis({ status: "idle", result: null, message: "" });
  }

  async function handleAnalyze() {
    setAnalysis({ status: "loading", result: null, message: "" });
    try {
      const result = await analyzeDocument(selectedDocument.Document_ID);
      setAnalysis({ status: "success", result, message: "" });
    } catch (err) {
      setAnalysis({ status: "error", result: null, message: getApiErrorMessage(err) });
    }
  }

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return documents ?? [];
    return (documents ?? []).filter(
      (doc) =>
        doc.Document_Type.toLowerCase().includes(term) ||
        doc.Document_Name.toLowerCase().includes(term) ||
        doc.Claim_Number?.toLowerCase().includes(term)
    );
  }, [documents, search]);

  return (
    <div>
      <PageHeader
        title="Documents"
        subtitle="All documents submitted across your claims."
        actions={
          <Link to="/customer/documents/upload">
            <Button>
              <UploadCloud className="h-4 w-4" aria-hidden="true" />
              Upload Documents
            </Button>
          </Link>
        }
      />

      {error ? (
        <ErrorState message={getApiErrorMessage(error)} onRetry={reload} />
      ) : (
        <Card>
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Search by document type, name, or claim"
            className="mb-4 sm:max-w-sm"
          />

          <DataTable
            isLoading={isLoading}
            rows={filtered}
            rowKey="Document_ID"
            emptyMessage={documents?.length ? "No documents match your search." : "No documents uploaded yet."}
            columns={[
              { key: "name", header: "Document Name", render: (d) => d.Document_Name || d.Document_Type },
              { key: "claim", header: "Claim", render: (d) => d.Claim_Number ?? "-" },
              { key: "date", header: "Upload Date", render: (d) => formatDate(d.Document_Submitted_Date) },
              {
                key: "status",
                header: "Status",
                render: (d) => <StatusBadge label={d.Document_Status} tone={getStatusTone(d.Document_Status)} />,
              },
              {
                key: "action",
                header: "Action",
                render: (d) => (
                  <button
                    type="button"
                    onClick={() => openDocument(d)}
                    className="font-medium text-brand-600 hover:text-brand-700"
                  >
                    View
                  </button>
                ),
              },
            ]}
          />
        </Card>
      )}

      <Modal isOpen={Boolean(selectedDocument)} onClose={() => setSelectedDocument(null)} title="Document Details">
        {selectedDocument && (
          <div className="space-y-4">
            <dl className="space-y-3 text-sm">
              <Row label="Document Type" value={selectedDocument.Document_Type} />
              <Row label="Document Name" value={selectedDocument.Document_Name} />
              <Row label="Claim" value={selectedDocument.Claim_Number ?? "-"} />
              <Row label="Submitted" value={formatDate(selectedDocument.Document_Submitted_Date)} />
              <Row label="Status" value={selectedDocument.Document_Status} />
              <Row label="Verification Status" value={selectedDocument.Verification_Status} />
              {selectedDocument.Copy_Retained === false && (
                <Row
                  label="Copy Kept"
                  value="No - this copy was read when you uploaded it and is not stored. Only the details needed for checking were saved."
                />
              )}
            </dl>

            <div className="border-t border-border pt-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h4 className="text-sm font-semibold text-ink">Document Analysis</h4>
                  <p className="mt-1 text-xs text-muted">
                    Extracts text from this file and checks the claim's document completeness. Does not verify or
                    approve anything.
                  </p>
                </div>
                <Button size="sm" variant="secondary" onClick={handleAnalyze} isLoading={analysis.status === "loading"}>
                  <ScanSearch className="h-4 w-4" aria-hidden="true" />
                  Analyze
                </Button>
              </div>

              {analysis.status === "error" && <p className="mt-3 text-sm text-danger">{analysis.message}</p>}

              {analysis.status === "success" && analysis.result && (
                <dl className="mt-3 space-y-3 text-sm">
                  <Row
                    label="OCR Status"
                    value={EXTRACTION_STATUS_LABEL[analysis.result.extraction_status] ?? analysis.result.extraction_status}
                  />
                  <Row label="OCR Confidence" value={analysis.result.ocr_confidence.toFixed(2)} />
                  <Row label="Text Extracted" value={analysis.result.extracted_text ? "Yes" : "No"} />
                  <Row
                    label="Document Completeness"
                    value={
                      analysis.result.completeness.available
                        ? `${Math.round(analysis.result.completeness.completeness_ratio * 100)}% (${analysis.result.completeness.present_document_types.length}/${analysis.result.completeness.required_document_types.length} required types)`
                        : "Unavailable - no documents to assess yet"
                    }
                  />
                  {analysis.result.completeness.missing_document_types.length > 0 && (
                    <Row label="Missing Document Types" value={analysis.result.completeness.missing_document_types.join(", ")} />
                  )}
                  {analysis.result.limitations.length > 0 && (
                    <Row label="Limitations" value={analysis.result.limitations.join(" ")} />
                  )}
                </dl>
              )}

              {analysis.status === "success" && analysis.result && (
                <div className="mt-4 border-t border-border pt-4">
                  <h5 className="text-xs font-semibold uppercase tracking-wide text-muted">Extracted Entities</h5>
                  <p className="mt-1 text-xs text-muted">
                    Best-effort extraction — not yet used for consistency decisions.
                  </p>
                  {analysis.result.entities.entities.length === 0 ? (
                    <p className="mt-2 text-sm text-ink">No entities found.</p>
                  ) : (
                    <ul className="mt-2 space-y-1 text-sm">
                      {analysis.result.entities.entities.map((entity) => (
                        <li key={`${entity.entity_type}-${entity.normalized_value}`} className="flex justify-between gap-4">
                          <span className="text-muted">
                            {entity.entity_type === "registration_number" ? "Registration Number" : "Policy Number"}
                          </span>
                          <span className="text-right text-ink">
                            {entity.normalized_value} ({Math.round(entity.confidence * 100)}%)
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-muted">{label}</dt>
      <dd className="text-right text-ink">{value}</dd>
    </div>
  );
}
