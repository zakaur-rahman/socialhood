import Link from "next/link";

import { LegalFacts, LegalPage, type LegalSection } from "@/components/marketing/legal/LegalPage";
import { LEGAL, governingLawClause, isSet, operatorName } from "@/lib/legal";
import { SITE_NAME } from "@/lib/marketing/site";
import { pageMetadata } from "@/lib/marketing/seo";

export const metadata = pageMetadata({
  title: "Terms of Service",
  description: `The terms for using ${SITE_NAME}: plans and the Pro trial, billing, cancellation, delivery, acceptable use, AI features, data processing and liability.`,
  path: "/terms",
});

const N = SITE_NAME;
const email = LEGAL.contactEmail;
const mail = <a href={`mailto:${email}`}>{email}</a>;

// Grounded in what is built: plans and entitlements (billing/plans.py), the trial and billing rules
// (FR-BIL-01…07, C-050), the no-follow-gate rule (C-031), Ask Amplychat (read-only in R1), the
// integrations' statuses (C-138). C-144 added the operator, Dodo as merchant of record, delivery,
// connected services and grievances. C-156 added the AI features section (modelled on Wati's §11),
// the DPA incorporation, the subprocessors link, the WhatsApp no-markup line and, with
// LEGAL.governingLaw set, the governing-law section (no courts named: the owner left jurisdiction
// unset). NOT reviewed by a lawyer (no lawyer budget, C-156).
function sections(): LegalSection[] {
  const law = governingLawClause(LEGAL);
  const operator = operatorName(LEGAL);
  const proprietor = isSet(LEGAL.proprietor) ? LEGAL.proprietor.trim() : null;
  const list: LegalSection[] = [
    {
      id: "agreement",
      title: "These terms",
      body: (
        <>
          <p>
            These terms are an agreement between you and {operator}
            {proprietor ? <>, a sole proprietorship of {proprietor} registered in India</> : null} (&quot;{N}&quot;,
            &quot;we&quot;, &quot;us&quot;), for using the {N} website and app. By creating an account or using {N}, you
            accept them. If you use {N} for a business, you confirm that you can accept these terms for it, and
            &quot;you&quot; includes that business.
          </p>
          <p>
            Our <Link href="/privacy">Privacy Policy</Link> explains how we handle personal data, our{" "}
            <Link href="/refunds">Refund and Cancellation Policy</Link> explains refunds and cancelling, and our{" "}
            <Link href="/shipping">Shipping and Delivery Policy</Link> explains how {N} is delivered, and our{" "}
            <Link href="/dpa">Data Processing Agreement</Link> covers the personal data we process for you. All four are
            part of these terms.
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
            {N} is an inbox and automation tool for Instagram professional accounts, WhatsApp Business numbers, Facebook
            Pages (with Meta&apos;s approval) and website chat. It brings messages and comments into one place, suggests or
            sends replies with AI using your knowledge base, runs comment and DM automations, schedules and publishes posts,
            takes orders with payment links, and shows analytics.
          </p>
          <p>
            We improve {N} over time, so features may change. If we remove something important you pay for, we&apos;ll
            tell you in advance.
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
            You may only connect Instagram, Facebook, WhatsApp and other accounts that you or your business own or are
            authorised to manage.
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
              <strong>Free</strong> costs nothing and needs no card. <strong>Pro</strong> is a monthly subscription.{" "}
              <strong>Max</strong> is coming soon. What each plan includes and costs is shown on our{" "}
              <Link href="/pricing">pricing page</Link> and in the app. Pro isn&apos;t on sale yet; the trial and billing
              terms below apply once it is.
            </li>
            <li>
              <strong>Trial.</strong> Pro starts with a 7-day free trial, once per workspace. A card is needed to start it.
              Unless you cancel before the trial ends, Pro continues as a paid subscription and your card is charged.
            </li>
            <li>
              <strong>Payments.</strong> Dodo Payments is the merchant of record for our subscriptions: it runs checkout,
              takes the payment, charges any tax that applies and issues your invoice, and its own terms apply to the
              payment. The price is shown in the app and at checkout. You pay in advance for each monthly period, and the
              subscription renews automatically until you cancel.
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
              <strong>WhatsApp fees.</strong> Our plans don&apos;t include Meta&apos;s WhatsApp messaging fees. You pay
              them to Meta directly, through your own WhatsApp Business account, and we add no markup.
            </li>
            <li>
              <strong>Price changes.</strong> If we change the price of your plan, we&apos;ll tell you before the change
              applies to your next billing period, and you can cancel before it does.
            </li>
          </ul>
          <p>
            Refunds are covered by our <Link href="/refunds">Refund and Cancellation Policy</Link>.
          </p>
        </>
      ),
    },
    {
      id: "delivery",
      title: "Delivery",
      body: (
        <p>
          {N} is software used online. Nothing is shipped: a plan&apos;s features are available in your workspace as soon
          as the trial starts or the payment succeeds, and Dodo Payments emails your receipt. Our{" "}
          <Link href="/shipping">Shipping and Delivery Policy</Link> has the details.
        </p>
      ),
    },
    {
      id: "acceptable-use",
      title: "Acceptable use",
      body: (
        <>
          <p>When you use {N} you must:</p>
          <ul>
            <li>
              follow the law and Meta&apos;s rules for the platforms you connect, including Meta&apos;s Platform Terms, the
              Instagram Terms of Use and Community Guidelines, Facebook&apos;s Messenger policies, and the WhatsApp Business
              Messaging and Commerce policies;
            </li>
            <li>
              have the right to message the people you message, get their consent where the law or Meta requires it, and
              respect their choice to stop hearing from you;
            </li>
            <li>tell people that a message was sent automatically where the law requires it ({N} can add a line for this);</li>
            <li>keep your knowledge base, catalogue, messages and posts accurate and lawful.</li>
          </ul>
          <p>You must not use {N} to:</p>
          <ul>
            <li>send spam, unsolicited bulk messages, or messages outside the windows Instagram, Messenger and WhatsApp allow;</li>
            <li>make following, liking or sharing a condition for getting something you promised (Instagram doesn&apos;t allow it);</li>
            <li>deceive, harass, threaten or discriminate against anyone, or share illegal or harmful content;</li>
            <li>sell goods or services that the law, Meta&apos;s commerce policies or your payment provider don&apos;t allow;</li>
            <li>process data you have no right to, or sensitive data you don&apos;t need;</li>
            <li>
              break, overload, probe or get around the security or limits of {N} or Meta&apos;s platforms, or copy, resell
              or reverse-engineer the service.
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
            You keep all rights to your content: your knowledge base, catalogue, posts, media and messages. You allow us to
            store, process and transmit it only as needed to provide {N} to you.
          </p>
          <p>
            You are the controller (under India&apos;s DPDP Act, the Data Fiduciary) for your customers&apos; and
            followers&apos; data that you bring into {N}, and you are responsible for having a lawful basis to process it
            and for answering their requests about it. We process it on your behalf and on your instructions, as our
            processor terms describe, and we help you answer those requests.
          </p>
          <p>
            Our <Link href="/dpa">Data Processing Agreement</Link>, including the EU Standard Contractual Clauses and the UK
            Addendum it incorporates, is part of these terms and applies as soon as you accept them. The service providers
            we use are listed on our <Link href="/subprocessors">subprocessors page</Link>.
          </p>
        </>
      ),
    },
    {
      id: "ai-features",
      title: "AI features",
      body: (
        <>
          <p>
            {N}&apos;s AI features, including suggested and automatic replies, analysis, lead scores, spam flags, summaries,
            captions and Ask {N}, generate content automatically. The AI is instructed to answer only from your knowledge
            base and the conversation, and to hand a conversation to you when it isn&apos;t sure, but it can still be wrong,
            incomplete, out of date or inappropriate.
          </p>
          <ul>
            <li>
              <strong>No promise of accuracy.</strong> AI output is provided &quot;as is&quot;. We don&apos;t warrant that it
              is accurate, complete or fit for any purpose.
            </li>
            <li>
              <strong>You review it.</strong> Check AI output before you rely on it or send it. In Suggest mode a person
              sends each reply; in Auto mode replies are sent without a person reviewing them first, and only if you turn it
              on. You can switch Auto off at any time.
            </li>
            <li>
              <strong>You are responsible for what is sent.</strong> You are responsible for the messages sent from your
              accounts, including the replies Auto mode and your automations send, and for keeping your knowledge base
              accurate.
            </li>
            <li>
              <strong>No decisions about people.</strong> Don&apos;t use {N}&apos;s AI to make decisions that have legal or
              similarly significant effects on people, such as about credit, employment, housing, insurance, education or
              access to essential services, and don&apos;t rely on it for legal, medical, financial or other professional
              advice.
            </li>
            <li>Ask {N} only reads your data and prepares drafts for you to review. It never acts by itself.</li>
            <li>
              The AI runs on Google&apos;s Gemini API. Our <Link href="/privacy#ai">Privacy Policy</Link> explains what we
              send to Google and how Google may use it.
            </li>
          </ul>
        </>
      ),
    },
    {
      id: "platforms",
      title: "Meta's platforms and other services",
      body: (
        <>
          <p>
            {N} depends on Instagram, Facebook and WhatsApp, which Meta runs. Meta can change its APIs, rules and limits,
            restrict or suspend accounts, or stop a feature working, and those decisions are outside our control.
            We&apos;ll adapt {N} where we can, but we aren&apos;t responsible for Meta&apos;s actions or for its charges.
          </p>
          <p>
            You can also connect your own accounts with other services, such as Razorpay, Shopify, Google Sheets and Zapier.
            Their terms apply to your use of them. Payments your customers make through your Razorpay account are between
            you and them: we never hold that money, and you are responsible for your orders, deliveries and refunds to your
            customers.
          </p>
        </>
      ),
    },
    {
      id: "availability",
      title: "Availability",
      body: (
        <p>
          We work to keep {N} running and your data safe, but we don&apos;t promise that it will always be available,
          uninterrupted or free of errors. We may pause it for maintenance, and we&apos;ll try to do that at quiet times.
        </p>
      ),
    },
    {
      id: "ending",
      title: "Suspension and ending",
      body: (
        <>
          <p>
            You can stop using {N} at any time and delete your workspace in Settings → Workspace. We may suspend or close a
            workspace that breaks these terms, puts others or the service at risk, or that Meta or the law requires us to
            stop serving. Where we can, we&apos;ll warn you first and give you a chance to fix the problem.
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
          Apart from what these terms promise, {N} is provided &quot;as is&quot; and &quot;as available&quot;. To the
          extent the law allows, we make no other promises, including about fitness for a particular purpose or the results
          you will get.
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
              we aren&apos;t liable for messages sent from your accounts, including AI and automated ones, or for the actions
              of Meta or other third parties;
            </li>
            <li>
              our total liability for all claims about {N} is limited to the amount you paid us in the 12 months before the
              claim arose.
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
          or in the app before it takes effect. If you keep using {N} after that, the new terms apply.
        </p>
      ),
    },
  ];
  if (law) {
    list.push({ id: "law", title: "Governing law", body: <p>{law}</p> });
  }
  list.push({
    id: "contact",
    title: "Contact and complaints",
    body: (
      <>
        <p>
          Questions or complaints about {N} or these terms? Email {mail}; our <Link href="/contact">contact page</Link>{" "}
          has more ways to reach us. Privacy grievances are answered as our{" "}
          <Link href="/privacy#your-rights">Privacy Policy</Link> describes.
        </p>
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
            anytime, keeping Pro until the end of the period you&apos;ve paid for. {N} is delivered online; nothing is
            shipped.
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
