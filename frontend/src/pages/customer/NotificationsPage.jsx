import { Bell } from "lucide-react";

import Card from "../../components/common/Card";
import EmptyState from "../../components/common/EmptyState";
import PageHeader from "../../components/common/PageHeader";

/** No notifications endpoint exists on the backend yet - this is the
 * page layout and empty state only, with no fabricated notification data. */
export default function NotificationsPage() {
  return (
    <div>
      <PageHeader title="Notifications" subtitle="Updates about your claims and account." />
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
