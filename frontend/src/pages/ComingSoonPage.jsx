import { Construction } from "lucide-react";
import { useLocation } from "react-router-dom";

import EmptyState from "../components/common/EmptyState";
import PageHeader from "../components/common/PageHeader";

/**
 * Placeholder for every nav item that has a route but no page yet.
 * Keeps the navigation and layout foundation demonstrably complete
 * without inventing dashboard content ahead of its Step 4 sub-step.
 */
export default function ComingSoonPage() {
  const location = useLocation();

  return (
    <div>
      <PageHeader title="Coming soon" subtitle={location.pathname} />
      <EmptyState
        icon={Construction}
        title="This section is under construction"
        message="This page will be implemented in a later Step 4 sub-step."
      />
    </div>
  );
}
