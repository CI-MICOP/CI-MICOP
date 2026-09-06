import { Bell } from "lucide-react";

import Card from "../../components/common/Card";
import EmptyState from "../../components/common/EmptyState";
import PageHeader from "../../components/common/PageHeader";

export default function SurveyorNotificationsPage() {
  return (
    <div>
      <PageHeader title="Notifications" subtitle="Updates about your assigned claims." />
      <Card>
        <EmptyState
          icon={Bell}
          title="Notifications aren't available yet"
          message="This feature is not yet connected to a backend notifications API."
        />
      </Card>
    </div>
  );
}
