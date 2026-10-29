import { ArrowUpCircle } from "lucide-react";

import BackButton from "../../components/common/BackButton";
import Card from "../../components/common/Card";
import EmptyState from "../../components/common/EmptyState";
import PageHeader from "../../components/common/PageHeader";

export default function EscalationsPage() {
  return (
    <div>
      <PageHeader title="Escalations" subtitle="Claims escalated for further review." />
      <BackButton fallback="/officer" />
      <Card>
        <EmptyState
          icon={ArrowUpCircle}
          title="No dedicated escalations endpoint exists yet"
          message="The backend has no bulk endpoint listing escalated claims. Escalation status for an individual claim can be reviewed on that claim's Make Decision tab or in Audit Logs."
        />
      </Card>
    </div>
  );
}
