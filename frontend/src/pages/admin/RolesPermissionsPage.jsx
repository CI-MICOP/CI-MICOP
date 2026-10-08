import { Info } from "lucide-react";

import Card from "../../components/common/Card";
import ErrorState from "../../components/common/ErrorState";
import PageHeader from "../../components/common/PageHeader";
import { useFetch } from "../../hooks/useFetch";
import { listAllUsers } from "../../services/adminService";
import { countUsersByRole } from "../../utils/adminStats";
import { getApiErrorMessage } from "../../utils/errors";

// What each role can and cannot do, written out from the access rules the
// backend enforces (backend/app/api/v1/deps.py, services/claim_access.py
// and each router's dependencies). If those rules change, update this
// list with them - it is a description, not the source of the rules.
const ROLES = [
  {
    role: "Customer",
    can: [
      "File a new claim on their own policy",
      "Upload documents to their own claims",
      "View their own claims, documents, policies, vehicles and profile",
    ],
    cannot: ["See another customer's records", "Use any surveyor, officer or admin function"],
  },
  {
    role: "Surveyor",
    can: [
      "View the claims assigned to them",
      "Start and update their own inspections, and submit the survey report",
      "Record vehicle damage, repair estimates and evidence on assigned claims",
    ],
    cannot: ["See claims assigned to another surveyor", "Record a claim decision", "Use any admin function"],
  },
  {
    role: "Claims Officer",
    can: [
      "View every claim",
      "Assign a surveyor to a claim",
      "Run the AI analysis and the document, evidence and repair-estimate checks",
      "Record the final decision on a claim",
    ],
    cannot: ["File claims or upload documents for a customer", "Record surveyor findings", "Use any admin function"],
  },
  {
    role: "Admin",
    can: [
      "View every user account",
      "View every claim and its decision audit trail",
      "Assign a surveyor to a claim",
      "Run the AI analysis and the document, evidence and repair-estimate checks",
      "Update any inspection",
    ],
    cannot: [
      "Record the final decision on a claim (Claims Officer only)",
      "File claims or upload documents (Customer only)",
      "Record vehicle damage, repair estimates or evidence (Surveyor only)",
    ],
  },
];

export default function RolesPermissionsPage() {
  const { data: users, isLoading, error, reload } = useFetch(listAllUsers, []);
  const counts = new Map(countUsersByRole(users ?? []));

  return (
    <div>
      <PageHeader title="Roles & Permissions" subtitle="What each role can do in CI-MICOP." />

      <p className="mb-6 flex items-start gap-2 rounded-card border border-surface bg-surface p-3 text-xs text-muted">
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        Roles are fixed in the application and are checked by the server on every request. They cannot be edited
        here, and the backend has no endpoint to change a user's role.
      </p>

      {error && <ErrorState message={getApiErrorMessage(error)} onRetry={reload} />}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {ROLES.map(({ role, can, cannot }) => (
          <Card key={role}>
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-ink">{role}</h2>
              {!error && (
                <span className="text-xs text-muted">{isLoading ? "Counting accounts..." : `${counts.get(role) ?? 0} account(s)`}</span>
              )}
            </div>
            <PermissionList title="Can" items={can} />
            <PermissionList title="Cannot" items={cannot} />
          </Card>
        ))}
      </div>
    </div>
  );
}

function PermissionList({ title, items }) {
  return (
    <div className="mt-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted">{title}</p>
      <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-ink">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
