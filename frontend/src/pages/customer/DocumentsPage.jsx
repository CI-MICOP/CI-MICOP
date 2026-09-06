import { UploadCloud } from "lucide-react";
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
import { listMyDocuments } from "../../services/documentService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatDate } from "../../utils/format";
import { getStatusTone } from "../../utils/statusTone";

export default function DocumentsPage() {
  const [search, setSearch] = useState("");
  const [selectedDocument, setSelectedDocument] = useState(null);

  const { data: documents, isLoading, error, reload } = useFetch(listMyDocuments, []);

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
                    onClick={() => setSelectedDocument(d)}
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
          <dl className="space-y-3 text-sm">
            <Row label="Document Type" value={selectedDocument.Document_Type} />
            <Row label="Document Name" value={selectedDocument.Document_Name} />
            <Row label="Claim" value={selectedDocument.Claim_Number ?? "-"} />
            <Row label="Submitted" value={formatDate(selectedDocument.Document_Submitted_Date)} />
            <Row label="Status" value={selectedDocument.Document_Status} />
            <Row label="Verification Status" value={selectedDocument.Verification_Status} />
            <Row label="Completeness" value={`${selectedDocument.Document_Completeness}%`} />
          </dl>
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
