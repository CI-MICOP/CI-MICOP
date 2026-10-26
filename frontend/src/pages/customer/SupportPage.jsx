import { HelpCircle, LifeBuoy, MessageCircle, Phone } from "lucide-react";

import Card from "../../components/common/Card";
import EmptyState from "../../components/common/EmptyState";
import PageHeader from "../../components/common/PageHeader";
import QuickActionCard from "../../components/common/QuickActionCard";

const FAQS = [
  {
    question: "How do I file a new claim?",
    answer: "Open \"Claims\" from the menu at the bottom of the screen, choose \"File a New Claim\", and follow the four-step form: incident details, vehicle & policy, documents, then review and submit.",
  },
  {
    question: "How can I check my claim status?",
    answer: "Open \"Claims\" from the menu at the bottom of the screen and select a claim to see its current status and timeline.",
  },
  {
    question: "Where do I upload supporting documents?",
    answer: "Use \"Docs\" > \"Upload Documents\", or the document step inside the new claim form.",
  },
  {
    question: "What should I submit for this claim?",
    answer: "With every claim: a copy of the driving licence of whoever was driving, the vehicle's RC and your insurance policy, plus accident photos taken with the camera in the claim form. If the police were involved, add the FIR; if the vehicle is being repaired, add the garage's repair estimate.",
  },
  {
    question: "My insurer already has my RC, licence and policy - why upload them again?",
    answer: "Your insurer's own records and the copies you submit are kept separate. The copy you upload is checked against those records for this claim, so it is still required even if the insurer holds the details. Each copy is read for the check and is not kept - only the details needed for checking (such as the registration or policy number) are saved with your claim.",
  },
  {
    question: "Why can't I choose accident photos from my gallery?",
    answer: "Accident photos have to be taken with your device's camera in the claim form, so they show the vehicle and the scene as they are now. Photos are not chosen from your gallery or files. If the camera can't be opened, the form tells you why - allow camera access or use a device with a camera. Please don't take photos of yourself here.",
  },
  {
    question: "Does uploading a document mean it has been verified?",
    answer: "No. Uploading only sends it in. A claims officer reviews every claim and may contact you for a clearer copy or an explanation.",
  },
  {
    question: "What if a record is missing or something doesn't match?",
    answer: "Nothing is decided automatically. A document you haven't uploaded yet is different from a record your insurer doesn't hold - either way, or if details differ (for example a registration number), the claim is marked for a claims officer to review, and they may contact you.",
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
