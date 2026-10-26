import type { ReactNode } from "react";

import { Container, SECTION_EYEBROW } from "@/components/marketing/primitives";
import { Card } from "@/components/ui/card";
import { SUPPORT_EMAIL } from "@/lib/copy";
import { pageMetadata } from "@/lib/marketing/seo";
import { SITE_NAME } from "@/lib/marketing/site";
import { SECURITY_POLICY_PATH, SECURITY_TXT_PATH } from "@/lib/security/security-txt";
import { cn } from "@/lib/utils";
import { MARKETING_HEADING, READING } from "@/styles/tokens";

export const metadata = pageMetadata({
  title: "Security",
  description: `How to report a security problem in ${SITE_NAME}, what is in scope, and what happens after you report it.`,
  path: SECURITY_POLICY_PATH,
});

const mail = <a href={`mailto:${SUPPORT_EMAIL}?subject=Security%20report`}>{SUPPORT_EMAIL}</a>;

// The same prose look as the legal pages (components/marketing/legal/LegalPage).
const PROSE = [
  cn(READING, "text-fg-secondary"),
  "[&_h2]:text-xl [&_h2]:font-semibold [&_h2]:tracking-tight [&_h2]:text-fg",
  "[&_p]:mt-3 [&_ul]:mt-3 [&_ul]:list-disc [&_ul]:space-y-1.5 [&_ul]:pl-5 [&_li]:pl-1",
  "[&_strong]:font-semibold [&_strong]:text-fg",
  "[&_a]:font-medium [&_a]:text-brand-fg [&_a]:underline [&_a]:underline-offset-4",
].join(" ");

const SECTIONS: { id: string; title: string; body: ReactNode }[] = [
  {
    id: "report",
    title: "How to report a problem",
    body: (
      <>
        <p>Email {mail} with “Security” in the subject. Tell us:</p>
        <ul>
          <li>the page, address or feature that is affected;</li>
          <li>the steps to reproduce it, with any requests or screenshots that help;</li>
          <li>what an attacker could do with it;</li>
          <li>how to reach you, and the name you&apos;d like us to use.</li>
        </ul>
        <p>Write in English. Don&apos;t include other people&apos;s personal data in the report.</p>
      </>
    ),
  },
  {
    id: "scope",
    title: "What is in scope",
    body: (
      <ul>
        <li>The {SITE_NAME} website and the signed-in app on the same domain.</li>
        <li>The {SITE_NAME} API and the website chat widget it serves.</li>
        <li>How we handle your workspace&apos;s data and your connected Instagram and WhatsApp accounts.</li>
      </ul>
    ),
  },
  {
    id: "out-of-scope",
    title: "What is out of scope",
    body: (
      <ul>
        <li>
          Services we use but don&apos;t run, such as Clerk, Meta, Vercel, Render, Cloudinary, Sentry and Dodo Payments.
          Report those to the provider.
        </li>
        <li>Denial of service, load testing, spam and social engineering of our team or customers.</li>
        <li>Scanner output, missing headers or best practices without a way to exploit them.</li>
        <li>Problems that need a compromised device or browser, or that only affect your own account.</li>
      </ul>
    ),
  },
  {
    id: "rules",
    title: "Testing rules",
    body: (
      <ul>
        <li>Test only with accounts and workspaces you own.</li>
        <li>
          Don&apos;t read, change or delete anyone else&apos;s data. If you reach some by accident, stop, don&apos;t keep
          it, and tell us.
        </li>
        <li>Don&apos;t send messages to real customers or post on accounts that aren&apos;t yours.</li>
        <li>Give us time to fix the problem before you share details with anyone.</li>
      </ul>
    ),
  },
  {
    id: "after",
    title: "After you report",
    body: (
      <>
        <p>
          We reply to confirm we have your report, look into it, and tell you what we decide. If it&apos;s a real
          problem, we fix it and let you know when the fix is live.
        </p>
        <p>We don&apos;t run a paid bug bounty, so we can&apos;t offer money for reports.</p>
      </>
    ),
  },
];

/** /security: the responsible disclosure policy that /.well-known/security.txt points at (C-143). */
export default function SecurityPage() {
  return (
    <main id="main" tabIndex={-1} className="flex-1 outline-none">
      <Container className="py-12 sm:py-16">
        <header className="max-w-3xl">
          <p className={SECTION_EYEBROW}>Trust</p>
          <h1 className={cn(MARKETING_HEADING, "mt-3")}>Security</h1>
          <Card
            padding="roomy"
            className={cn(READING, "mt-6 text-fg-secondary [&_a]:text-brand-fg [&_a]:underline [&_a]:underline-offset-4")}
          >
            <p>
              Found a security problem in {SITE_NAME}? Email {mail}. We read every report and reply to each one.
            </p>
          </Card>
        </header>

        <div className={cn("mt-10 max-w-3xl space-y-12", PROSE)}>
          {SECTIONS.map((section) => (
            <section key={section.id} aria-labelledby={section.id}>
              <h2 id={section.id}>{section.title}</h2>
              {section.body}
            </section>
          ))}
          <p className="text-sm">
            Machine-readable contact details are in{" "}
            <a href={SECURITY_TXT_PATH}>security.txt</a>
            .
          </p>
        </div>
      </Container>
    </main>
  );
}
