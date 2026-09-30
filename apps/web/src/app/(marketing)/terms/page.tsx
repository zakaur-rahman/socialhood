import Link from "next/link";

import { LegalFacts, LegalPage, type LegalSection } from "@/components/marketing/legal/LegalPage";
import { LEGAL, governingLawClause, operatorName } from "@/lib/legal";
import { pageMetadata } from "@/lib/marketing/seo";

export const metadata = pageMetadata({
  title: "Terms of Service",
  description:
    "The terms for using Social Hood: plans and the Pro trial, billing through Dodo Payments, cancellation, acceptable use, AI output and liability.",
  path: "/terms",
});

const email = LEGAL.contactEmail;
const mail = <a href={`mailto:${email}`}>{email}</a>;

// Grounded in what is built: plans and entitlements (billing/plans.py), the trial and billing rules
// (FR-BIL-01…07, C-050), the no-follow-gate rule (C-031), Ask Social Hood (read-only in R1).
// LAWYER REVIEW before launch (launch checklist §6.4); the governing-law clause appears only once
// lib/legal.ts sets it.
function sections(): LegalSection[] {
  const law = governingLawClause(LEGAL);
  const list: LegalSection[] = [
    {
      id: "agreement",
      title: "These terms",
      body: (
        <>
          <p>
            These terms are an agreement between you and {operatorName(LEGAL)} (&quot;Social Hood&quot;, &quot;we&quot;,
            &quot;us&quot;) for using the Social Hood website and app. By creating an account or using Social Hood, you
            accept them. If you use Social Hood for a business, you confirm that you can accept these terms for it, and
            &quot;you&quot; includes that business.
          </p>
          <p>
            Our <Link href="/privacy">Privacy Policy</Link> explains how we handle personal data, and our{" "}
            <Link href="/refunds">Refund Policy</Link> explains refunds. Both are part of these terms.
          </p>
        </>
      ),
    },
    {
      id: "service",
      title: "The service",
      body: (
        <>
          <p>
            Social Hood is an inbox and automation tool for Instagram professional accounts and WhatsApp Business numbers.
            It brings messages and comments into one place, suggests or sends replies with AI using your knowledge base,
            runs comment and DM automations, schedules and publishes posts, and shows analytics.
          </p>
          <p>
            We improve Social Hood over time, so features may change. If we remove something important you pay for,
            we&apos;ll tell you in advance.
          </p>
        </>
      ),
    },
    {
      id: "accounts",
      title: "Your account and workspace",
      body: (
        <ul>
          <li>You must be 18 or older and give accurate information when you sign up.</li>
          <li>Keep your sign-in secure. You are responsible for what happens in your account and your workspace.</li>
          <li>
            The workspace owner controls the workspace, including its plan and billing, and is responsible for the members
            they invite.
          </li>
          <li>
            You may only connect Instagram and WhatsApp accounts that you or your business own or are authorised to manage.
          </li>
        </ul>
      ),
    },
    {
      id: "plans",
      title: "Plans, trial and billing",
      body: (
        <>
          <ul>
            <li>
              <strong>Free</strong> costs nothing and needs no card. <strong>Pro</strong> is a monthly subscription. What each
              plan includes is shown on our <Link href="/#pricing">pricing section</Link> and in the app.
            </li>
            <li>
              <strong>Trial.</strong> Pro starts with a 7-day free trial, once per workspace. A card is needed to start it.
              Unless you cancel before the trial ends, Pro continues as a paid subscription and your card is charged.
            </li>
            <li>
              <strong>Payments.</strong> Dodo Payments handles checkout, payments, invoices and your payment method. The price
              is shown in the app and at checkout. You pay in advance for each monthly period, and the subscription renews
              automatically until you cancel.
            </li>
            <li>
              <strong>Cancelling.</strong> The workspace owner can cancel at any time in Settings → Billing. Pro stays active
              until the end of the period you&apos;ve paid for, then the workspace moves to Free. You can resume before
              then.
            </li>
            <li>
              <strong>Failed payments.</strong> If a payment fails, you have a 3-day grace period to fix it before the
              workspace moves to Free.
            </li>
            <li>
              <strong>Moving to Free.</strong> Accounts beyond the Free limit become read-only, Auto mode switches to Suggest,
              and automations beyond the Free limit or using AI replies are paused. Free keeps 90 days of message history,
              so older messages are deleted.
            </li>
            <li>
              <strong>AI credits.</strong> AI features use credits from a monthly allowance that resets at the start of each
              billing period. Unused credits don&apos;t carry over. When they run out, AI features pause until they reset or
              you upgrade.
            </li>
            <li>
              <strong>WhatsApp fees.</strong> Our plans don&apos;t include Meta&apos;s WhatsApp messaging fees. Meta charges
              them directly to your business.
            </li>
            <li>
              <strong>Price changes.</strong> If we change the price of your plan, we&apos;ll tell you before the change
              applies to your next billing period, and you can cancel before it does.
            </li>
          </ul>
          <p>
            Refunds are covered by our <Link href="/refunds">Refund Policy</Link>.
          </p>
        </>
      ),
    },
    {
      id: "acceptable-use",
      title: "Acceptable use",
      body: (
        <>
          <p>When you use Social Hood you must:</p>
          <ul>
            <li>
              follow the law and Meta&apos;s rules for the platforms you connect, including Meta&apos;s Platform Terms, the
              Instagram Terms of Use and Community Guidelines, and the WhatsApp Business Messaging and Commerce policies;
            </li>
            <li>have the right to message the people you message, and respect their choice to stop hearing from you;</li>
            <li>tell people that a message was sent automatically where the law requires it (Social Hood can add a line for this);</li>
            <li>keep your knowledge base, messages and posts accurate and lawful.</li>
          </ul>
          <p>You must not use Social Hood to:</p>
          <ul>
            <li>send spam, unsolicited bulk messages, or messages outside the windows Instagram and WhatsApp allow;</li>
            <li>make following, liking or sharing a condition for getting something you promised (Instagram doesn&apos;t allow it);</li>
            <li>deceive, harass, threaten or discriminate against anyone, or share illegal or harmful content;</li>
            <li>process data you have no right to, or sensitive data you don&apos;t need;</li>
            <li>
              break, overload, probe or get around the security or limits of Social Hood or Meta&apos;s platforms, or copy,
              resell or reverse-engineer the service.
            </li>
          </ul>
        </>
      ),
    },
    {
      id: "your-content",
      title: "Your content and your customers' data",
      body: (
        <>
          <p>
            You keep all rights to your content: your knowledge base, posts, media and messages. You allow us to store,
            process and transmit it only as needed to provide Social Hood to you.
          </p>
          <p>
            You are responsible for your customers&apos; data that you bring into Social Hood, including having a lawful
            basis to process it. We process it on your behalf, as our <Link href="/privacy">Privacy Policy</Link> describes.
          </p>
        </>
      ),
    },
    {
      id: "ai-output",
      title: "AI output",
      body: (
        <>
          <p>
            Social Hood&apos;s AI features, including suggested and automatic replies, analysis, summaries, captions and Ask
            Social Hood, generate content automatically. The AI is instructed to answer only from your knowledge base and
            the conversation, and to hand a conversation to you when it isn&apos;t sure, but it can still be wrong,
            incomplete or out of date.
          </p>
          <ul>
            <li>
              You choose each account&apos;s AI mode. In Auto mode, replies are sent without a person reviewing them first.
            </li>
            <li>
              You are responsible for the messages sent from your accounts, including AI and automated ones, and for keeping
              your knowledge base accurate.
            </li>
            <li>Don&apos;t rely on AI output for legal, medical, financial or other professional advice.</li>
            <li>Ask Social Hood only reads your data and prepares drafts for you to review. It never acts by itself.</li>
          </ul>
        </>
      ),
    },
    {
      id: "platforms",
      title: "Meta's platforms",
      body: (
        <p>
          Social Hood depends on Instagram and WhatsApp, which Meta runs. Meta can change its APIs, rules and limits, restrict
          or suspend accounts, or stop a feature working, and those decisions are outside our control. We&apos;ll adapt
          Social Hood where we can, but we aren&apos;t responsible for Meta&apos;s actions or for its charges.
        </p>
      ),
    },
    {
      id: "availability",
      title: "Availability",
      body: (
        <p>
          We work to keep Social Hood running and your data safe, but we don&apos;t promise that it will always be
          available, uninterrupted or free of errors. We may pause it for maintenance, and we&apos;ll try to do that at
          quiet times.
        </p>
      ),
    },
    {
      id: "ending",
      title: "Suspension and ending",
      body: (
        <>
          <p>
            You can stop using Social Hood at any time and delete your workspace in Settings → Workspace. We may suspend or
            close a workspace that breaks these terms, puts others or the service at risk, or that Meta or the law requires
            us to stop serving. Where we can, we&apos;ll warn you first and give you a chance to fix the problem.
          </p>
          <p>After a workspace is deleted, its data is removed as our Privacy Policy describes.</p>
        </>
      ),
    },
    {
      id: "disclaimers",
      title: "Disclaimers",
      body: (
        <p>
          Apart from what these terms promise, Social Hood is provided &quot;as is&quot; and &quot;as available&quot;. To the
          extent the law allows, we make no other promises, including about fitness for a particular purpose or the
          results you will get.
        </p>
      ),
    },
    {
      id: "liability",
      title: "Limits of liability",
      body: (
        <>
          <p>To the extent the law allows:</p>
          <ul>
            <li>
              we aren&apos;t liable for indirect or consequential losses, such as lost profits, revenue, sales, data or
              goodwill;
            </li>
            <li>
              we aren&apos;t liable for messages sent from your accounts, including AI and automated ones, or for the
              actions of Meta or other third parties;
            </li>
            <li>
              our total liability for all claims about Social Hood is limited to the amount you paid us in the 12 months
              before the claim arose.
            </li>
          </ul>
          <p>Nothing in these terms limits liability that the law doesn&apos;t allow to be limited.</p>
          <p>
            You agree to cover our reasonable losses from claims by others that arise from your content, the messages you
            send, or your breach of these terms or of Meta&apos;s rules.
          </p>
        </>
      ),
    },
    {
      id: "changes",
      title: "Changes to these terms",
      body: (
        <p>
          When we change these terms we update the date at the top. If a change is significant, we&apos;ll tell you by email
          or in the app before it takes effect. If you keep using Social Hood after that, the new terms apply.
        </p>
      ),
    },
  ];
  if (law) {
    list.push({ id: "law", title: "Governing law", body: <p>{law}</p> });
  }
  list.push({
    id: "contact",
    title: "Contact us",
    body: (
      <>
        <p>Questions about these terms? Email {mail}.</p>
        <LegalFacts />
      </>
    ),
  });
  return list;
}

export default function TermsPage() {
  return (
    <LegalPage
      document="terms"
      sections={sections()}
      summary={
        <>
          <p>
            The short version: Free is free; Pro is monthly, starts with a 7-day trial (card required), and you can cancel
            anytime, keeping Pro until the end of the period you&apos;ve paid for.
          </p>
          <p>
            Follow Meta&apos;s rules and the law, don&apos;t spam, and check what the AI sends for you: you are responsible
            for messages sent from your accounts.
          </p>
        </>
      }
    />
  );
}
