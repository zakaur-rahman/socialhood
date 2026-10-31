import Link from "next/link";

import { LegalPage, type LegalSection } from "@/components/marketing/legal/LegalPage";
import { SubprocessorTable } from "@/components/marketing/legal/SubprocessorTable";
import { LEGAL, operatorName } from "@/lib/legal";
import { SITE_NAME } from "@/lib/marketing/site";
import { pageMetadata } from "@/lib/marketing/seo";

export const metadata = pageMetadata({
  title: "Subprocessors",
  description: `The service providers that process personal data for ${SITE_NAME}, what each one does, the data involved and where it is processed.`,
  path: "/subprocessors",
});

const N = SITE_NAME;
const email = LEGAL.contactEmail;
const mail = <a href={`mailto:${email}`}>{email}</a>;

// C-156: the table is lib/subprocessors.ts, shared with the privacy policy and the DPA (Annex 3).
// Not reviewed by a lawyer.
function sections(): LegalSection[] {
  const operator = operatorName(LEGAL);
  return [
    {
      id: "list",
      title: "Our subprocessors",
      body: (
        <>
          <p>
            These providers process personal data for {operator} to run {N}. Each one works under a contract that limits
            it to that purpose and requires it to protect the data.
          </p>
          <SubprocessorTable />
        </>
      ),
    },
    {
      id: "not-subprocessors",
      title: "Others who receive data",
      body: (
        <ul>
          <li>
            <strong>Meta</strong> (Instagram, Facebook and WhatsApp). Your replies, automated messages and posts go to
            Meta&apos;s platforms through its official APIs. Meta runs those platforms under its own terms and is not our
            subprocessor.
          </li>
          <li>
            <strong>Dodo Payments</strong>, once paid plans open. As merchant of record it runs checkout, takes payments,
            charges tax and issues invoices, and it decides how it handles payment data under its own{" "}
            <a href="https://dodopayments.com/privacy-policy" rel="noopener noreferrer">
              privacy policy
            </a>
            . Paid plans aren&apos;t on sale yet, so no payment data is sent today.
          </li>
          <li>
            <strong>Services a business connects</strong>, such as Razorpay, Shopify, Google Sheets, Zapier and its own
            webhooks. A business sends them data on its own instructions, under its own agreement with them. Our{" "}
            <Link href="/privacy#sharing">Privacy Policy</Link> lists what each one gets.
          </li>
          <li>
            <strong>Browser push services</strong> (for example Google, Apple, Mozilla and Microsoft) deliver the phone and
            desktop notifications you turn on. Each notification is encrypted so only your device can read it.
          </li>
          <li>
            <strong>Grafana Cloud</strong> receives service health metrics. They contain no personal data.
          </li>
        </ul>
      ),
    },
    {
      id: "changes",
      title: "Changes to this list",
      body: (
        <>
          <p>
            When we add or replace a subprocessor, we update this page and its date, and we email the owner of each
            workspace at least 30 days before a new subprocessor starts processing their data. Owners can object as our{" "}
            <Link href="/dpa#subprocessors">Data Processing Agreement</Link> describes.
          </p>
          <p>To be told about changes, email {mail}.</p>
        </>
      ),
    },
  ];
}

export default function SubprocessorsPage() {
  return (
    <LegalPage
      document="subprocessors"
      sections={sections()}
      summary={
        <p>
          The companies that process personal data for {N}, what they do, the data involved and where. Our{" "}
          <Link href="/privacy">Privacy Policy</Link> and <Link href="/dpa">Data Processing Agreement</Link> refer to this
          list. To be told about changes, email {mail}.
        </p>
      }
    />
  );
}
