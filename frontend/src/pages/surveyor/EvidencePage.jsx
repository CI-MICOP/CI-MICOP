import { useCallback } from "react";
import { useParams } from "react-router-dom";

import Breadcrumbs from "../../components/common/Breadcrumbs";
import Card from "../../components/common/Card";
import EmptyState from "../../components/common/EmptyState";
import ErrorState from "../../components/common/ErrorState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import StatusBadge from "../../components/common/StatusBadge";
import ClaimTabs from "../../components/surveyor/ClaimTabs";
import { useFetch } from "../../hooks/useFetch";
import { getClaimById } from "../../services/claimService";
import { getAssignedClaimDetail } from "../../services/surveyorService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatDate } from "../../utils/format";
import { getStatusTone } from "../../utils/statusTone";

export default function EvidencePage() {
  const { claimId } = useParams();

  const fetchDetail = useCallback(async () => {
    const [claim, assigned] = await Promise.all([getClaimById(claimId), getAssignedClaimDetail(claimId)]);
    return { claim, ...assigned };
  }, [claimId]);

  const { data, isLoading, error, reload } = useFetch(fetchDetail, [fetchDetail]);

  if (isLoading) return <LoadingState label="Loading evidence..." />;
  if (error) {
    return (
      <div>
        <PageHeader title="Evidence" />
        <ErrorState message={getApiErrorMessage(error)} onRetry={reload} />
      </div>
    );
  }

  const { claim, evidence } = data;

  return (
    <div>
      <Breadcrumbs
        items={[
          { label: "Assigned Claims", to: "/surveyor/claims" },
          { label: claim.Claim_Number, to: `/surveyor/claims/${claim.Claim_ID}` },
          { label: "Evidence" },
        ]}
      />
      <PageHeader title={`Evidence — ${claim.Claim_Number}`} />
      <ClaimTabs claimId={claim.Claim_ID} />

      {evidence.length === 0 ? (
        <Card>
          <EmptyState title="No evidence on file for this claim" />
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {evidence.map((item) => (
            <Card key={item.Evidence_ID}>
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-ink">{item.Evidence_Type}</h3>
                <StatusBadge label={item.Verification_Status} tone={getStatusTone(item.Verification_Status)} />
              </div>
              <dl className="grid grid-cols-2 gap-3 text-sm">
                <Detail label="File Name" value={item.File_Name} />
                <Detail label="Date" value={formatDate(item.Evidence_Date)} />
                <Detail label="Source" value={item.Evidence_Source} />
                <Detail label="Image Quality" value={item.Image_Quality} />
                <Detail label="Vehicle Damage Detected" value={item.Vehicle_Damage_Detected ? "Yes" : "No"} />
                <Detail label="Damage Severity" value={item.Damage_Severity} />
                <Detail label="Location Match" value={item.Location_Match ? "Yes" : "No"} />
                <Detail label="Duplicate Evidence" value={item.Duplicate_Evidence_Indicator ? "Yes" : "No"} />
                <Detail label="Confidence Score" value={item.Evidence_Confidence_Score} />
              </dl>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function Detail({ label, value }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-muted">{label}</dt>
      <dd className="text-ink">{value}</dd>
    </div>
  );
}
