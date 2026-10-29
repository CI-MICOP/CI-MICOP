import { Bell } from "lucide-react";

import BackButton from "../../components/common/BackButton";
import Card from "../../components/common/Card";
import EmptyState from "../../components/common/EmptyState";
import PageHeader from "../../components/common/PageHeader";

export default function OfficerNotificationsPage() {
  return (
    <div>
      <PageHeader title="Notifications" subtitle="Updates about claims in your queue." />
      <BackButton fallback="/officer" />
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
