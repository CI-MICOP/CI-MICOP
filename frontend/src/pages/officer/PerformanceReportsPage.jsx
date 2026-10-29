import { useCallback, useMemo } from "react";

import BackButton from "../../components/common/BackButton";
import Card from "../../components/common/Card";
import ErrorState from "../../components/common/ErrorState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import StatCard from "../../components/common/StatCard";
import { useFetch } from "../../hooks/useFetch";
import { getClaimProcessingDetail, listClaimsForProcessing } from "../../services/officerService";
import { getApiErrorMessage } from "../../utils/errors";

export default function PerformanceReportsPage() {
  const fetchData = useCallback(async () => {
    const summaries = await listClaimsForProcessing({ limit: 200 });
    const details = await Promise.all(summaries.map((s) => getClaimProcessingDetail(s.Claim_ID)));
    return { summaries, details };
  }, []);
  const { data, isLoading, error, reload } = useFetch(fetchData, [fetchData]);

  const metrics = useMemo(() => {
    if (!data) return null;
    const { summaries, details } = data;
    const decisionsCompleted = summaries.filter((c) => c.Final_Decision).length;
    const processingDays = details.map((d) => d.claim.Claim_Processing_Days);
    const repairDays = details.map((d) => d.claim.Repair_Duration_Days);
    const average = (arr) => (arr.length ? Math.round((arr.reduce((a, b) => a + b, 0) / arr.length) * 10) / 10 : null);
    return {
      claimsHandled: summaries.length,
      decisionsCompleted,
      avgProcessingDays: average(processingDays),
      avgRepairDays: average(repairDays),
    };
  }, [data]);

  if (isLoading) {
    return (
      <div>
        <PageHeader title="Performance Reports" />
        <BackButton fallback="/officer" />
        <LoadingState label="Calculating performance metrics..." />
      </div>
    );
  }
  if (error) {
    return (
      <div>
        <PageHeader title="Performance Reports" />
        <BackButton fallback="/officer" />
        <ErrorState message={getApiErrorMessage(error)} onRetry={reload} />
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="Performance Reports" subtitle={`Calculated from the ${data.summaries.length} claims currently visible to this role (API cap: 200).`} />
      <BackButton fallback="/officer" />
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard label="Claims Handled" value={metrics.claimsHandled} />
        <StatCard label="Decisions Completed" value={metrics.decisionsCompleted} />
        <StatCard label="Avg. Processing Days" value={metrics.avgProcessingDays ?? "N/A"} />
        <StatCard label="Avg. Repair Duration (Days)" value={metrics.avgRepairDays ?? "N/A"} />
      </div>
      <Card className="mt-6">
        <p className="text-sm text-muted">
          These metrics are computed directly from real <code>Claim_Processing_Days</code> and{" "}
          <code>Repair_Duration_Days</code> values returned by the API - nothing here is estimated or
          invented. If the system holds more than 200 claims, this report only covers the most recent 200,
          since that is the maximum page size the claims-listing endpoint supports.
        </p>
      </Card>
    </div>
  );
}
