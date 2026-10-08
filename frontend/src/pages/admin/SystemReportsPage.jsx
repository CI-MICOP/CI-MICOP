import { useCallback } from "react";

import CountBars from "../../components/admin/CountBars";
import Card from "../../components/common/Card";
import ErrorState from "../../components/common/ErrorState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import StatCard from "../../components/common/StatCard";
import { useFetch } from "../../hooks/useFetch";
import { listAllUsers } from "../../services/adminService";
import { listClaimsForProcessing } from "../../services/officerService";
import { countBy, countUsersByRole } from "../../utils/adminStats";
import { getApiErrorMessage } from "../../utils/errors";
import { formatCurrency } from "../../utils/format";

const CLAIM_LIMIT = 200; // the largest page the claims-listing endpoint allows

export default function SystemReportsPage() {
  const fetchReport = useCallback(async () => {
    const [users, claims] = await Promise.all([listAllUsers(), listClaimsForProcessing({ limit: CLAIM_LIMIT })]);
    return { users, claims };
  }, []);
  const { data, isLoading, error, reload } = useFetch(fetchReport, [fetchReport]);

  if (isLoading) {
    return (
      <div>
        <PageHeader title="System Reports" />
        <LoadingState label="Building reports..." />
      </div>
    );
  }
  if (error) {
    return (
      <div>
        <PageHeader title="System Reports" />
        <ErrorState message={getApiErrorMessage(error)} onRetry={reload} />
      </div>
    );
  }

  const { users, claims } = data;
  const totalClaimed = claims.reduce((sum, claim) => sum + Number(claim.Claim_Amount || 0), 0);
  const usersWithFailedLogins = users.filter((u) => u.Failed_Login_Count > 0).length;

  return (
    <div>
      <PageHeader title="System Reports" subtitle="Users and claims in numbers." />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="User Accounts" value={users.length} />
        <StatCard label="Accounts with Failed Logins" value={usersWithFailedLogins} />
        <StatCard label="Claims" value={claims.length} />
        <StatCard label="Total Amount Claimed" value={formatCurrency(totalClaimed)} />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <CountBars title="Users by Role" rows={countUsersByRole(users)} emptyMessage="No user accounts." />
        <CountBars title="Users by Account Status" rows={countBy(users, (u) => u.Account_Status)} emptyMessage="No user accounts." />
        <CountBars title="Claims by Status" rows={countBy(claims, (c) => c.Claim_Status)} emptyMessage="No claims." />
        <CountBars title="Claims by Final Decision" rows={countBy(claims, (c) => c.Final_Decision)} emptyMessage="No claims." />
        <CountBars title="Claims by Type" rows={countBy(claims, (c) => c.Claim_Type)} emptyMessage="No claims." />
      </div>

      <Card className="mt-6">
        <p className="text-sm text-muted">
          Every figure is counted from the user and claim lists returned by the API - nothing is estimated.
          {claims.length === CLAIM_LIMIT &&
            ` The claims-listing endpoint returns at most ${CLAIM_LIMIT} claims, so the claim figures cover the most recent ${CLAIM_LIMIT} only.`}
        </p>
      </Card>
    </div>
  );
}
