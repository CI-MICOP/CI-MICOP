import { HelpCircle, Phone } from "lucide-react";

import Card from "../../components/common/Card";
import EmptyState from "../../components/common/EmptyState";
import PageHeader from "../../components/common/PageHeader";

const FAQS = [
  {
    question: "How do I update an inspection?",
    answer: "Open the claim from \"Inspections\" on the menu at the bottom of the screen, go to the Inspection tab, edit the fields, and click Save Inspection.",
  },
  {
    question: "How do I submit a survey report?",
    answer: "Open the claim's Survey Report tab and click \"Submit Survey Report\" once your inspection findings are complete.",
  },
  {
    question: "Where can I see my past inspections?",
    answer: "Open \"Survey Reports\" on the menu at the bottom of the screen to see every inspection you have carried out and whether its report was submitted.",
  },
];

export default function SurveyorSupportPage() {
  return (
    <div>
      <PageHeader title="Support" subtitle="Get help with inspections and claim assignments." />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card className="lg:col-span-2">
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
