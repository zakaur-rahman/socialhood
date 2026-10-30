import {
  Ban,
  Bug,
  CircleCheck,
  CircleMinus,
  Info,
  KeyRound,
  ListChecks,
  Mail,
  MessageSquareOff,
  ShieldAlert,
  Timer,
  UserRound,
} from "lucide-react";
import type { ReactNode } from "react";

import { InfoBand, InfoCard, InfoPage } from "@/components/marketing/InfoPage";
import { Callout } from "@/components/site/Callout";
import { SUPPORT_EMAIL } from "@/lib/copy";
import { pageMetadata } from "@/lib/marketing/seo";
import { SITE_NAME } from "@/lib/marketing/site";
import { SECURITY_POLICY_PATH, SECURITY_TXT_PATH } from "@/lib/security/security-txt";

export const metadata = pageMetadata({
  title: "Security",
  description: `How to report a security problem in ${SITE_NAME}, what is in scope, and what happens after you report it.`,
  path: SECURITY_POLICY_PATH,
});

const REPORT_HREF = `mailto:${SUPPORT_EMAIL}?subject=Security%20report`;
const mail = <a href={REPORT_HREF}>{SUPPORT_EMAIL}</a>;

function ScopeList({ icon: Icon, items }: { icon: typeof CircleCheck; items: ReactNode[] }) {
  return (
    <ul className="scope-list">
      {items.map((item, index) => (
        <li key={index}>
          <Icon size={20} strokeWidth={1.75} aria-hidden focusable="false" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

/** /security: the responsible disclosure policy that /.well-known/security.txt points at (C-143; C-159 layout). */
export default function SecurityPage() {
  return (
    <InfoPage
      name="Security"
      path={SECURITY_POLICY_PATH}
      className="security"
      eyebrow="Trust"
      title="Security"
      lede={
        <>
          Found a security problem in {SITE_NAME}? Email {mail}. We read every report and reply to each one.
        </>
      }
      head={
        <a href={REPORT_HREF} className="btn btn-main">
          <Mail size={18} strokeWidth={1.75} aria-hidden focusable="false" />
          {SUPPORT_EMAIL}
        </a>
      }
    >
      <InfoBand
        id="report"
        title="How to report a problem"
        intro={<p>Email {mail} with “Security” in the subject. Tell us:</p>}
      >
        <ul className="fgrid">
          <InfoCard icon={ListChecks}>
            <p>the page, address or feature that is affected;</p>
          </InfoCard>
          <InfoCard icon={Bug}>
            <p>the steps to reproduce it, with any requests or screenshots that help;</p>
          </InfoCard>
          <InfoCard icon={ShieldAlert}>
            <p>what an attacker could do with it;</p>
          </InfoCard>
          <InfoCard icon={UserRound}>
            <p>how to reach you, and the name you&apos;d like us to use.</p>
          </InfoCard>
        </ul>
        <Callout icon={Info}>
          <p>Write in English. Don&apos;t include other people&apos;s personal data in the report.</p>
        </Callout>
      </InfoBand>

      <section aria-label="Scope" className="ib-sec">
        <div className="wrap">
          <div className="scope">
            <section aria-labelledby="scope-title" className="scope-card is-in">
              <h2 id="scope-title" className="h-sec">
                What is in scope
              </h2>
              <ScopeList
                icon={CircleCheck}
                items={[
                  <>The {SITE_NAME} website and the signed-in app on the same domain.</>,
                  <>The {SITE_NAME} API and the website chat widget it serves.</>,
                  <>How we handle your workspace&apos;s data and your connected Instagram and WhatsApp accounts.</>,
                ]}
              />
            </section>
            <section aria-labelledby="out-of-scope-title" className="scope-card is-out">
              <h2 id="out-of-scope-title" className="h-sec">
                What is out of scope
              </h2>
              <ScopeList
                icon={CircleMinus}
                items={[
                  <>
                    Services we use but don&apos;t run, such as Clerk, Meta, Google Cloud, Cloudinary, Sentry and Dodo Payments.
                    Report those to the provider.
                  </>,
                  <>Denial of service, load testing, spam and social engineering of our team or customers.</>,
                  <>Scanner output, missing headers or best practices without a way to exploit them.</>,
                  <>Problems that need a compromised device or browser, or that only affect your own account.</>,
                ]}
              />
            </section>
          </div>
        </div>
      </section>

      <InfoBand id="rules" title="Testing rules">
        <ul className="fgrid">
          <InfoCard icon={KeyRound}>
            <p>Test only with accounts and workspaces you own.</p>
          </InfoCard>
          <InfoCard icon={Ban}>
            <p>
              Don&apos;t read, change or delete anyone else&apos;s data. If you reach some by accident, stop, don&apos;t keep it,
              and tell us.
            </p>
          </InfoCard>
          <InfoCard icon={MessageSquareOff}>
            <p>Don&apos;t send messages to real customers or post on accounts that aren&apos;t yours.</p>
          </InfoCard>
          <InfoCard icon={Timer}>
            <p>Give us time to fix the problem before you share details with anyone.</p>
          </InfoCard>
        </ul>
      </InfoBand>

      <InfoBand
        id="after"
        title="After you report"
        night
        className="info-close"
        intro={
          <>
            <p>
              We reply to confirm we have your report, look into it, and tell you what we decide. If it&apos;s a real problem,
              we fix it and let you know when the fix is live.
            </p>
            <p>We don&apos;t run a paid bug bounty, so we can&apos;t offer money for reports.</p>
            <p className="info-related">
              Machine-readable contact details are in <a href={SECURITY_TXT_PATH}>security.txt</a>.
            </p>
          </>
        }
      />
    </InfoPage>
  );
}
