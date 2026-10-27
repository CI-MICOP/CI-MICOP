import Card from "../../components/common/Card";
import DataTable from "../../components/common/DataTable";
import ErrorState from "../../components/common/ErrorState";
import PageHeader from "../../components/common/PageHeader";
import StatusBadge from "../../components/common/StatusBadge";
import SurveyReportActions from "../../components/surveyor/SurveyReportActions";
import { useFetch } from "../../hooks/useFetch";
import { getSurveyReports } from "../../services/surveyorService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatDate } from "../../utils/format";

/**
 * Survey Reports history: the surveyor's submitted reports
 * (GET /surveyor/survey-reports). Opening one shows the read-only report
 * document - it never reopens the inspection workflow.
 */
export default function InspectionHistoryPage() {
  const { data, isLoading, error, reload } = useFetch(getSurveyReports, []);
  const rows = (data ?? []).map((row) => ({ ...row, key: row.inspection.Inspection_ID }));

  return (
    <div>
      <PageHeader title="Survey Reports" subtitle="Survey reports you have submitted." />

      {error ? (
        <ErrorState message={getApiErrorMessage(error)} onRetry={reload} />
      ) : (
        <Card>
          <DataTable
            isLoading={isLoading}
            rows={rows}
            rowKey="key"
            emptyMessage="No submitted survey reports yet."
            columns={[
              { key: "claim", header: "Claim", render: (r) => r.claim?.Claim_Number ?? r.inspection.Claim_ID },
              { key: "vehicle", header: "Vehicle", render: (r) => r.claim?.Vehicle_ID ?? "-" },
              { key: "date", header: "Inspection Date", render: (r) => formatDate(r.inspection.Inspection_Date) },
              { key: "location", header: "Location", render: (r) => r.inspection.Inspection_Location },
              { key: "status", header: "Report Status", render: () => <StatusBadge label="Submitted" tone="success" /> },
              {
                key: "action",
                header: "Document",
                // Centred, so the "Document" header sits midway over its two actions.
                align: "center",
                render: (r) => (
                  <SurveyReportActions
                    inspectionId={r.inspection.Inspection_ID}
                    claimNumber={r.claim?.Claim_Number}
                    viewLabel="View Document"
                    downloadLabel="Download Document"
                    size="sm"
                    centered
                  />
                ),
              },
            ]}
          />
        </Card>
      )}
    </div>
  );
}
