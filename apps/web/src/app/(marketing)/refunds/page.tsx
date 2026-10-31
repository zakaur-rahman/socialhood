import Link from "next/link";

import { LegalFacts, LegalPage, type LegalSection } from "@/components/marketing/legal/LegalPage";
import { LEGAL } from "@/lib/legal";
import { SITE_NAME } from "@/lib/marketing/site";
import { pageMetadata } from "@/lib/marketing/seo";

export const metadata = pageMetadata({
  title: "Refund and Cancellation Policy",
  description: `How to cancel an ${SITE_NAME} subscription, when we refund a payment, and how to ask about a charge.`,
  path: "/refunds",
});

const N = SITE_NAME;
const email = LEGAL.contactEmail;
const mail = <a href={`mailto:${email}`}>{email}</a>;

// OWNER REVIEW: a common default for a monthly SaaS (no refunds for partial periods, billing
// errors refunded), not yet a business decision. C-144 added cancelling (Razorpay and Dodo both
// ask for a "refund and cancellation" policy) and the business's own Razorpay payments. LAWYER
// REVIEW before launch (§6.4), including consumer-law refund rights where customers live.
const SECTIONS: LegalSection[] = [
  {
    id: "free-and-trial",
    title: "Free plan and the Pro trial",
    body: (
      <ul>
        <li>The Free plan costs nothing, so there is nothing to refund.</li>
        <li>
          Pro starts with a 7-day free trial, once per workspace. A card is needed to start it, but you aren&apos;t charged
          during the trial. Cancel before it ends (Settings → Billing) and you won&apos;t be charged at all.
        </li>
      </ul>
    ),
  },
  {
    id: "cancelling",
    title: "Cancelling",
    body: (
      <>
        <p>
          The workspace owner can cancel at any time in Settings → Billing, with no cancellation fee. The cancellation takes
          effect at the end of the period you&apos;ve paid for: Pro stays active until then, and you can resume before it
          ends. After that the workspace moves to Free, and nothing more is charged.
        </p>
        <p>
          Deleting your workspace (Settings → Workspace) cancels an active subscription at once. If you can&apos;t reach
          Settings, email {mail} from the owner&apos;s email address and we&apos;ll cancel it for you.
        </p>
      </>
    ),
  },
  {
    id: "subscriptions",
    title: "Refunds for Pro subscriptions",
    body: (
      <>
        <p>
          Pro is paid monthly, in advance. Because you keep full access for the period you&apos;ve paid for, we don&apos;t
          refund:
        </p>
        <ul>
          <li>the rest of a period after you cancel or move to Free;</li>
          <li>AI credits or other allowances you didn&apos;t use;</li>
          <li>a renewal you forgot to cancel, once that period has started and Pro has been used.</li>
        </ul>
        <p>If you think a renewal shouldn&apos;t have happened, write to us anyway and we&apos;ll look at it.</p>
      </>
    ),
  },
  {
    id: "billing-errors",
    title: "Billing errors",
    body: (
      <>
        <p>We refund charges that were our mistake or the payment system&apos;s, for example:</p>
        <ul>
          <li>being charged twice for the same period, or for two subscriptions on one workspace;</li>
          <li>being charged after cancelling in time;</li>
          <li>being charged the wrong amount.</li>
        </ul>
        <p>Email {mail} within 30 days of the charge so we can check it with Dodo Payments.</p>
      </>
    ),
  },
  {
    id: "how-refunds-work",
    title: "How refunds are paid",
    body: (
      <p>
        Dodo Payments is the merchant of record for our subscriptions, so refunds go back to the original payment method
        through Dodo Payments. How long a refund takes to appear depends on your bank or card issuer.
      </p>
    ),
  },
  {
    id: "your-customers",
    title: "Payments to businesses that use us",
    body: (
      <p>
        When you pay a business through a payment link or UPI it sends from {N}, you are paying that business through its
        own Razorpay account, not us. Ask that business about cancelling an order or getting a refund; {N} only helps it
        send the link and record the payment.
      </p>
    ),
  },
  {
    id: "your-rights",
    title: "Your legal rights",
    body: <p>This policy doesn&apos;t take away any refund rights that the law where you live gives you.</p>,
  },
  {
    id: "contact",
    title: "Ask about a charge",
    body: (
      <>
        <p>
          Email {mail} with your workspace&apos;s name, the date and amount of the charge, and the email address used at
          checkout. Our <Link href="/contact">contact page</Link> has more ways to reach us.
        </p>
        <LegalFacts />
      </>
    ),
  },
];

export default function RefundsPage() {
  return (
    <LegalPage
      document="refunds"
      sections={SECTIONS}
      summary={
        <p>
          Cancel anytime in Settings → Billing and keep Pro until the end of the period you&apos;ve paid for. We don&apos;t
          refund partial periods or unused credits, but we always refund billing mistakes. Questions about a charge? Email{" "}
          {mail}.
        </p>
      }
    />
  );
}
