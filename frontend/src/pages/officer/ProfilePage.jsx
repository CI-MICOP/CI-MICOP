import BackButton from "../../components/common/BackButton";
import Card from "../../components/common/Card";
import PageHeader from "../../components/common/PageHeader";
import { useAuth } from "../../hooks/useAuth";
import { formatDate } from "../../utils/format";

export default function OfficerProfilePage() {
  const { user } = useAuth();

  return (
    <div>
      <PageHeader title="Profile Settings" subtitle="Your account information on file with CI-MICOP." />
      <BackButton fallback="/officer" />
      <Card className="max-w-2xl">
        <p className="mb-4 text-xs text-muted">
          This information is read-only. Profile editing is not yet supported by the backend.
        </p>
        <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Username" value={user?.Username} />
          <Field label="Employee ID" value={user?.Employee_ID} />
          <Field label="Email" value={user?.Email} />
          <Field label="Phone" value={user?.Phone} />
          <Field label="Role" value={user?.Role} />
          <Field label="Account Status" value={user?.Account_Status} />
          <Field label="Joined" value={formatDate(user?.Created_Date)} />
          <Field label="Last Login" value={user?.Last_Login ? formatDate(user.Last_Login) : "-"} />
        </dl>
      </Card>
    </div>
  );
}

function Field({ label, value }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-muted">{label}</dt>
      <dd className="mt-0.5 text-sm text-ink">{value ?? "-"}</dd>
    </div>
  );
}
