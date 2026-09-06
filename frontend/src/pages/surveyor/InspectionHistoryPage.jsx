import { useCallback, useMemo } from "react";
import { Link } from "react-router-dom";

import Card from "../../components/common/Card";
import DataTable from "../../components/common/DataTable";
import ErrorState from "../../components/common/ErrorState";
import PageHeader from "../../components/common/PageHeader";
import StatusBadge from "../../components/common/StatusBadge";
import { useFetch } from "../../hooks/useFetch";
import { listClaims } from "../../services/claimService";
import { getMyInspections } from "../../services/surveyorService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatDate } from "../../utils/format";
import { getStatusTone } from "../../utils/statusTone";

export default function InspectionHistoryPage() {
  const fetchData = useCallback(async () => {
    const [inspections, claims] = await Promise.all([getMyInspections(), listClaims({ limit: 200 })]);
    return { inspections, claims };
  }, []);
  const { data, isLoading, error, reload } = useFetch(fetchData, [fetchData]);

  const claimById = useMemo(() => {
    const map = new Map();
    (data?.claims ?? []).forEach((c) => map.set(c.Claim_ID, c));
    return map;
  }, [data]);

  return (
    <div>
      <PageHeader title="Inspection History" subtitle="All inspections you have carried out." />

      {error ? (
        <ErrorState message={getApiErrorMessage(error)} onRetry={reload} />
      ) : (
        <Card>
          <DataTable
            isLoading={isLoading}
            rows={data?.inspections ?? []}
            rowKey="Inspection_ID"
            emptyMessage="No inspection history yet."
            columns={[
              {
                key: "claim",
                header: "Claim",
                render: (i) => claimById.get(i.Claim_ID)?.Claim_Number ?? i.Claim_ID,
              },
              { key: "date", header: "Inspection Date", render: (i) => formatDate(i.Inspection_Date) },
              { key: "vehicle", header: "Vehicle", render: (i) => claimById.get(i.Claim_ID)?.Vehicle_ID ?? "-" },
              { key: "location", header: "Location", render: (i) => i.Inspection_Location },
              {
                key: "status",
                header: "Status",
                render: (i) => <StatusBadge label={i.Inspection_Status} tone={getStatusTone(i.Inspection_Status)} />,
              },
              {
                key: "report",
                header: "Report Status",
                render: (i) => (
                  <StatusBadge
                    label={i.Survey_Report_Submitted ? "Submitted" : "Not Submitted"}
                    tone={i.Survey_Report_Submitted ? "success" : "warning"}
                  />
                ),
              },
              {
                key: "action",
                header: "Action",
                render: (i) => (
                  <Link to={`/surveyor/claims/${i.Claim_ID}`} className="font-medium text-brand-600 hover:text-brand-700">
                    View Claim
                  </Link>
                ),
              },
            ]}
          />
        </Card>
      )}
    </div>
  );
}
