import Link from "next/link";

import { InfoPage, type InfoSection } from "@/components/marketing/InfoPage";
import { SUPPORT_EMAIL } from "@/lib/copy";
import { pageMetadata } from "@/lib/marketing/seo";
import { SITE_NAME } from "@/lib/marketing/site";

const PATH = "/safety";

export const metadata = pageMetadata({
  title: "Safety and Meta's limits",
  description: `How ${SITE_NAME} keeps to Meta's limits and queues what it sends, why there's no password to share, and what we never do.`,
  path: PATH,
});

const mail = <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>;

// Every rate below is the API's own pacing, sized to Meta's published limits:
// apps/api/src/socialhood/platforms/buckets.py (SPECS), shared by every worker so more workers
// never send faster. The queue and its order: services/automations/queue.py. The 7-day limit:
// services/comments/actions.py PRIVATE_REPLY_LIMIT. Held sends on a reconnect-needed account and
// the reconnect email: services/automations/queue.py, services/notifications.py (EMAIL_TYPES).
const SECTIONS: InfoSection[] = [
  {
    id: "limits",
    title: "Meta's limits, and how we queue what we send",
    body: (
      <>
        <p>
          Meta limits how fast an app may send for each Instagram account and WhatsApp number. {SITE_NAME} paces every send to
          stay inside those limits, for each account on its own, however many workers are running:
        </p>
        <table>
          <thead>
            <tr>
              <th scope="col">What is sent</th>
              <th scope="col">Our pace, per account</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Private replies to Instagram comments (comment-to-DM)</td>
              <td>At most 750 in any hour</td>
            </tr>
            <tr>
              <td>Instagram messages: text, links and reactions</td>
              <td>Up to 100 a second</td>
            </tr>
            <tr>
              <td>Instagram messages with audio, video or images</td>
              <td>Up to 10 a second</td>
            </tr>
            <tr>
              <td>WhatsApp messages</td>
              <td>Up to 80 a second for each number</td>
            </tr>
          </tbody>
        </table>
        <p>
          When more is waiting than the limit allows, for example when a Reel takes off and hundreds of people comment the
          keyword, the rest waits in a queue and goes out as the limit allows, oldest or newest first as you choose for each
          automation. Nothing is sent twice. A busy account never slows down another one.
        </p>
        <p>
          Instagram only allows a private reply to a comment within 7 days of the comment. A queued reply that reaches that
          limit is not sent, and the automation&apos;s results say why.
        </p>
        <p>
          Instagram also only lets a business message someone within 24 hours of that person&apos;s last message, and{" "}
          {SITE_NAME} shows when that window closes.
        </p>
      </>
    ),
  },
  {
    id: "login",
    title: "Official APIs and login, with no password shared",
    body: (
      <ul>
        <li>Instagram connects with Instagram&apos;s own login, and WhatsApp through Meta&apos;s sign-up window.</li>
        <li>
          You choose what to allow on Meta&apos;s screen. {SITE_NAME} receives an access token, stored encrypted, and never sees
          or asks for your Instagram or Facebook password.
        </li>
        <li>Everything goes through Meta&apos;s official APIs. You can disconnect an account at any time.</li>
      </ul>
    ),
  },
  {
    id: "never",
    title: "What we never do",
    body: (
      <ul>
        <li>
          <strong>No scraping.</strong> We read only what Meta&apos;s APIs give us for the accounts you connect. We don&apos;t
          collect data from other people&apos;s profiles or pages.
        </li>
        <li>
          <strong>No follow-gating.</strong> Meta&apos;s rules don&apos;t allow making a follow, like or share the price of
          something you promised. Our follow invite is sent only after the message the person asked for, never instead of it,
          and our templates never withhold a link from people who don&apos;t follow. Don&apos;t build a flow that does.
        </li>
        <li>
          <strong>No buying or selling engagement.</strong> We don&apos;t sell followers, likes, comments or views, and we
          don&apos;t help anyone fake them.
        </li>
        <li>
          <strong>No cold messages on Instagram.</strong> Instagram only lets a business message people who wrote or commented
          first, and {SITE_NAME} keeps to that.
        </li>
        <li>
          <strong>No posting behind your back.</strong> {SITE_NAME} publishes only the posts you create and schedule. Ask{" "}
          {SITE_NAME} never sends, publishes or changes anything by itself.
        </li>
      </ul>
    ),
  },
  {
    id: "restricted",
    title: "If Meta restricts your account",
    body: (
      <>
        <p>
          Meta decides on restrictions, and only Meta can lift them. {SITE_NAME} can&apos;t appeal for you or get around a
          restriction, and we won&apos;t try. What happens on our side:
        </p>
        <ul>
          <li>
            If Meta stops accepting the connection, the account is marked as needing to be reconnected and owners and admins
            get an email. Nothing is sent from it until you reconnect, and its queued comment replies wait.
          </li>
          <li>
            A send Meta refuses is listed on the Activity page with the reason in plain words. Only temporary errors are
            tried again; a refusal isn&apos;t.
          </li>
          <li>Queued comment replies still expire after Instagram&apos;s 7 days.</li>
        </ul>
        <p>
          What to do: check the account&apos;s status in the Instagram app and follow Meta&apos;s steps there. Once the account
          is in good standing again, reconnect it in {SITE_NAME}. If you&apos;re unsure what happened, write to {mail} and
          we&apos;ll help you read the errors.
        </p>
      </>
    ),
  },
  {
    id: "no-guarantees",
    title: "What we can't promise",
    body: (
      <p>
        We follow Meta&apos;s rules and limits, but we don&apos;t control Meta&apos;s decisions, and what you send is your
        responsibility. No tool can promise that an account will never be restricted, and we don&apos;t.{" "}
        {SITE_NAME}&apos;s own app is still in Meta&apos;s App Review, so some features wait on Meta&apos;s approval; each
        page says which.
      </p>
    ),
  },
];

/** /safety (C-156): Meta's limits and our queue, official login, what we never do, restrictions. */
export default function SafetyPage() {
  return (
    <InfoPage
      name="Safety"
      path={PATH}
      eyebrow="Safety"
      title="Automation that stays inside Meta's rules"
      lede={`How ${SITE_NAME} paces what it sends, why you never share a password, and what we refuse to build.`}
      sections={SECTIONS}
      footer={
        <p>
          Related: <Link href="/security">Security</Link> for reporting a vulnerability, and the{" "}
          <Link href="/privacy">Privacy policy</Link> for what we collect.
        </p>
      }
    />
  );
}
