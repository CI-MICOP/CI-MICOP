import { MessageCircle } from "lucide-react";

import BackButton from "../../components/common/BackButton";
import Card from "../../components/common/Card";
import EmptyState from "../../components/common/EmptyState";
import PageHeader from "../../components/common/PageHeader";

export default function RfiPage() {
  return (
    <div>
      <PageHeader title="RFI / Clarifications" subtitle="Requests for information sent to customers or surveyors." />
      <BackButton fallback="/officer" />
      <Card>
        <EmptyState
          icon={MessageCircle}
          title="RFI functionality isn't available yet"
          message="There is no RFI/clarification data model or endpoint in the current backend. This page will become functional once that capability is added."
        />
      </Card>
    </div>
  );
}
