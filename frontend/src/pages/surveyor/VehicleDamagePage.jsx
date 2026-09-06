import { Info } from "lucide-react";
import { useCallback } from "react";
import { useParams } from "react-router-dom";

import Breadcrumbs from "../../components/common/Breadcrumbs";
import Card from "../../components/common/Card";
import EmptyState from "../../components/common/EmptyState";
import ErrorState from "../../components/common/ErrorState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import ClaimTabs from "../../components/surveyor/ClaimTabs";
import { useFetch } from "../../hooks/useFetch";
import { getClaimById } from "../../services/claimService";
import { getAssignedClaimDetail } from "../../services/surveyorService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatCurrency } from "../../utils/format";

export default function VehicleDamagePage() {
  const { claimId } = useParams();

  const fetchDetail = useCallback(async () => {
    const [claim, assigned] = await Promise.all([getClaimById(claimId), getAssignedClaimDetail(claimId)]);
    return { claim, ...assigned };
  }, [claimId]);

  const { data, isLoading, error, reload } = useFetch(fetchDetail, [fetchDetail]);

  if (isLoading) return <LoadingState label="Loading damage assessment..." />;
  if (error) {
    return (
      <div>
        <PageHeader title="Vehicle Damage Assessment" />
        <ErrorState message={getApiErrorMessage(error)} onRetry={reload} />
      </div>
    );
  }

  const { claim, vehicle_damage: damages } = data;

  return (
    <div>
      <Breadcrumbs
        items={[
          { label: "Assigned Claims", to: "/surveyor/claims" },
          { label: claim.Claim_Number, to: `/surveyor/claims/${claim.Claim_ID}` },
          { label: "Vehicle Damage" },
        ]}
      />
      <PageHeader title={`Vehicle Damage Assessment — ${claim.Claim_Number}`} />
      <ClaimTabs claimId={claim.Claim_ID} />

      <p className="mb-4 flex items-start gap-2 rounded-card bg-surface p-3 text-xs text-muted">
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        This assessment is read-only. There is no existing backend endpoint for a surveyor to create or
        edit vehicle damage records - only viewing already-recorded damage is currently supported. Your
        own damage observations for this claim are captured on the Inspection tab instead.
      </p>

      {damages.length === 0 ? (
        <Card>
          <EmptyState title="No damage assessment recorded for this vehicle" />
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {damages.map((damage) => (
            <Card key={damage.Damage_ID}>
              <h3 className="mb-3 text-sm font-semibold text-ink">{damage.Damaged_Part}</h3>
              <dl className="grid grid-cols-2 gap-3 text-sm">
                <Detail label="Damage Type" value={damage.Damage_Type} />
                <Detail label="Severity" value={damage.Damage_Severity} />
                <Detail label="Location" value={damage.Damage_Location} />
                <Detail label="Repair or Replace" value={damage.Repair_or_Replace} />
                <Detail label="Estimated Cost" value={formatCurrency(damage.Estimated_Damage_Cost)} />
                <Detail label="Photo Evidence" value={damage.Photo_Evidence_Available ? "Available" : "Not available"} />
              </dl>
              <div className="mt-3">
                <p className="text-xs font-medium uppercase tracking-wide text-muted">Description</p>
                <p className="mt-0.5 text-sm text-ink">{damage.Damage_Description}</p>
              </div>
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
