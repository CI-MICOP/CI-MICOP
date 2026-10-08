import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import Card from "../../components/common/Card";
import ErrorState from "../../components/common/ErrorState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import StatusBadge from "../../components/common/StatusBadge";
import { useFetch } from "../../hooks/useFetch";
import { getUserById } from "../../services/adminService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatDate } from "../../utils/format";
import { getStatusTone } from "../../utils/statusTone";

export default function UserDetailsPage() {
  const { userId } = useParams();
  const { data: user, isLoading, error, reload } = useFetch(() => getUserById(userId), [userId]);

  const backLink = (
    <Link to="/admin/users" className="inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:text-brand-700">
      <ArrowLeft className="h-4 w-4" aria-hidden="true" />
      Back to users
    </Link>
  );

  if (isLoading) {
    return (
      <div>
        <PageHeader title="User" actions={backLink} />
        <LoadingState label="Loading user..." />
      </div>
    );
  }
  if (error) {
    return (
      <div>
        <PageHeader title="User" actions={backLink} />
        <ErrorState message={getApiErrorMessage(error)} onRetry={reload} />
      </div>
    );
  }

  return (
    <div>
      <PageHeader title={user.Username} subtitle={`${user.Role} account`} actions={backLink} />
      <Card className="max-w-3xl">
        <p className="mb-4 text-xs text-muted">
          This information is read-only. Editing or disabling an account is not yet supported by the backend.
        </p>
        <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="User ID" value={user.User_ID} />
          <Field label="Username" value={user.Username} />
          <Field label="Role" value={user.Role} />
          <Field label="Permission Level" value={user.Permission_Level} />
          <Field label="Customer ID" value={user.Customer_ID} />
          <Field label="Employee ID" value={user.Employee_ID} />
          <Field label="Email" value={user.Email} />
          <Field label="Phone" value={user.Phone} />
          <Field
            label="Account Status"
            value={<StatusBadge label={user.Account_Status} tone={getStatusTone(user.Account_Status)} />}
          />
          <Field label="Login Status" value={user.Login_Status} />
          <Field label="Created" value={formatDate(user.Created_Date)} />
          <Field label="Last Login" value={formatDate(user.Last_Login)} />
          <Field label="Failed Logins in a Row" value={user.Failed_Login_Count} />
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
