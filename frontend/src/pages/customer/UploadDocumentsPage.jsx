import { AlertTriangle } from "lucide-react";
import { useState } from "react";

import Button from "../../components/common/Button";
import Card from "../../components/common/Card";
import EmptyState from "../../components/common/EmptyState";
import ErrorState from "../../components/common/ErrorState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import DocumentUploadGrid from "../../components/customer/DocumentUploadGrid";
import { useFetch } from "../../hooks/useFetch";
import { listClaims } from "../../services/claimService";
import { getApiErrorMessage } from "../../utils/errors";

export default function UploadDocumentsPage() {
  const [claimId, setClaimId] = useState("");
  const [files, setFiles] = useState({});
  const [submitAttempted, setSubmitAttempted] = useState(false);

  const { data: claims, isLoading, error, reload } = useFetch(() => listClaims({ limit: 200 }), []);

  if (isLoading) return <LoadingState label="Loading your claims..." />;
  if (error) return <ErrorState message={getApiErrorMessage(error)} onRetry={reload} />;

  return (
    <div>
      <PageHeader title="Upload Documents" subtitle="Attach supporting documents to one of your claims." />

      {claims.length === 0 ? (
        <EmptyState title="No claims to attach documents to" message="File a claim first, then upload documents against it." />
      ) : (
        <Card>
          <label className="mb-4 block">
            <span className="mb-1 block text-sm font-medium text-ink">Claim</span>
            <select value={claimId} onChange={(e) => setClaimId(e.target.value)} className="input sm:max-w-sm">
              <option value="">Select a claim</option>
              {claims.map((claim) => (
                <option key={claim.Claim_ID} value={claim.Claim_ID}>
                  {claim.Claim_Number} &middot; {claim.Claim_Type}
                </option>
              ))}
            </select>
          </label>

          <DocumentUploadGrid files={files} onFileChange={(key, file) => setFiles((prev) => ({ ...prev, [key]: file }))} />

          {submitAttempted && (
            <div className="mt-4 flex gap-3 rounded-card border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
              <AlertTriangle className="h-5 w-5 shrink-0 text-warning" aria-hidden="true" />
              <div>
                <p className="font-medium">Document upload is not yet connected to the backend</p>
                <p className="mt-1 text-amber-800">
                  The CI-MICOP API currently only supports retrieving documents, not uploading them. The
                  files selected above have not been sent or saved anywhere.
                </p>
              </div>
            </div>
          )}

          <div className="mt-4 flex justify-end border-t border-border pt-4">
            <Button
              disabled={!claimId || Object.values(files).every((f) => !f)}
              onClick={() => setSubmitAttempted(true)}
            >
              Upload Selected Documents
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
