import { CheckCircle2, CircleDashed, FileText } from "lucide-react";
import { useCallback, useMemo } from "react";
import { useParams } from "react-router-dom";

import Breadcrumbs from "../../components/common/Breadcrumbs";
import Card from "../../components/common/Card";
import ErrorState from "../../components/common/ErrorState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import { useFetch } from "../../hooks/useFetch";
import { getClaimById } from "../../services/claimService";
import { listDocumentsByClaim } from "../../services/documentService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatDate } from "../../utils/format";

/**
 * Built entirely from real claim/document fields - there is no dedicated
 * claim-audit-trail endpoint exposed to customers, so stages that aren't
 * backed by an actual timestamp are shown as "not yet available" rather
 * than invented.
 */
export default function ClaimTimelinePage() {
  const { claimId } = useParams();

  const fetchTimeline = useCallback(async () => {
    const claim = await getClaimById(claimId);
    const documents = await listDocumentsByClaim(claim.Claim_ID);
    return { claim, documents };
  }, [claimId]);

  const { data, isLoading, error, reload } = useFetch(fetchTimeline, [fetchTimeline]);

  const events = useMemo(() => {
    if (!data) return [];
    const { claim, documents } = data;
    const list = [
      {
        id: "intimation",
        date: claim.Claim_Intimation_Date,
        title: "Claim Intimated",
        description: "The claim was reported to CI-MICOP.",
        happened: true,
      },
      {
        id: "submitted",
        date: claim.Claim_Date,
        title: "Claim Submitted",
        description: `${claim.Claim_Type} claim registered.`,
        happened: true,
      },
      ...[...documents]
        .sort((a, b) => new Date(a.Document_Submitted_Date) - new Date(b.Document_Submitted_Date))
        .map((doc) => ({
          id: `doc-${doc.Document_ID}`,
          date: doc.Document_Submitted_Date,
          title: `${doc.Document_Type} Uploaded`,
          description: `Status: ${doc.Document_Status}${doc.Verification_Status ? ` · ${doc.Verification_Status}` : ""}`,
          happened: true,
        })),
      {
        id: "decision",
        date: claim.Decision_Date,
        title: "Decision",
        description: claim.Final_Decision
          ? `${claim.Final_Decision}${claim.Decision_Reason ? ` — ${claim.Decision_Reason}` : ""}`
          : null,
        happened: Boolean(claim.Final_Decision),
      },
    ];
    // Not-yet-happened events (e.g. an undecided claim's Decision_Date,
    // which the schema still requires to be non-null) always sort last,
    // regardless of the placeholder date value underneath them.
    return list.sort((a, b) => {
      if (a.happened !== b.happened) return a.happened ? -1 : 1;
      return new Date(a.date) - new Date(b.date);
    });
  }, [data]);

  if (isLoading) return <LoadingState label="Loading claim timeline..." />;
  if (error) {
    return (
      <div>
        <PageHeader title="Claim Timeline" />
        <ErrorState message={getApiErrorMessage(error)} onRetry={reload} />
      </div>
    );
  }

  return (
    <div>
      <Breadcrumbs
        items={[
          { label: "My Claims", to: "/customer/claims" },
          { label: data.claim.Claim_Number, to: `/customer/claims/${data.claim.Claim_ID}` },
          { label: "Timeline" },
        ]}
      />
      <PageHeader title={`Claim Timeline — ${data.claim.Claim_Number}`} subtitle="Progress based on available claim and document records." />

      <Card>
        <ol className="space-y-6">
          {events.map((event) => (
            <li key={event.id} className="flex gap-4">
              <div className="flex flex-col items-center">
                {event.happened ? (
                  <CheckCircle2 className="h-5 w-5 text-success" aria-hidden="true" />
                ) : (
                  <CircleDashed className="h-5 w-5 text-muted" aria-hidden="true" />
                )}
                <span className="mt-1 w-px flex-1 bg-border" />
              </div>
              <div className="pb-2">
                <p className={`text-sm font-medium ${event.happened ? "text-ink" : "text-muted"}`}>{event.title}</p>
                {event.happened ? (
                  <>
                    <p className="text-xs text-muted">{formatDate(event.date)}</p>
                    {event.description && <p className="mt-1 text-sm text-ink">{event.description}</p>}
                  </>
                ) : (
                  <p className="text-xs text-muted">Not yet available</p>
                )}
              </div>
            </li>
          ))}
        </ol>
        {data.documents.length === 0 && (
          <p className="mt-2 flex items-center gap-2 text-xs text-muted">
            <FileText className="h-3.5 w-3.5" aria-hidden="true" />
            No documents have been uploaded for this claim yet.
          </p>
        )}
      </Card>
    </div>
  );
}
