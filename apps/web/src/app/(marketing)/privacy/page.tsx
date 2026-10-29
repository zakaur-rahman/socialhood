import Link from "next/link";

import { LegalFacts, LegalPage, type LegalSection } from "@/components/marketing/legal/LegalPage";
import { SubprocessorTable } from "@/components/marketing/legal/SubprocessorTable";
import { LEGAL, grievanceDays, operatorName, publicLocation } from "@/lib/legal";
import { SITE_NAME } from "@/lib/marketing/site";
import { pageMetadata } from "@/lib/marketing/seo";

export const metadata = pageMetadata({
  title: "Privacy Policy",
  description: `How ${SITE_NAME} collects, uses, shares, keeps and deletes personal data, including Instagram, Facebook and WhatsApp data, and your GDPR, CCPA and DPDP rights.`,
  path: "/privacy",
});

const N = SITE_NAME;
const email = LEGAL.contactEmail;
const mail = <a href={`mailto:${email}`}>{email}</a>;

// Grounded in the built system: BUILD_SPEC §5.9, C-056 and C-067 (retention and deletion),
// C-049/C-053 (email and push), C-057 (Sentry scrubbing), C-145 (one GCP VM in asia-southeast1,
// nightly backups kept at most 30 days: infra/vm/backup.sh), C-149 (billing and Sentry off until
// configured), FR-PRV-01/02 and SEC-11/12, the growth-plan integrations (C-103 Sheets, C-116 Shopify,
// C-120 Razorpay, GR-28 website chat, GR-29 Facebook Pages) and the purge jobs (jobs/tasks/purge.py).
// C-144 checked it against Meta's Platform Terms §4, the DPDP Act and Rules, and Google's API
// Services User Data Policy. C-156 added the GDPR mechanics (roles, legal bases, transfers, rights by
// region), the CCPA section, the shared subprocessor list (lib/subprocessors.ts) and the Gemini
// paid-tier facts (ai/gemini.py uses an API key on the Gemini Developer API, not Vertex AI; Google's
// Gemini API Additional Terms, effective 2026-03-23, read 2026-10-29). NOT reviewed by a lawyer (no
// lawyer budget, C-156).
function sections(): LegalSection[] {
  const operator = operatorName(LEGAL);
  const where = publicLocation();
  return [
    {
      id: "who-we-are",
      title: "Who we are and what this covers",
      body: (
        <>
          <p>
            {N} is run by {operator} (&quot;we&quot;, &quot;us&quot;), a sole proprietorship registered in India and based
            in {where}. This policy explains how we handle personal data when you visit our website, when you use the {N}{" "}
            app, and when you message or comment on a business or creator that uses {N}, on Instagram, Facebook, WhatsApp
            or a website chat.
          </p>
          <LegalFacts />
          <h3>Our role</h3>
          <ul>
            <li>
              <strong>Your account data</strong> (for example your name, email, workspace and billing details): we decide
              how it is used and are responsible for it. We are its <strong>controller</strong> under the GDPR and its Data
              Fiduciary under India&apos;s Digital Personal Data Protection Act, 2023 (DPDP Act).
            </li>
            <li>
              <strong>Your customers&apos; and followers&apos; data</strong> (the messages, comments, contacts and profiles
              that arrive from Instagram, Facebook, WhatsApp and website chat, or that a business adds): the business or
              creator that connected the account decides why it is processed, and is its controller (and Data Fiduciary).
              We process it on their behalf and on their instructions, as their <strong>processor</strong> (Data
              Processor), under our <Link href="/dpa">Data Processing Agreement</Link>.
            </li>
          </ul>
          <p>
            If you messaged or commented on a business or creator that uses {N}, they are your first point of contact for
            your data, and their own privacy notice applies. You can also write to us and we&apos;ll help them respond.
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
            When you connect an Instagram professional account, a Facebook Page or a WhatsApp Business number, Meta gives us
            the account&apos;s ID, username, Page name or phone number, name and profile picture, the permissions you
            granted, and access tokens that let {N} act for the account. We never ask for or receive your Instagram or
            Facebook password, and we store access tokens encrypted.
          </p>
          <h3>Messages, comments and the people who send them</h3>
          <ul>
            <li>
              Instagram direct messages, Messenger messages to a connected Facebook Page, and WhatsApp messages sent to and
              from your connected accounts: text, photos, videos, voice notes and other attachments, reactions, and whether
              each was sent, delivered and read.
            </li>
            <li>Comments and replies on your Instagram posts and Reels and on your Facebook Page&apos;s posts.</li>
            <li>
              What Meta shares about the people who message or comment: their name, username, profile picture, WhatsApp
              phone number, the ad or link a chat started from, and whether they follow your Instagram account (used only
              for the optional follow nudge).
            </li>
          </ul>
          <h3>Website chat</h3>
          <p>
            If a business adds {N}&apos;s chat to its website, we receive the messages a visitor sends, the name and email
            address they choose to give, their answer to any marketing consent question (with the words shown and the
            time), the page&apos;s address, and their IP address, which we use only to limit abuse. The chat keeps a
            random visitor ID in the visitor&apos;s browser so the conversation continues on their next visit.
          </p>
          <h3>Contacts, orders and consent</h3>
          <p>
            The contact details a business keeps about its customers in {N}: names, phone numbers, email addresses, notes,
            tags and custom fields; orders with their items, amounts, delivery address and payment status; and records of
            each customer&apos;s consent to marketing messages, including when and how it was given or withdrawn.
          </p>
          <h3>Content you add</h3>
          <p>
            Your knowledge base (text, the content of web pages you link, and files you upload), product catalogue,
            automations, sequences, scheduled posts and messages, captions, and the photos and videos you upload. {N} can
            also show your posts&apos; and account&apos;s insights, such as reach and saves, but only if you grant Meta&apos;s
            insights permission; we don&apos;t ask for it today.
          </p>
          <h3>What the AI produces</h3>
          <p>
            The analysis of messages and comments (intent, sentiment, lead score, language, topics and spam), conversation
            and comment summaries, suggested replies, knowledge gaps, and your questions to Ask {N} with its answers.
          </p>
          <h3>Billing</h3>
          <p>
            Your plan and subscription status. Paid plans aren&apos;t on sale yet. When they are, card and other payment
            details go to Dodo Payments, which runs checkout; we never see or store full card numbers.
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
      title: "How we use it, and our legal bases",
      body: (
        <>
          <p>
            For the data we control, this table shows each purpose and the legal basis we rely on under the GDPR (Article
            6(1)). For your customers&apos; and followers&apos; data, the business or creator chooses the legal basis; we
            only process it to provide {N} to them.
          </p>
          <div className="overflow-x-auto">
            <table>
              <thead>
                <tr>
                  <th scope="col">Purpose</th>
                  <th scope="col">Data</th>
                  <th scope="col">Legal basis</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>
                    Run your account and workspace: show your conversations, send your replies and automated messages, publish
                    posts, run automations and the AI features you use, and connect the tools you choose
                  </td>
                  <td>Account, workspace and connected-account details, content you add</td>
                  <td>Performing our contract with you (Art. 6(1)(b))</td>
                </tr>
                <tr>
                  <td>Email and push notifications, the weekly digest, and messages about your account</td>
                  <td>Email address, push subscription, notification choices</td>
                  <td>Contract (Art. 6(1)(b)); you can turn the optional ones off in Settings</td>
                </tr>
                <tr>
                  <td>Plans, AI credits and, once paid plans open, billing</td>
                  <td>Plan, subscription status, AI credit use</td>
                  <td>Contract (Art. 6(1)(b)); keeping tax and accounting records the law requires (Art. 6(1)(c))</td>
                </tr>
                <tr>
                  <td>Answer you when you contact support</td>
                  <td>What you send us, your account details</td>
                  <td>Contract (Art. 6(1)(b)) or our legitimate interest in answering you (Art. 6(1)(f))</td>
                </tr>
                <tr>
                  <td>Keep {N} secure, prevent abuse and spam, limit request rates and fix errors</td>
                  <td>IP addresses, request details, error reports with message text removed</td>
                  <td>Our legitimate interest in a secure, working service for everyone (Art. 6(1)(f))</td>
                </tr>
                <tr>
                  <td>Meet our legal obligations, and establish or defend legal claims</td>
                  <td>What the obligation or claim needs</td>
                  <td>Legal obligation (Art. 6(1)(c)); legitimate interest (Art. 6(1)(f))</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p>
            Where we rely on legitimate interests, we have weighed them against your rights, and you can object (see{" "}
            <a href="#your-rights">Your rights</a>). Under India&apos;s DPDP Act we process your account data for the
            purposes you give it to us for, and you can withdraw consent at any time.
          </p>
          <p>
            <strong>We don&apos;t sell personal data, we don&apos;t use it for advertising, and we don&apos;t train AI
            models on it.</strong>{" "}
            We don&apos;t send marketing emails. People at {N} look at a workspace&apos;s data only when you ask us for
            help, to investigate a problem or abuse, or when the law requires it.
          </p>
        </>
      ),
    },
    {
      id: "meta-data",
      title: "Data from Instagram, Facebook and WhatsApp",
      body: (
        <>
          <p>When a business or creator connects an account, Meta&apos;s platforms send us:</p>
          <ul>
            <li>
              <strong>Instagram:</strong> the account&apos;s ID, username, name and profile picture; direct messages,
              including replies to and mentions in stories, with their photos, videos, voice notes, stickers and reactions;
              comments and replies on posts and Reels; the posts {N} publishes for the account; and, for the people who
              message or comment, their name, username, profile picture, whether they follow the account, and the ad or
              link a chat started from.
            </li>
            <li>
              <strong>Facebook Pages</strong> (with Meta&apos;s approval): the Page&apos;s ID and name; Messenger messages
              to the Page; comments on the Page&apos;s posts; and the name and profile picture Meta shares for the people
              who write.
            </li>
            <li>
              <strong>WhatsApp:</strong> the business number&apos;s ID, display name and phone number; messages sent to and
              from it, including photos, videos, voice notes, documents, locations, button replies and orders; whether each
              message was delivered and read; and the customer&apos;s WhatsApp phone number, profile name and the ad a chat
              started from.
            </li>
            <li>The access tokens and permissions the account holder granted.</li>
          </ul>
          <p>
            <strong>Why:</strong> only to provide {N} to that business or creator: its inbox, replies, AI drafts and
            automations, publishing and analytics. We don&apos;t sell this data, use it for ads, share it with data brokers,
            or use it to build profiles of people across businesses.
          </p>
          <p>
            <strong>Deleting it:</strong>
          </p>
          <ul>
            <li>
              Disconnecting an account deletes its access token at once, and no new messages or comments arrive for it.
              What was already stored stays in the workspace until the business deletes it.
            </li>
            <li>
              Deleting an account&apos;s data (Disconnect and delete data, in Settings → Connections), deleting the
              workspace, or a deletion request through Instagram or Facebook removes everything stored for the account
              within 24 hours. Raw events from Meta are deleted after 30 days in any case.
            </li>
            <li>
              Anyone can ask: on our <Link href="/data-deletion">data deletion page</Link>, or by emailing {mail}. See{" "}
              <a href="#deleting">Deleting your data</a>.
            </li>
          </ul>
          <p>
            We use Meta&apos;s official APIs and follow Meta&apos;s Platform Terms. Meta&apos;s own privacy policy covers
            what happens on its platforms.
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
            {N}&apos;s AI features use Google&apos;s Gemini API: analysing messages and comments, drafting and sending
            replies, summaries, captions and hashtags, searching your knowledge base, and answering Ask {N} questions.
            Replies are drafted from the business&apos;s own knowledge base and the conversation. For each task we send
            Google the text it needs, such as a message with the recent conversation and the relevant parts of the knowledge
            base, and Google returns the result.
          </p>
          <p>
            We use the Gemini API as a paid service. Under{" "}
            <a href="https://ai.google.dev/gemini-api/terms" rel="noopener noreferrer">
              Google&apos;s terms for the paid Gemini API
            </a>
            , Google doesn&apos;t use what we send, or what it returns, to improve its products. Google keeps it for a
            limited time to detect misuse, and may store or cache it briefly in any country where it has facilities. We
            don&apos;t use your data to train AI models either.
          </p>
          <ul>
            <li>
              Each connected account has an AI mode: <strong>Off</strong>, <strong>Suggest</strong> (the AI drafts, a person
              sends) or <strong>Auto</strong> (the AI replies by itself when it&apos;s confident, and hands anything else to a
              person). Auto sends without a person reviewing the reply, and only if the business turns it on.
            </li>
            <li>
              With AI analysis turned off for an account, its messages and comments aren&apos;t sent to Google for analysis
              or summaries. Features you use on purpose, like a suggested reply or Ask {N}, still send the text they need.
            </li>
            <li>
              A business can add a short line, such as &quot;Sent automatically&quot;, to the messages its automations and
              Auto mode send (Settings → Workspace).
            </li>
            <li>Ask {N} reads your workspace&apos;s data to answer. It never sends, changes or deletes anything.</li>
          </ul>
          <h3>Automated decisions</h3>
          <p>
            The AI drafts and sends replies, scores leads, flags likely spam and, if a business turns it on, hides spam
            comments. These help a business run its inbox; none of them makes a decision that has a legal or similarly
            significant effect on anyone. A person at the business can review and change any of them, and the business can
            switch Auto mode and spam hiding off at any time. AI output can be wrong; our{" "}
            <Link href="/terms#ai-features">Terms of Service</Link> explain who is responsible for what the AI sends.
          </p>
        </>
      ),
    },
    {
      id: "google-user-data",
      title: "Google user data",
      body: (
        <>
          <p>We receive data from Google&apos;s APIs in two cases:</p>
          <ul>
            <li>
              <strong>Google sign-in</strong> (through Clerk): your name, email address and profile photo, used only to
              create and sign in to your account.
            </li>
            <li>
              <strong>Google Sheets sync</strong>, if a business connects it: the email address of the Google account it
              connects, and access to only the spreadsheets {N} creates or that the business picks (Google&apos;s{" "}
              <code>drive.file</code> permission). We use it only to add the business&apos;s new leads as rows to its
              chosen sheet. We can&apos;t see the rest of its Google Drive.
            </li>
          </ul>
          <p>
            {N}&apos;s use and transfer to any other app of information received from Google APIs will adhere to the{" "}
            <a href="https://developers.google.com/terms/api-services-user-data-policy" rel="noopener noreferrer">
              Google API Services User Data Policy
            </a>
            , including the Limited Use requirements. We don&apos;t use Google user data for advertising, don&apos;t sell
            it, don&apos;t use it to train AI models, and people at {N} read it only with your permission, for security, or
            when the law requires. You can disconnect Google at any time in {N}, or remove {N}&apos;s access in your Google
            Account&apos;s security settings.
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
            <strong>Meta.</strong> Your replies, automated messages and posts go to Instagram, Facebook and WhatsApp through
            Meta&apos;s official APIs.
          </p>
          <p>
            <strong>Our subprocessors</strong>, the service providers that process data for us, only to run {N}. The list is
            kept on our <Link href="/subprocessors">subprocessors page</Link>, which is the up-to-date version:
          </p>
          <SubprocessorTable />
          <p>
            Browser push services (for example Google, Apple, Mozilla and Microsoft) deliver the notifications you turn on,
            encrypted so only your device can read them. Service health metrics go to Grafana Cloud and contain no personal
            data. Once paid plans open, Dodo Payments handles payments as merchant of record, under its own privacy policy.
          </p>
          <p>
            <strong>Tools a business connects.</strong> A business can connect its own accounts with other services. We then
            send them what the business sets up, on its instructions, and their own terms and privacy policies apply:
          </p>
          <div className="overflow-x-auto">
            <table>
              <thead>
                <tr>
                  <th scope="col">Service</th>
                  <th scope="col">What it&apos;s for</th>
                  <th scope="col">Data involved</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Razorpay (the business&apos;s own account)</td>
                  <td>Payment links and UPI for the business&apos;s orders, and refunds</td>
                  <td>The customer&apos;s name and phone number, the order number and amount</td>
                </tr>
                <tr>
                  <td>Shopify (the business&apos;s own store, with our Shopify app listing)</td>
                  <td>Brings the store&apos;s products into the catalogue</td>
                  <td>We only read products; we send no customer data to Shopify</td>
                </tr>
                <tr>
                  <td>Google Sheets (the business&apos;s own Google account)</td>
                  <td>Adds new leads to a spreadsheet</td>
                  <td>The lead fields the business chooses, such as name, phone, email and source</td>
                </tr>
                <tr>
                  <td>Zapier, the public API and webhooks (on the business&apos;s instructions)</td>
                  <td>Sends events to the business&apos;s other tools</td>
                  <td>The events and fields the business subscribes to, such as new contacts and messages</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p>
            <strong>When the law requires it.</strong> We may disclose data when the law requires it, or to protect the
            rights, safety or property of our users, the public or {N}.
          </p>
          <p>
            <strong>If the business changes hands.</strong> If {N} is sold or merged, personal data may pass to the new
            owner, who must keep protecting it as this policy describes. We&apos;ll tell you before that happens.
          </p>
        </>
      ),
    },
    {
      id: "transfers",
      title: "Where your data goes",
      body: (
        <>
          <p>
            We are in India. The website, the app, our API, database, background jobs and backups run on Google Cloud in
            Singapore (asia-southeast1). Some of our subprocessors process data in other countries, mainly the United
            States, and Google may process AI requests wherever it has facilities. Each one&apos;s location is on the{" "}
            <Link href="/subprocessors">subprocessors page</Link>.
          </p>
          <ul>
            <li>
              <strong>From the EEA and the UK</strong>, where the destination has no adequacy decision, we rely
              on the European Commission&apos;s Standard Contractual Clauses (and the UK Addendum to them): in our{" "}
              <Link href="/dpa#transfers">Data Processing Agreement</Link> with business customers, and in our
              subprocessors&apos; data processing terms. You can ask us for a copy at {email}.
            </li>
            <li>
              <strong>From India</strong>, we transfer data outside India only as the DPDP Act allows.
            </li>
          </ul>
        </>
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
                  <td>Your user account (name, email, profile photo)</td>
                  <td>
                    While your account exists. When it is deleted, the workspaces only you own are deleted too (see below).
                  </td>
                </tr>
                <tr>
                  <td>
                    A workspace&apos;s data: conversations, comments, contacts, consent records, orders, knowledge,
                    automations, posts, media and settings
                  </td>
                  <td>While the workspace exists. Removed within 24 hours of deleting the workspace.</td>
                </tr>
                <tr>
                  <td>
                    A connected account&apos;s data: its conversations, messages, contacts, comments, posts, automations and
                    message files
                  </td>
                  <td>
                    Until the business deletes that account&apos;s data (or Meta asks us to), then permanently removed within
                    24 hours, usually within minutes.
                  </td>
                </tr>
                <tr>
                  <td>A disconnected account&apos;s access token</td>
                  <td>Deleted at once when the account is disconnected</td>
                </tr>
                <tr>
                  <td>Messages on the Free plan (including after a paid plan ends)</td>
                  <td>90 days, then deleted with their analysis. Conversations left with no messages are deleted too.</td>
                </tr>
                <tr>
                  <td>Messages on Pro and Max</td>
                  <td>While the workspace exists</td>
                </tr>
                <tr>
                  <td>The raw events Meta sends us</td>
                  <td>30 days</td>
                </tr>
                <tr>
                  <td>Logs of what we sent to webhooks and Google Sheets</td>
                  <td>30 days</td>
                </tr>
                <tr>
                  <td>Notifications</td>
                  <td>90 days</td>
                </tr>
                <tr>
                  <td>Ask {N} conversations</td>
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
                  <td>Database backups</td>
                  <td>Nightly copies: the last 7 days and the last 4 Sundays, never more than 30 days, then deleted.</td>
                </tr>
                <tr>
                  <td>Records of data deletion requests (a confirmation code, the Meta account ID and the status)</td>
                  <td>Kept, so the status page keeps working</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p>
            Deleted data can remain in our database backups until those backups expire, at most 30 days later. Daily jobs
            remove data when its period ends. Once paid plans open, Dodo Payments keeps payment records for as long as the
            law requires.
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
              permanently removed within 24 hours. If your {N} user account is deleted, the workspaces only you own are
              deleted the same way.
            </li>
            <li>
              <strong>Disconnect an account</strong> (Settings → Connections). Its access token is deleted at once and no new
              messages or comments arrive for it. What was already stored stays in the workspace until you delete it.
            </li>
            <li>
              <strong>Delete an account&apos;s data</strong> (Settings → Connections, owners and admins: Disconnect and delete
              data, or Remove for an account already disconnected). The account is disconnected at once, then everything
              stored for it is permanently deleted within 24 hours: its conversations and messages with their AI analysis
              and suggested replies, its contacts, its comments, its posts and their statistics, the automations and
              scheduled messages and posts for it, the photos and files received or sent in its messages, and the account
              itself. The workspace&apos;s knowledge base, settings, members and billing, and its other accounts, are kept.
            </li>
            <li>
              <strong>Remove {N} from Instagram or Facebook.</strong> Removing {N} in your Instagram or Facebook settings
              disconnects the account. If you also ask for your data to be deleted, Meta sends us your request: we
              disconnect every account connected with your login, in every workspace, and delete each one&apos;s data as
              described above, along with the raw events Meta sent us for it. You get a confirmation code you can check on
              our <Link href="/data-deletion">data deletion page</Link>; it shows the request as completed once every
              account&apos;s data is gone.
            </li>
            <li>
              <strong>Email us</strong> at {mail}. Anyone can ask, including customers of a business that uses {N}. We may
              need to confirm who you are, and for customers&apos; data we work with the business it belongs to.
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
          <h3>Everyone</h3>
          <p>Wherever you live, you can ask us to:</p>
          <ul>
            <li>tell you what personal data we hold about you and give you a copy;</li>
            <li>correct it or delete it;</li>
            <li>stop using it for something you object to.</li>
          </ul>
          <p>
            Email {mail} from the email address of your {N} account, or tell us the Instagram username, Facebook name or
            WhatsApp number you messaged a business from, so we can find your data and confirm it&apos;s yours. Your
            account settings also let you correct your details and delete your data yourself. If your data reached us through
            a business&apos;s account, we pass your request to that business and help it respond. We never charge for a
            request and never treat you worse for making one.
          </p>

          <h3>EEA and UK (GDPR)</h3>
          <p>If the GDPR or the UK GDPR applies, you have the right to:</p>
          <ul>
            <li>access your personal data (Article 15) and have it corrected (Article 16) or erased (Article 17);</li>
            <li>restrict how we use it (Article 18);</li>
            <li>receive the data you gave us in a portable format (Article 20);</li>
            <li>object to processing based on our legitimate interests (Article 21);</li>
            <li>withdraw consent at any time, where we rely on it, without affecting what came before;</li>
            <li>
              not be subject to a decision based solely on automated processing that has legal or similarly significant
              effects (Article 22); we don&apos;t make such decisions;
            </li>
            <li>
              complain to a data protection authority, in particular where you live or work (Article 77). In the UK, that is
              the Information Commissioner&apos;s Office.
            </li>
          </ul>
          <p>We answer within one month, which the law lets us extend by two more months for complex requests.</p>

          <h3>California (CCPA/CPRA)</h3>
          <ul>
            <li>
              In the last 12 months we have collected the categories of personal information described in{" "}
              <a href="#what-we-collect">What we collect</a>: identifiers (such as name, email, username and IP address),
              customer records, commercial information (your plan), internet activity (request and error logs) and the
              content of messages, for the purposes in <a href="#how-we-use-it">How we use it</a>.
            </li>
            <li>
              <strong>We don&apos;t sell or share personal information</strong>, as the CCPA defines those words, and
              haven&apos;t done so in the last 12 months. We don&apos;t knowingly sell or share the personal information of
              anyone under 16.
            </li>
            <li>
              We honour <strong>Global Privacy Control</strong>: if your browser sends it, we treat it as a request to opt
              out of sale and sharing. Because we do neither, nothing changes for you.
            </li>
            <li>
              You can ask to know, delete and correct your personal information. You can use an authorised agent; we may
              ask them for proof. We won&apos;t discriminate against you for using these rights.
            </li>
          </ul>

          <h3>India (DPDP Act)</h3>
          <p>Under the DPDP Act, you can ask us to:</p>
          <ul>
            <li>give you a summary of the personal data we hold about you and how we process it;</li>
            <li>correct, complete or update it;</li>
            <li>erase it;</li>
            <li>
              stop processing that relies on your consent, by withdrawing it, as easily as you gave it: email us at any
              time, or tell the business you no longer want its marketing messages;
            </li>
            <li>let someone you nominate exercise these rights if you die or can&apos;t act yourself;</li>
            <li>address a grievance about how we handle your data.</li>
          </ul>
          <h3>Grievances</h3>
          <p>
            Write to our Grievance Officer at {mail} with &quot;Grievance&quot; in the subject. We acknowledge it and answer
            within {grievanceDays(LEGAL)} days. If you aren&apos;t satisfied with our answer, you can complain to the Data
            Protection Board of India, or to the data protection authority where you live.
          </p>
        </>
      ),
    },
    {
      id: "cookies",
      title: "Cookies and local storage",
      body: (
        <p>
          We only use cookies and browser storage that {N} needs to work: Clerk&apos;s sign-in cookies, a theme cookie, and
          a few view preferences and the website chat&apos;s visitor ID in local storage. We don&apos;t use analytics,
          advertising or tracking cookies, so there is no cookie banner. Every item, what it&apos;s for and how long it
          lasts is on our <Link href="/cookies">cookies page</Link>.
        </p>
      ),
    },
    {
      id: "security",
      title: "Security and breaches",
      body: (
        <>
          <p>
            Connections to {N} are encrypted with HTTPS. Instagram, Facebook and WhatsApp connect through Meta&apos;s
            official APIs, access tokens and payment keys are stored encrypted, and every workspace&apos;s data is kept
            separate from every other workspace. Only the people who run {N} can reach our production systems. Annex 2 of
            our <Link href="/dpa#annex-2">Data Processing Agreement</Link> lists our security measures.
          </p>
          <p>
            No system is perfectly secure. If a breach affects your personal data, we&apos;ll tell you without delay what
            happened, what it may mean for you, what we&apos;re doing about it and what you can do, and we&apos;ll report it
            to the Data Protection Board of India and other authorities as the law requires. When a breach affects a
            business&apos;s customers, we tell the business without undue delay, and within 72 hours, so it can tell them.
          </p>
        </>
      ),
    },
    {
      id: "children",
      title: "Children",
      body: (
        <p>
          {N} is a tool for businesses and creators. Accounts are for people who are 18 or older, and we don&apos;t
          knowingly collect children&apos;s data for our own purposes. If you think a child has created an account, email{" "}
          {mail} and we&apos;ll delete it. A business&apos;s customers or a creator&apos;s followers may include children;
          the business or creator is responsible for that data, and we never use it to track or target anyone with
          advertising.
        </p>
      ),
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
          <p>
            For privacy questions, requests or grievances, email {mail}. More ways to reach us are on our{" "}
            <Link href="/contact">contact page</Link>.
          </p>
          <LegalFacts />
        </>
      ),
    },
  ];
}

export default function PrivacyPage() {
  return (
    <LegalPage
      document="privacy"
      sections={sections()}
      summary={
        <>
          <p>
            {N} is an inbox and automation tool for businesses and creators on Instagram, Facebook, WhatsApp and website
            chat. To do that, we handle your account data, and the messages, comments and profiles that Meta and your
            website send us when people contact you. For your account data we are the controller; for your customers&apos;
            and followers&apos; data, you are, and we process it for you.
          </p>
          <p>
            We use it only to run {N}.{" "}
            <strong>
              We never sell it, never use it for ads, and never ask for your Instagram or Facebook password.
            </strong>{" "}
            You can delete your workspace at any time, and its data is removed within 24 hours.
          </p>
        </>
      }
    />
  );
}
