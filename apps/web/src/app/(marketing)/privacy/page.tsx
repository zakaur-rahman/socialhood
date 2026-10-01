import Link from "next/link";

import { LegalFacts, LegalPage, type LegalSection } from "@/components/marketing/legal/LegalPage";
import { LEGAL } from "@/lib/legal";
import { pageMetadata } from "@/lib/marketing/seo";

export const metadata = pageMetadata({
  title: "Privacy Policy",
  description:
    "How Social Hood collects, uses, shares, keeps and deletes personal data, including the Instagram and WhatsApp data it receives from Meta.",
  path: "/privacy",
});

const email = LEGAL.contactEmail;
const mail = <a href={`mailto:${email}`}>{email}</a>;

// Grounded in the built system: BUILD_SPEC §5.9, C-056 and C-067 (retention and deletion, an
// account's data, backup exports: docs/ops/backup.md), C-049/C-053
// (email and push), C-057 (Sentry scrubbing, Render and Vercel), FR-PRV-01/02 and SEC-11/12.
// LAWYER REVIEW before launch (launch checklist §6.4), including the DPDP Act obligations.
const SECTIONS: LegalSection[] = [
  {
    id: "who-we-are",
    title: "Who we are and what this covers",
    body: (
      <>
        <p>
          This policy explains how Social Hood (&quot;we&quot;, &quot;us&quot;) handles personal data when you visit our
          website, when you use the Social Hood app, and when you message or comment on a business that uses Social Hood.
        </p>
        <LegalFacts />
        <h3>Our role</h3>
        <ul>
          <li>
            <strong>Your account data</strong> (for example your name and email): we decide how it is used and are
            responsible for it. Under India&apos;s Digital Personal Data Protection Act, 2023 (DPDP Act), we are its Data
            Fiduciary.
          </li>
          <li>
            <strong>Your customers&apos; data</strong> (the messages, comments and profiles that arrive from Instagram and
            WhatsApp): the business that connected the account decides why it is processed. We process it on that
            business&apos;s behalf and on its instructions, as its Data Processor.
          </li>
        </ul>
        <p>
          If you messaged or commented on a business that uses Social Hood, that business is your first point of contact
          for your data. You can also write to us and we&apos;ll help the business respond.
        </p>
      </>
    ),
  },
  {
    id: "what-we-collect",
    title: "What we collect",
    body: (
      <>
        <h3>Your account and workspace</h3>
        <p>
          Your name, email address and profile photo, through our sign-in provider Clerk (including Google sign-in if you
          use it). Your workspace&apos;s name, time zone, members and their roles, your settings and your notification
          choices.
        </p>
        <h3>The accounts you connect</h3>
        <p>
          When you connect an Instagram professional account or a WhatsApp Business number, Meta gives us the
          account&apos;s ID, username or phone number, name and profile picture, the permissions you granted, and access
          tokens that let Social Hood act for the account. We never ask for or receive your Instagram or Facebook
          password, and we store access tokens encrypted.
        </p>
        <h3>Messages, comments and the people who send them</h3>
        <ul>
          <li>
            Instagram direct messages and WhatsApp messages sent to and from your connected accounts: text, photos, videos,
            voice notes and other attachments, and whether each was sent, delivered and read.
          </li>
          <li>Comments and replies on your Instagram posts and Reels.</li>
          <li>
            What Meta shares about the people who message or comment: their name, username, profile picture, WhatsApp
            phone number, and whether they follow your Instagram account (used only for the optional follow nudge).
          </li>
        </ul>
        <h3>Content you add, and insights</h3>
        <p>
          Your knowledge base (text, the content of web pages you link, and files you upload), automations, scheduled posts
          and messages, captions, and the photos and videos you upload. If you grant Instagram&apos;s insights permission,
          your posts&apos; and account&apos;s insights, such as reach, views, likes, comments, saves and shares.
        </p>
        <h3>What the AI produces</h3>
        <p>
          The analysis of messages and comments (intent, sentiment, lead score, language, topics and spam), conversation
          and comment summaries, suggested replies, knowledge gaps, and your questions to Ask Social Hood with its answers.
        </p>
        <h3>Billing</h3>
        <p>
          Your plan, subscription status and payment status. Card details go to Dodo Payments, which handles checkout; we
          never see or store full card numbers.
        </p>
        <h3>Technical data</h3>
        <p>
          IP addresses and request details, used to keep the service secure and limit abuse; error reports; records of
          AI credit use; and, if you turn on phone notifications, your browser&apos;s push subscription.
        </p>
      </>
    ),
  },
  {
    id: "how-we-use-it",
    title: "How we use it",
    body: (
      <>
        <ul>
          <li>
            To run Social Hood: show your conversations and comments, send your replies and automated messages, publish
            your posts, run your automations, and send notifications and the weekly digest.
          </li>
          <li>To provide the AI features described below.</li>
          <li>To manage your plan and billing, and to email you about your account.</li>
          <li>To help when you contact support.</li>
          <li>To keep the service secure, prevent abuse and fix errors.</li>
          <li>To meet our legal obligations.</li>
        </ul>
        <p>
          <strong>We don&apos;t sell personal data, we don&apos;t use it for advertising, and we don&apos;t use it to train AI
          models.</strong>{" "}
          People at Social Hood look at a workspace&apos;s data only when you ask us for help, to investigate a problem or
          abuse, or when the law requires it.
        </p>
      </>
    ),
  },
  {
    id: "ai",
    title: "AI features and Google Gemini",
    body: (
      <>
        <p>
          Social Hood&apos;s AI features use Google&apos;s Gemini API: analysing messages and comments, suggesting and
          sending replies, summaries, captions and hashtags, searching your knowledge base, and answering Ask Social Hood
          questions. For each task we send Google the text it needs, such as a message with the recent conversation and
          the relevant parts of your knowledge base, and Google returns the result.
        </p>
        <ul>
          <li>
            Each connected account has an AI mode: <strong>Off</strong>, <strong>Suggest</strong> (the AI drafts, a person
            sends) or <strong>Auto</strong> (the AI replies by itself when it&apos;s confident, and hands anything else to a
            person).
          </li>
          <li>
            With AI analysis turned off for an account, its messages and comments aren&apos;t sent to Google for analysis
            or summaries. Features you use on purpose, like a suggested reply or Ask Social Hood, still send the text they
            need.
          </li>
          <li>
            A business can add a short line, such as &quot;Sent automatically&quot;, to the messages its automations and
            Auto mode send (Settings → Workspace).
          </li>
          <li>Ask Social Hood reads your workspace&apos;s data to answer. It never sends, changes or deletes anything.</li>
        </ul>
        <p>
          AI output can be wrong. Our <Link href="/terms">Terms of Service</Link> explain who is responsible for what the
          AI sends.
        </p>
      </>
    ),
  },
  {
    id: "sharing",
    title: "Who we share it with",
    body: (
      <>
        <p>
          <strong>Meta.</strong> Your replies, automated messages and posts go to Instagram and WhatsApp through Meta&apos;s
          official APIs. Meta&apos;s own privacy policy covers what happens on its platforms.
        </p>
        <p>
          <strong>Service providers</strong> that process data for us, only to run Social Hood:
        </p>
        <div className="overflow-x-auto">
          <table>
            <thead>
              <tr>
                <th scope="col">Provider</th>
                <th scope="col">What they do for us</th>
                <th scope="col">Data involved</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Google (Gemini API)</td>
                <td>AI features</td>
                <td>Text of messages, comments, knowledge and questions sent for an AI task</td>
              </tr>
              <tr>
                <td>Cloudinary</td>
                <td>Stores and delivers media and files</td>
                <td>Photos, videos and files you upload or receive in messages</td>
              </tr>
              <tr>
                <td>Clerk</td>
                <td>Sign-up, sign-in and sessions, with bot protection (Cloudflare Turnstile)</td>
                <td>Name, email address, profile photo, sign-in activity</td>
              </tr>
              <tr>
                <td>Dodo Payments</td>
                <td>Checkout, payments, invoices and subscriptions</td>
                <td>Owner&apos;s email address, workspace ID, payment details</td>
              </tr>
              <tr>
                <td>Resend</td>
                <td>Sends our emails</td>
                <td>Email addresses and the content of notification and digest emails</td>
              </tr>
              <tr>
                <td>Sentry</td>
                <td>Error tracking</td>
                <td>
                  Technical error reports. We strip message text, email addresses, tokens, cookies and request bodies before
                  they are sent.
                </td>
              </tr>
              <tr>
                <td>Render</td>
                <td>Hosts our API, database and background jobs</td>
                <td>All data in the service</td>
              </tr>
              <tr>
                <td>Vercel</td>
                <td>Hosts this website and the web app</td>
                <td>Requests to the website and app</td>
              </tr>
              <tr>
                <td>Browser push services (for example Google, Apple, Mozilla, Microsoft)</td>
                <td>Deliver phone and desktop notifications you turn on</td>
                <td>Notifications, encrypted so that only your device can read them</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p>We also send service health metrics to Grafana Cloud. They contain no personal data.</p>
        <p>
          <strong>When the law requires it.</strong> We may disclose data when the law requires it, or to protect the
          rights, safety or property of our users, the public or Social Hood.
        </p>
        <p>
          <strong>If the business changes hands.</strong> If Social Hood is sold or merged, personal data may pass to the
          new owner, who must keep protecting it as this policy describes. We&apos;ll tell you before that happens.
        </p>
      </>
    ),
  },
  {
    id: "where",
    title: "Where your data is stored",
    body: (
      <p>
        Our API, database and background jobs run on Render in Singapore, and the website and web app run on Vercel. Some
        of the providers above process data in other countries, including the United States.
      </p>
    ),
  },
  {
    id: "retention",
    title: "How long we keep it",
    body: (
      <>
        <div className="overflow-x-auto">
          <table>
            <thead>
              <tr>
                <th scope="col">Data</th>
                <th scope="col">How long</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>A workspace&apos;s data: conversations, comments, contacts, knowledge, automations, posts, media and settings</td>
                <td>While the workspace exists. Removed within 24 hours of deleting the workspace.</td>
              </tr>
              <tr>
                <td>
                  A connected account&apos;s data: its conversations, messages, contacts, comments, posts, automations and
                  message files
                </td>
                <td>
                  Until you delete that account&apos;s data (or Meta asks us to), then permanently removed within 24
                  hours, usually within minutes.
                </td>
              </tr>
              <tr>
                <td>Database backups</td>
                <td>Recovery history 7 days; backup exports 30 days, then deleted.</td>
              </tr>
              <tr>
                <td>Messages on the Free plan (including after a paid plan ends)</td>
                <td>
                  90 days, then deleted with their analysis. Conversations left with no messages are deleted too.
                </td>
              </tr>
              <tr>
                <td>Messages on Pro</td>
                <td>While the workspace exists</td>
              </tr>
              <tr>
                <td>The raw events Meta sends us</td>
                <td>30 days</td>
              </tr>
              <tr>
                <td>Notifications</td>
                <td>90 days</td>
              </tr>
              <tr>
                <td>Ask Social Hood conversations</td>
                <td>180 days after they finish</td>
              </tr>
              <tr>
                <td>Records of AI credit use</td>
                <td>13 months</td>
              </tr>
              <tr>
                <td>Records of background jobs</td>
                <td>30 days</td>
              </tr>
              <tr>
                <td>Records of data deletion requests (a confirmation code, the Instagram account ID and the status)</td>
                <td>Kept, so the status page keeps working</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p>
          Deleted data can remain in our database backups until those backups expire: the database&apos;s recovery history
          is kept for 7 days, and backup exports for 30 days, after which they are deleted. Dodo Payments keeps payment
          records for as long as the law requires.
        </p>
      </>
    ),
  },
  {
    id: "deleting",
    title: "Deleting your data",
    body: (
      <>
        <ul>
          <li>
            <strong>Delete your workspace</strong> (Settings → Workspace; owners only). Everything stops at once: access
            tokens are destroyed, accounts are disconnected, automations are paused, and scheduled messages and posts are
            cancelled. An active subscription is cancelled, and the workspace&apos;s data, including uploaded media, is
            permanently removed within 24 hours. If your Social Hood user account is deleted, the workspaces only you own
            are deleted the same way.
          </li>
          <li>
            <strong>Disconnect an account</strong> (Settings → Connections). Its access token is deleted at once and no new
            messages or comments arrive for it. What was already stored stays in the workspace until you delete it.
          </li>
          <li>
            <strong>Delete an account&apos;s data</strong> (Settings → Connections, owners and admins: Disconnect and delete
            data, or Remove for an account already disconnected). The account is disconnected at once, then everything
            stored for it is permanently deleted within 24 hours: its conversations and messages with their AI analysis and suggested
            replies, its contacts, its comments, its posts and their statistics, the automations and scheduled messages
            and posts for it, the photos and files received or sent in its messages, and the account itself. The
            workspace&apos;s knowledge base, settings, members and billing, and its other accounts, are kept.
          </li>
          <li>
            <strong>Remove Social Hood from Instagram.</strong> Removing Social Hood in Instagram&apos;s settings disconnects
            the account. If you also ask for your data to be deleted, Meta sends us your request: we disconnect every
            account connected with your Instagram login, in every workspace, and delete each one&apos;s data as described
            above, along with the raw events Meta sent us for it. You get a confirmation code you can check on our{" "}
            <Link href="/data-deletion">data deletion page</Link>; it shows the request as completed once every
            account&apos;s data is gone.
          </li>
          <li>
            <strong>Email us</strong> at {mail}. Anyone can ask, including customers of a business that uses Social Hood. We
            may need to confirm who you are, and for customers&apos; data we work with the business it belongs to.
          </li>
        </ul>
      </>
    ),
  },
  {
    id: "your-rights",
    title: "Your rights",
    body: (
      <>
        <p>Under the DPDP Act, and similar laws elsewhere, you can ask us to:</p>
        <ul>
          <li>give you a summary of the personal data we hold about you and how we process it;</li>
          <li>correct, complete or update it;</li>
          <li>erase it;</li>
          <li>stop processing that relies on your consent, by withdrawing it;</li>
          <li>let someone you nominate exercise these rights if you die or can&apos;t act yourself;</li>
          <li>address a grievance about how we handle your data.</li>
        </ul>
        <p>
          Depending on where you live, you may have other rights too, such as objecting to processing or getting a copy
          of your data. Email {mail} to use any of them. If your data reached us through a business&apos;s Instagram or
          WhatsApp account, we pass your request to that business and help it respond.
        </p>
        <p>
          If you aren&apos;t satisfied with our answer to a grievance, you can complain to the Data Protection Board of
          India, or to the data protection authority where you live.
        </p>
      </>
    ),
  },
  {
    id: "cookies",
    title: "Cookies and local storage",
    body: (
      <>
        <ul>
          <li>
            <strong>Sign-in cookies.</strong> Clerk&apos;s cookies keep you signed in and protect sign-in. They are
            necessary for the app to work. Sign-up and sign-in may show a Cloudflare Turnstile check, through Clerk, to stop
            bots.
          </li>
          <li>
            <strong>Local storage.</strong> The app remembers a few view preferences in your browser, such as your inbox and
            calendar views.
          </li>
          <li>
            <strong>Service worker.</strong> If you install Social Hood or turn on push notifications, your browser keeps a
            small script from us that receives the notifications.
          </li>
        </ul>
        <p>
          We don&apos;t use analytics, advertising or tracking cookies, and we don&apos;t load third-party analytics or ad
          scripts. Error reports go to Sentry without cookies.
        </p>
      </>
    ),
  },
  {
    id: "security",
    title: "Security",
    body: (
      <>
        <p>
          Connections to Social Hood are encrypted with HTTPS. Instagram and WhatsApp connect through Meta&apos;s official
          APIs, access tokens are stored encrypted, and every workspace&apos;s data is kept separate from every other
          workspace. Only the people who run Social Hood can reach our production systems.
        </p>
        <p>
          No system is perfectly secure. If a breach affects your personal data, we&apos;ll tell you and the authorities as
          the law requires.
        </p>
      </>
    ),
  },
  {
    id: "children",
    title: "Children",
    body: <p>Social Hood is a tool for businesses. Accounts are for people who are 18 or older.</p>,
  },
  {
    id: "changes",
    title: "Changes to this policy",
    body: (
      <p>
        When we change this policy we update the date at the top. If a change is significant, we&apos;ll tell you by email
        or in the app before it takes effect.
      </p>
    ),
  },
  {
    id: "contact",
    title: "Contact us",
    body: (
      <>
        <p>For privacy questions, requests or grievances, email {mail}.</p>
        <LegalFacts />
      </>
    ),
  },
];

export default function PrivacyPage() {
  return (
    <LegalPage
      document="privacy"
      sections={SECTIONS}
      summary={
        <>
          <p>
            Social Hood is an inbox and automation tool for businesses on Instagram and WhatsApp. To do that, we handle your
            account data and the messages, comments and profiles of your customers that Meta sends us when they contact your
            business.
          </p>
          <p>
            We use it only to run Social Hood. <strong>We never sell it, never use it for ads, and never ask for your
            Instagram or Facebook password.</strong> You can delete your workspace at any time, and its data is removed
            within 24 hours.
          </p>
        </>
      }
    />
  );
}
