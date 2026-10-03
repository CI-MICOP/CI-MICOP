import { useParams } from "react-router-dom";

import Breadcrumbs from "../../components/common/Breadcrumbs";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import ClaimTabs from "../../components/officer/ClaimTabs";
import ClaimWorkspaceError from "../../components/officer/ClaimWorkspaceError";
import EvidenceDuplicationPanel from "../../components/officer/EvidenceDuplicationPanel";
import { useClaimWorkspace } from "../../hooks/useClaimWorkspace";

export default function EvidenceCheckPage() {
  const { claimId } = useParams();
  const { data, isLoading, error, reload } = useClaimWorkspace(claimId);

  if (isLoading) return <LoadingState label="Loading claim..." />;
  if (error) {
    return (
      <div>
        <PageHeader title="Evidence Check" />
        <ClaimWorkspaceError error={error} onRetry={reload} />
      </div>
    );
  }

  const { claim } = data;

  return (
    <div>
      <Breadcrumbs items={[{ label: "All Claims", to: "/officer/claims" }, { label: claim.Claim_Number, to: `/officer/claims/${claim.Claim_ID}` }, { label: "Evidence Check" }]} />
      <PageHeader title={`Evidence Check — ${claim.Claim_Number}`} />
      <ClaimTabs claimId={claim.Claim_ID} />

      <EvidenceDuplicationPanel claimId={claim.Claim_ID} />
    </div>
  );
}
