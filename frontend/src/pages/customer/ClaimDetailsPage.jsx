import { Clock, FolderOpen } from "lucide-react";
import { useCallback, useMemo } from "react";
import { Link, useParams } from "react-router-dom";

import Breadcrumbs from "../../components/common/Breadcrumbs";
import Button from "../../components/common/Button";
import Card from "../../components/common/Card";
import EmptyState from "../../components/common/EmptyState";
import ErrorState from "../../components/common/ErrorState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import StatusBadge from "../../components/common/StatusBadge";
import { useFetch } from "../../hooks/useFetch";
import { getClaimById } from "../../services/claimService";
import { listDocumentsByClaim } from "../../services/documentService";
import { getPolicyById } from "../../services/policyService";
import { getVehicleById } from "../../services/vehicleService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatCurrency, formatDate, formatVehicleLabel } from "../../utils/format";
import { getStatusTone } from "../../utils/statusTone";

export default function ClaimDetailsPage() {
  const { claimId } = useParams();

  const fetchDetail = useCallback(async () => {
    const claim = await getClaimById(claimId);
    const [vehicle, policy, documents] = await Promise.all([
      getVehicleById(claim.Vehicle_ID),
      getPolicyById(claim.Policy_ID),
      listDocumentsByClaim(claim.Claim_ID),
    ]);
    return { claim, vehicle, policy, documents };
  }, [claimId]);

  const { data, isLoading, error, reload } = useFetch(fetchDetail, [fetchDetail]);

  const recentActivity = useMemo(() => {
    if (!data) return [];
    const events = [
      { id: "submitted", date: data.claim.Claim_Date, text: `Claim submitted (${data.claim.Claim_Type})` },
      ...data.documents.map((doc) => ({
        id: `doc-${doc.Document_ID}`,
        date: doc.Document_Submitted_Date,
        text: `${doc.Document_Type} uploaded (${doc.Document_Status})`,
      })),
    ];
    if (data.claim.Final_Decision) {
      events.push({
        id: "decision",
        date: data.claim.Decision_Date,
        text: `Decision recorded: ${data.claim.Final_Decision}`,
      });
    }
    return events.sort((a, b) => new Date(b.date) - new Date(a.date));
  }, [data]);

  if (isLoading) return <LoadingState label="Loading claim details..." />;
  if (error) {
    return (
      <div>
        <PageHeader title="Claim Details" />
        <ErrorState
          title={error.response?.status === 404 ? "Claim not found" : "Unable to load this claim"}
          message={getApiErrorMessage(error)}
          onRetry={reload}
        />
      </div>
    );
  }

  const { claim, vehicle, policy, documents } = data;

  return (
    <div>
      <Breadcrumbs
        items={[
          { label: "My Claims", to: "/customer/claims" },
          { label: claim.Claim_Number },
        ]}
      />
      <PageHeader
        title={`Claim ${claim.Claim_Number}`}
        subtitle={`Filed on ${formatDate(claim.Claim_Date)}`}
        actions={
          <Link to={`/customer/claims/${claim.Claim_ID}/timeline`}>
            <Button variant="secondary">
              <Clock className="h-4 w-4" aria-hidden="true" />
              View Timeline
            </Button>
          </Link>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <h3 className="mb-4 text-sm font-semibold text-ink">Claim Information</h3>
            <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Detail label="Claim Status">
                <StatusBadge label={claim.Claim_Status} tone={getStatusTone(claim.Claim_Status)} />
              </Detail>
              <Detail label="Claim Type" value={claim.Claim_Type} />
              <Detail label="Claim Amount" value={formatCurrency(claim.Claim_Amount)} />
              <Detail label="Approved Amount" value={formatCurrency(claim.Approved_Amount)} />
              <Detail label="Current Stage" value={claim.Claim_Status} />
              <Detail label="Final Decision" value={claim.Final_Decision || "Pending"} />
            </dl>
          </Card>

          <Card>
            <h3 className="mb-4 text-sm font-semibold text-ink">Accident Information</h3>
            <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Detail label="Place of Accident" value={claim.Place_of_Accident} />
              <Detail label="Accident Pincode" value={claim.Accident_Pincode} />
            </dl>
            <div className="mt-4">
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted">Description</p>
              <p className="text-sm text-ink">{claim.Claim_Description}</p>
            </div>
          </Card>

          <Card>
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-ink">Documents</h3>
              <Link to="/customer/documents" className="text-sm font-medium text-brand-600 hover:text-brand-700">
                View all
              </Link>
            </div>
            {documents.length === 0 ? (
              <EmptyState icon={FolderOpen} title="No documents uploaded for this claim" />
            ) : (
              <ul className="divide-y divide-border">
                {documents.map((doc) => (
                  <li key={doc.Document_ID} className="flex items-center justify-between py-2.5 text-sm">
                    <div className="min-w-0">
                      <p className="truncate text-ink">{doc.Document_Type}</p>
                      <p className="truncate text-xs text-muted">{doc.Document_Name}</p>
                      <p className="text-xs text-muted">{formatDate(doc.Document_Submitted_Date)}</p>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1">
                      <StatusBadge label={doc.Document_Status} tone={getStatusTone(doc.Document_Status)} />
                      <StatusBadge label={doc.Verification_Status} tone={getStatusTone(doc.Verification_Status)} />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <h3 className="mb-3 text-sm font-semibold text-ink">Policy</h3>
            <p className="text-sm font-medium text-ink">{policy.Policy_Number}</p>
            <p className="text-sm text-muted">{policy.Policy_Type}</p>
            <Link to={`/customer/policies`} className="mt-2 inline-block text-sm text-brand-600 hover:text-brand-700">
              View policy
            </Link>
          </Card>

          <Card>
            <h3 className="mb-3 text-sm font-semibold text-ink">Vehicle</h3>
            <p className="text-sm font-medium text-ink">{formatVehicleLabel(vehicle)}</p>
            <p className="text-sm text-muted">{vehicle.Fuel_Type} &middot; {vehicle.Manufacturing_Year}</p>
          </Card>

          <Card>
            <h3 className="mb-3 text-sm font-semibold text-ink">Recent Activity</h3>
            {recentActivity.length === 0 ? (
              <p className="text-sm text-muted">No activity recorded yet.</p>
            ) : (
              <ul className="space-y-3">
                {recentActivity.slice(0, 5).map((event) => (
                  <li key={event.id} className="text-sm">
                    <p className="text-ink">{event.text}</p>
                    <p className="text-xs text-muted">{formatDate(event.date)}</p>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}

function Detail({ label, value, children }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-muted">{label}</dt>
      <dd className="mt-0.5 text-sm text-ink">{children ?? value}</dd>
    </div>
  );
}
