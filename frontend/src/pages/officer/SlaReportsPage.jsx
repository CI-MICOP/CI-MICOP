import { Info } from "lucide-react";
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

export default function SlaReportsPage() {
  const fetchData = useCallback(async () => {
    const summaries = await listClaimsForProcessing({ limit: 200 });
    const details = await Promise.all(summaries.map((s) => getClaimProcessingDetail(s.Claim_ID)));
    return details.map((d) => d.claim.Claim_Processing_Days);
  }, []);
  const { data: processingDays, isLoading, error, reload } = useFetch(fetchData, [fetchData]);

  const stats = useMemo(() => {
    if (!processingDays || processingDays.length === 0) return null;
    const min = Math.min(...processingDays);
    const max = Math.max(...processingDays);
    const avg = Math.round((processingDays.reduce((a, b) => a + b, 0) / processingDays.length) * 10) / 10;
    return { min, max, avg };
  }, [processingDays]);

  if (isLoading) {
    return (
      <div>
        <PageHeader title="SLA Reports" />
        <BackButton fallback="/officer" />
        <LoadingState label="Calculating SLA metrics..." />
      </div>
    );
  }
  if (error) {
    return (
      <div>
        <PageHeader title="SLA Reports" />
        <BackButton fallback="/officer" />
        <ErrorState message={getApiErrorMessage(error)} onRetry={reload} />
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="SLA Reports" subtitle="Processing-time distribution across visible claims." />
      <BackButton fallback="/officer" />

      <p className="mb-6 flex items-start gap-2 rounded-card border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
        No SLA target/threshold is configured anywhere in the CI-MICOP database or schema. The figures
        below are real processing-time statistics only - they are not compared against any SLA target,
        and no compliance percentage is shown, because no target exists to measure against.
      </p>

      {!stats ? (
        <Card>
          <p className="text-sm text-muted">No claims available to calculate processing-time statistics.</p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatCard label="Fastest Claim (Days)" value={stats.min} />
          <StatCard label="Average Processing Days" value={stats.avg} />
          <StatCard label="Slowest Claim (Days)" value={stats.max} />
        </div>
      )}
    </div>
  );
}
