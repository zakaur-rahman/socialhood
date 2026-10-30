import {
  BadgeCheck,
  CalendarX,
  Clock,
  HandCoins,
  Image as ImageIcon,
  KeyRound,
  LifeBuoy,
  LockKeyhole,
  MessageSquareOff,
  MessageSquareReply,
  MessagesSquare,
  OctagonAlert,
  RotateCcw,
  ScanSearch,
  Send,
  UserCheck,
} from "lucide-react";
import Link from "next/link";

import { InfoBand, InfoCard, InfoPage } from "@/components/marketing/InfoPage";
import { Ico } from "@/components/marketing/landing/Ico";
import { Callout } from "@/components/site/Callout";
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
const PACE = [
  { what: "Private replies to Instagram comments (comment-to-DM)", pace: "At most 750 in any hour", icon: MessageSquareReply },
  { what: "Instagram messages: text, links and reactions", pace: "Up to 100 a second", icon: MessagesSquare },
  { what: "Instagram messages with audio, video or images", pace: "Up to 10 a second", icon: ImageIcon },
  { what: "WhatsApp messages", pace: "Up to 80 a second for each number", icon: Send },
];

/** /safety (C-156; C-159 layout): Meta's limits and our queue, official login, what we never do, restrictions. */
export default function SafetyPage() {
  return (
    <InfoPage
      name="Safety"
      path={PATH}
      className="safety"
      eyebrow="Safety"
      title="Automation that stays inside Meta's rules"
      lede={`How ${SITE_NAME} paces what it sends, why you never share a password, and what we refuse to build.`}
    >
      <InfoBand
        id="limits"
        title="Meta's limits, and how we queue what we send"
        intro={
          <p>
            Meta limits how fast an app may send for each Instagram account and WhatsApp number. {SITE_NAME} paces every send to
            stay inside those limits, for each account on its own, however many workers are running:
          </p>
        }
      >
        <dl className="pace">
          {PACE.map((row) => (
            <div key={row.what} className="fcard pace-card">
              <dt>
                <Ico icon={row.icon} />
                <span>{row.what}</span>
              </dt>
              <dd>{row.pace}</dd>
            </div>
          ))}
        </dl>
        <div className="lprose ib-text">
          <p>
            When more is waiting than the limit allows, for example when a Reel takes off and hundreds of people comment the
            keyword, the rest waits in a queue and goes out as the limit allows, oldest or newest first as you choose for each
            automation. Nothing is sent twice. A busy account never slows down another one.
          </p>
        </div>
        <ul className="fgrid">
          <InfoCard icon={Clock}>
            <p>
              Instagram only allows a private reply to a comment within 7 days of the comment. A queued reply that reaches that
              limit is not sent, and the automation&apos;s results say why.
            </p>
          </InfoCard>
          <InfoCard icon={MessagesSquare}>
            <p>
              Instagram also only lets a business message someone within 24 hours of that person&apos;s last message, and{" "}
              {SITE_NAME} shows when that window closes.
            </p>
          </InfoCard>
        </ul>
      </InfoBand>

      <InfoBand id="login" title="Official APIs and login, with no password shared">
        <ul className="fgrid tgrid-3">
          <InfoCard icon={KeyRound}>
            <p>Instagram connects with Instagram&apos;s own login, and WhatsApp through Meta&apos;s sign-up window.</p>
          </InfoCard>
          <InfoCard icon={LockKeyhole}>
            <p>
              You choose what to allow on Meta&apos;s screen. {SITE_NAME} receives an access token, stored encrypted, and never
              sees or asks for your Instagram or Facebook password.
            </p>
          </InfoCard>
          <InfoCard icon={BadgeCheck}>
            <p>Everything goes through Meta&apos;s official APIs. You can disconnect an account at any time.</p>
          </InfoCard>
        </ul>
      </InfoBand>

      <InfoBand id="never" title="What we never do">
        <ul className="fgrid odd">
          <InfoCard icon={ScanSearch} title="No scraping.">
            <p>
              We read only what Meta&apos;s APIs give us for the accounts you connect. We don&apos;t collect data from other
              people&apos;s profiles or pages.
            </p>
          </InfoCard>
          <InfoCard icon={UserCheck} title="No follow-gating.">
            <p>
              Meta&apos;s rules don&apos;t allow making a follow, like or share the price of something you promised. Our follow
              invite is sent only after the message the person asked for, never instead of it, and our templates never withhold
              a link from people who don&apos;t follow. Don&apos;t build a flow that does.
            </p>
          </InfoCard>
          <InfoCard icon={HandCoins} title="No buying or selling engagement.">
            <p>We don&apos;t sell followers, likes, comments or views, and we don&apos;t help anyone fake them.</p>
          </InfoCard>
          <InfoCard icon={MessageSquareOff} title="No cold messages on Instagram.">
            <p>
              Instagram only lets a business message people who wrote or commented first, and {SITE_NAME} keeps to that.
            </p>
          </InfoCard>
          <InfoCard icon={CalendarX} title="No posting behind your back.">
            <p>
              {SITE_NAME} publishes only the posts you create and schedule. Ask {SITE_NAME} never sends, publishes or changes
              anything by itself.
            </p>
          </InfoCard>
        </ul>
      </InfoBand>

      <InfoBand
        id="restricted"
        title="If Meta restricts your account"
        intro={
          <p>
            Meta decides on restrictions, and only Meta can lift them. {SITE_NAME} can&apos;t appeal for you or get around a
            restriction, and we won&apos;t try. What happens on our side:
          </p>
        }
      >
        <ul className="fgrid tgrid-3">
          <InfoCard icon={OctagonAlert}>
            <p>
              If Meta stops accepting the connection, the account is marked as needing to be reconnected and owners and admins
              get an email. Nothing is sent from it until you reconnect, and its queued comment replies wait.
            </p>
          </InfoCard>
          <InfoCard icon={RotateCcw}>
            <p>
              A send Meta refuses is listed on the Activity page with the reason in plain words. Only temporary errors are
              tried again; a refusal isn&apos;t.
            </p>
          </InfoCard>
          <InfoCard icon={Clock}>
            <p>Queued comment replies still expire after Instagram&apos;s 7 days.</p>
          </InfoCard>
        </ul>
        <Callout icon={LifeBuoy}>
          <p>
            What to do: check the account&apos;s status in the Instagram app and follow Meta&apos;s steps there. Once the account
            is in good standing again, reconnect it in {SITE_NAME}. If you&apos;re unsure what happened, write to {mail} and
            we&apos;ll help you read the errors.
          </p>
        </Callout>
      </InfoBand>

      <InfoBand
        id="no-guarantees"
        title="What we can't promise"
        night
        className="info-close"
        intro={
          <>
            <p>
              We follow Meta&apos;s rules and limits, but we don&apos;t control Meta&apos;s decisions, and what you send is your
              responsibility. No tool can promise that an account will never be restricted, and we don&apos;t.{" "}
              {SITE_NAME}&apos;s own app is still in Meta&apos;s App Review, so some features wait on Meta&apos;s approval; each
              page says which.
            </p>
            <p className="info-related">
              Related: <Link href="/security">Security</Link> for reporting a vulnerability, and the{" "}
              <Link href="/privacy">Privacy policy</Link> for what we collect.
            </p>
          </>
        }
      />
    </InfoPage>
  );
}
