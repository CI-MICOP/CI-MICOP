import Card from "../../components/common/Card";
import ErrorState from "../../components/common/ErrorState";
import LoadingState from "../../components/common/LoadingState";
import PageHeader from "../../components/common/PageHeader";
import { useFetch } from "../../hooks/useFetch";
import { getMyProfile } from "../../services/customerService";
import { getApiErrorMessage } from "../../utils/errors";
import { formatDate } from "../../utils/format";

export default function ProfilePage() {
  const { data: profile, isLoading, error, reload } = useFetch(getMyProfile, []);

  if (isLoading) return <LoadingState label="Loading your profile..." />;
  if (error) {
    return (
      <div>
        <PageHeader title="My Profile" />
        <ErrorState message={getApiErrorMessage(error)} onRetry={reload} />
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="My Profile" subtitle="Your personal information on file with CI-MICOP." />
      <Card className="max-w-2xl">
        <p className="mb-4 text-xs text-muted">
          This information is read-only. Profile editing is not yet supported by the backend.
        </p>
        <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Full Name" value={profile.Customer_Name} />
          <Field label="Date of Birth" value={formatDate(profile.Date_of_Birth)} />
          <Field label="Phone" value={profile.Phone} />
          <Field label="Email" value={profile.Email} />
          <Field label="Address" value={profile.Address} full />
          <Field label="City" value={profile.City} />
          <Field label="State" value={profile.State} />
          <Field label="Pincode" value={profile.Pincode} />
          <Field label="Customer Type" value={profile.Customer_Type} />
          <Field label="Occupation" value={profile.Occupation} />
        </dl>
      </Card>
    </div>
  );
}

function Field({ label, value, full }) {
  return (
    <div className={full ? "sm:col-span-2" : undefined}>
      <dt className="text-xs font-medium uppercase tracking-wide text-muted">{label}</dt>
      <dd className="mt-0.5 text-sm text-ink">{value}</dd>
    </div>
  );
}
