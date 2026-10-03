import { AlertTriangle, CheckCircle2, Loader2, RotateCcw } from "lucide-react";
import { useState } from "react";

import Button from "../../components/common/Button";
import Card from "../../components/common/Card";
import EmptyState from "../../components/common/EmptyState";
import ErrorState from "../../components/common/ErrorState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import StatusBadge from "../../components/common/StatusBadge";
import DocumentUploadGrid from "../../components/customer/DocumentUploadGrid";
import { DOCUMENT_CATEGORIES } from "../../components/customer/documentCategories";
import { useFetch } from "../../hooks/useFetch";
import { listClaims } from "../../services/claimService";
import { uploadDocument } from "../../services/documentService";
import { getApiErrorMessage, getUploadErrorMessage } from "../../utils/errors";

/**
 * Uploads documents to one of the customer's EXISTING claims through the
 * same POST /documents endpoint NewClaimPage uses after creating a claim.
 * The backend enforces ownership (a customer can only attach documents to
 * their own claim), file type and size - this page only reports results.
 */
export default function UploadDocumentsPage() {
  const [claimId, setClaimId] = useState("");
  const [files, setFiles] = useState({});
  // The batch currently shown in the results list: { claimId, categoryKeys }.
  const [batch, setBatch] = useState(null);
  // { [documentCategoryKey]: { status: "uploading" | "uploaded" | "failed", error? } }
  const [uploads, setUploads] = useState({});
  const [isUploading, setIsUploading] = useState(false);

  const { data: claims, isLoading, error, reload } = useFetch(() => listClaims({ limit: 200 }), []);

  const selectedCategories = DOCUMENT_CATEGORIES.filter((c) => files[c.key]);

  async function uploadOne(targetClaimId, categoryKey) {
    setUploads((prev) => ({ ...prev, [categoryKey]: { status: "uploading" } }));
    try {
      await uploadDocument(targetClaimId, categoryKey, files[categoryKey]);
      setUploads((prev) => ({ ...prev, [categoryKey]: { status: "uploaded" } }));
    } catch (err) {
      setUploads((prev) => ({ ...prev, [categoryKey]: { status: "failed", error: getUploadErrorMessage(err) } }));
    }
  }

  async function handleUpload() {
    if (isUploading) return;
    const categoryKeys = selectedCategories.map((c) => c.key);
    setBatch({ claimId, categoryKeys });
    setUploads({});
    setIsUploading(true);
    try {
      // Sequential, matching NewClaimPage: predictable per-file progress.
      for (const key of categoryKeys) {
        await uploadOne(claimId, key);
      }
    } finally {
      setIsUploading(false);
    }
  }

  function startOver() {
    setFiles({});
    setBatch(null);
    setUploads({});
  }

  if (isLoading) return <LoadingState label="Loading your claims..." />;
  if (error) return <ErrorState message={getApiErrorMessage(error)} onRetry={reload} />;

  const batchCategories = batch ? DOCUMENT_CATEGORIES.filter((c) => batch.categoryKeys.includes(c.key)) : [];
  const uploadedCount = batchCategories.filter((c) => uploads[c.key]?.status === "uploaded").length;
  const failedCount = batchCategories.filter((c) => uploads[c.key]?.status === "failed").length;
  const batchDone = batch && !isUploading;
  const batchClaim = batch ? claims.find((c) => c.Claim_ID === batch.claimId) : null;

  return (
    <div>
      <PageHeader title="Upload Documents" subtitle="Attach supporting documents to one of your claims." />

      {claims.length === 0 ? (
        <EmptyState title="No claims to attach documents to" message="File a claim first, then upload documents against it." />
      ) : (
        <Card>
          <label className="mb-4 block">
            <span className="mb-1 block text-sm font-medium text-ink">Claim</span>
            <select
              value={claimId}
              onChange={(e) => setClaimId(e.target.value)}
              disabled={isUploading}
              className="input sm:max-w-sm"
            >
              <option value="">Select a claim</option>
              {claims.map((claim) => (
                <option key={claim.Claim_ID} value={claim.Claim_ID}>
                  {claim.Claim_Number} &middot; {claim.Claim_Type}
                </option>
              ))}
            </select>
          </label>

          {!batch && (
            <DocumentUploadGrid files={files} onFileChange={(key, file) => setFiles((prev) => ({ ...prev, [key]: file }))} />
          )}

          {batch && (
            <div className="space-y-2">
              <p className="text-sm text-muted">
                Uploading to claim <span className="font-medium text-ink">{batchClaim?.Claim_Number ?? batch.claimId}</span>
              </p>
              {batchCategories.map((category) => {
                const state = uploads[category.key] ?? { status: "uploading" };
                return (
                  <div
                    key={category.key}
                    className="flex items-center justify-between gap-3 rounded-card border border-border bg-surface p-3 text-sm"
                  >
                    <div className="min-w-0">
                      <p className="truncate font-medium text-ink">{category.label}</p>
                      <p className="truncate text-xs text-muted">{files[category.key]?.name}</p>
                      {state.status === "failed" && <p className="mt-0.5 text-xs text-danger">{state.error}</p>}
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      {state.status === "uploading" && (
                        <Loader2 className="h-4 w-4 animate-spin text-brand-600" aria-label="Uploading" />
                      )}
                      {state.status === "uploaded" && <StatusBadge label="Uploaded" tone="success" />}
                      {state.status === "failed" && (
                        <>
                          <StatusBadge label="Failed" tone="danger" />
                          <Button
                            size="sm"
                            variant="secondary"
                            disabled={isUploading}
                            onClick={() => uploadOne(batch.claimId, category.key)}
                          >
                            <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
                            Retry
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                );
              })}

              {batchDone && (
                <div
                  className={`mt-2 flex gap-3 rounded-card border p-4 text-sm ${
                    failedCount === 0
                      ? "border-green-200 bg-green-50 text-green-900"
                      : "border-amber-200 bg-amber-50 text-amber-900"
                  }`}
                >
                  {failedCount === 0 ? (
                    <CheckCircle2 className="h-5 w-5 shrink-0 text-success" aria-hidden="true" />
                  ) : (
                    <AlertTriangle className="h-5 w-5 shrink-0 text-warning" aria-hidden="true" />
                  )}
                  <p>
                    {failedCount === 0
                      ? `All ${batchCategories.length} document${batchCategories.length === 1 ? "" : "s"} uploaded.`
                      : `${uploadedCount} of ${batchCategories.length} uploaded. ${failedCount} failed - use Retry to try again.`}
                  </p>
                </div>
              )}
            </div>
          )}

          <div className="mt-4 flex justify-end border-t border-border pt-4">
            {batch ? (
              <Button variant="secondary" disabled={isUploading} onClick={startOver}>
                Upload More Documents
              </Button>
            ) : (
              <Button disabled={!claimId || selectedCategories.length === 0} onClick={handleUpload}>
                Upload Selected Documents
              </Button>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}
