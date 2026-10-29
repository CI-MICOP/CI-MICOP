import { HelpCircle, MessageCircle, Phone } from "lucide-react";

import BackButton from "../../components/common/BackButton";
import Card from "../../components/common/Card";
import EmptyState from "../../components/common/EmptyState";
import PageHeader from "../../components/common/PageHeader";

const FAQS = [
  {
    question: "How do I review a claim?",
    answer: "Open \"My Work Queue\" or \"All Claims\", then select a claim to review its details, documents, fraud risk, and estimates across the claim's tabs.",
  },
  {
    question: "Where do I record a decision?",
    answer: "Open the claim's \"Make Decision\" tab. Final decisions are always made by you - AI provides decision support only.",
  },
  {
    question: "Where can I see a claim's audit trail?",
    answer: "Use \"Audit Logs\" from the sidebar and select the claim.",
  },
];

export default function OfficerSupportPage() {
  return (
    <div>
      <PageHeader title="Help & Support" subtitle="Get help with claims processing and decisions." />
      <BackButton fallback="/officer" />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <h3 className="mb-3 text-sm font-semibold text-ink">Chat with Support</h3>
          <EmptyState icon={MessageCircle} title="Live chat isn't available yet" message="This feature is not yet connected to a support backend." />
        </Card>

        <Card>
          <h3 className="mb-3 text-sm font-semibold text-ink">Contact Support</h3>
          <EmptyState icon={Phone} title="Contact details aren't configured yet" message="Support-request submission isn't connected to a backend yet." />
        </Card>

        <Card className="lg:col-span-2">
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
      </div>
    </div>
  );
}
