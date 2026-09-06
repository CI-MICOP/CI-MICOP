import { HelpCircle, LifeBuoy, MessageCircle, Phone } from "lucide-react";

import Card from "../../components/common/Card";
import EmptyState from "../../components/common/EmptyState";
import PageHeader from "../../components/common/PageHeader";
import QuickActionCard from "../../components/common/QuickActionCard";

const FAQS = [
  {
    question: "How do I file a new claim?",
    answer: "Go to \"New Claim\" from the sidebar and follow the four-step form: incident details, vehicle & policy, documents, then review and submit.",
  },
  {
    question: "How can I check my claim status?",
    answer: "Open \"My Claims\" from the sidebar and select a claim to see its current status and timeline.",
  },
  {
    question: "Where do I upload supporting documents?",
    answer: "Use \"Documents\" > \"Upload Documents\", or the document step inside the New Claim form.",
  },
];

export default function SupportPage() {
  return (
    <div>
      <PageHeader title="Support" subtitle="Get help with your claims, policies, and account." />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <h3 className="mb-3 text-sm font-semibold text-ink">Raise a Request</h3>
          <QuickActionCard
            label="Raise a Request"
            description="Log an issue or ask our support team for help"
            icon={LifeBuoy}
            to="/customer/support/request"
          />
        </Card>

        <Card>
          <h3 className="mb-3 text-sm font-semibold text-ink">Chat with Support</h3>
          <EmptyState icon={MessageCircle} title="Live chat isn't available yet" message="This feature is not yet connected to a support backend." />
        </Card>

        <Card>
          <h3 className="mb-3 text-sm font-semibold text-ink">FAQs</h3>
          <ul className="space-y-4">
            {FAQS.map((faq) => (
              <li key={faq.question}>
                <p className="flex items-start gap-2 text-sm font-medium text-ink">
                  <HelpCircle className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" aria-hidden="true" />
                  {faq.question}
                </p>
                <p className="mt-1 pl-6 text-sm text-muted">{faq.answer}</p>
              </li>
            ))}
          </ul>
        </Card>

        <Card>
          <h3 className="mb-3 text-sm font-semibold text-ink">Contact Support</h3>
          <EmptyState
            icon={Phone}
            title="Contact details aren't configured yet"
            message='Use "Raise a Request" below to reach our support team in the meantime.'
          />
        </Card>

        <Card className="lg:col-span-2">
          <h3 className="mb-3 text-sm font-semibold text-ink">My Requests</h3>
          <EmptyState title="No requests yet" message="Support-request history isn't available yet." />
        </Card>
      </div>
    </div>
  );
}
