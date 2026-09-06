import { AlertTriangle } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import Breadcrumbs from "../../components/common/Breadcrumbs";
import Button from "../../components/common/Button";
import Card from "../../components/common/Card";
import PageHeader from "../../components/common/PageHeader";

const CATEGORIES = ["Claim Issue", "Policy Question", "Document Issue", "Account Issue", "Other"];

const EMPTY_FORM = { subject: "", category: "", description: "", attachment: null };

export default function SupportRequestPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState(EMPTY_FORM);
  const [submitAttempted, setSubmitAttempted] = useState(false);
  const [touched, setTouched] = useState(false);

  const isValid = form.subject.trim() && form.category && form.description.trim();

  function update(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  function handleSubmit(event) {
    event.preventDefault();
    setTouched(true);
    if (!isValid) return;
    setSubmitAttempted(true);
  }

  return (
    <div>
      <Breadcrumbs items={[{ label: "Support", to: "/customer/support" }, { label: "Raise a Request" }]} />
      <PageHeader title="Support Request" subtitle="Tell us what you need help with." />

      <Card className="max-w-xl">
        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <Field label="Subject" required>
            <input
              type="text"
              value={form.subject}
              onChange={(e) => update("subject", e.target.value)}
              className="input"
            />
            {touched && !form.subject.trim() && <p className="mt-1 text-xs text-danger">Subject is required.</p>}
          </Field>

          <Field label="Category" required>
            <select value={form.category} onChange={(e) => update("category", e.target.value)} className="input">
              <option value="">Select a category</option>
              {CATEGORIES.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
            {touched && !form.category && <p className="mt-1 text-xs text-danger">Please select a category.</p>}
          </Field>

          <Field label="Description" required>
            <textarea
              value={form.description}
              onChange={(e) => update("description", e.target.value)}
              rows={4}
              className="input resize-none"
              placeholder="Describe your issue in detail..."
            />
            {touched && !form.description.trim() && <p className="mt-1 text-xs text-danger">Description is required.</p>}
          </Field>

          <Field label="Attach File (Optional)">
            <input
              type="file"
              onChange={(e) => update("attachment", e.target.files?.[0] ?? null)}
              className="block w-full text-sm text-muted file:mr-3 file:rounded-lg file:border-0 file:bg-surface file:px-3 file:py-1.5 file:text-sm file:text-ink"
            />
          </Field>

          {submitAttempted && (
            <div className="flex gap-3 rounded-card border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
              <AlertTriangle className="h-5 w-5 shrink-0 text-warning" aria-hidden="true" />
              <div>
                <p className="font-medium">Support requests are not yet connected to the backend</p>
                <p className="mt-1 text-amber-800">
                  There is currently no support-request API. Your request has not been sent or saved.
                </p>
              </div>
            </div>
          )}

          <div className="flex justify-end gap-3 border-t border-border pt-4">
            <Button type="button" variant="secondary" onClick={() => navigate("/customer/support")}>
              Cancel
            </Button>
            <Button type="submit">Submit Request</Button>
          </div>
        </form>
      </Card>
    </div>
  );
}

function Field({ label, required, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-ink">
        {label}
        {required && <span className="text-danger"> *</span>}
      </span>
      {children}
    </label>
  );
}
