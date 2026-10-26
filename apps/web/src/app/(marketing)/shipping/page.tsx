import Link from "next/link";

import { LegalFacts, LegalPage, type LegalSection } from "@/components/marketing/legal/LegalPage";
import { LEGAL } from "@/lib/legal";
import { SITE_NAME } from "@/lib/marketing/site";
import { pageMetadata } from "@/lib/marketing/seo";

export const metadata = pageMetadata({
  title: "Shipping and Delivery Policy",
  description: `${SITE_NAME} is software delivered online: nothing is shipped. When your plan starts and how to get help if it doesn't.`,
  path: "/shipping",
});

const N = SITE_NAME;
const email = LEGAL.contactEmail;
const mail = <a href={`mailto:${email}`}>{email}</a>;

// C-144: payment providers (Razorpay in particular) look for a shipping or delivery policy on the
// site. A SaaS ships nothing, so this short page says so, with when access starts. Its own page
// rather than only a Terms section, so a reviewer finds it under its usual name.
const SECTIONS: LegalSection[] = [
  {
    id: "nothing-shipped",
    title: "Nothing is shipped",
    body: (
      <p>
        {N} is software you use online in your web browser or as an installed web app. We don&apos;t sell or ship physical
        goods, so there are no shipping charges, couriers or delivery addresses.
      </p>
    ),
  },
  {
    id: "when-it-starts",
    title: "When you get access",
    body: (
      <ul>
        <li>The Free plan is available as soon as you sign up.</li>
        <li>
          Pro and its 7-day trial start as soon as checkout succeeds: your workspace shows the plan within a few minutes,
          and Dodo Payments emails your receipt.
        </li>
        <li>Each renewal continues your plan without a break.</li>
      </ul>
    ),
  },
  {
    id: "problems",
    title: "If your plan doesn't start",
    body: (
      <p>
        If you&apos;ve paid and your workspace still shows the old plan after an hour, email {mail} with the email address
        used at checkout. If we can&apos;t give you the plan you paid for, we refund you as our{" "}
        <Link href="/refunds">Refund and Cancellation Policy</Link> describes.
      </p>
    ),
  },
  {
    id: "your-customers",
    title: "Orders from businesses that use us",
    body: (
      <p>
        Businesses can take orders from their customers through {N}. Those businesses ship their own goods and set their
        own delivery terms; ask the business you ordered from about a delivery.
      </p>
    ),
  },
  {
    id: "contact",
    title: "Contact us",
    body: (
      <>
        <p>
          Email {mail}, or see our <Link href="/contact">contact page</Link>.
        </p>
        <LegalFacts />
      </>
    ),
  },
];

export default function ShippingPage() {
  return (
    <LegalPage
      document="shipping"
      sections={SECTIONS}
      summary={
        <p>
          {N} is delivered online: nothing is shipped and there are no shipping charges. Your plan starts as soon as you
          sign up or checkout succeeds.
        </p>
      }
    />
  );
}
