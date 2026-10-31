import { Clock, Gauge, MessageSquareReply, ScrollText } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { AutomationCard, ChannelMark } from "@/components/marketing/automations/AutomationPageView";
import { HubInbox } from "@/components/marketing/automations/scenes";
import { ExplainerMotion } from "@/components/marketing/explainers/ExplainerMotion";
import { FinalCta } from "@/components/marketing/FinalCta";
import { BreadcrumbJsonLd, JsonLd } from "@/components/marketing/JsonLd";
import { Ico } from "@/components/marketing/landing/Ico";
import { SECTION_EYEBROW } from "@/components/marketing/primitives";
import { AUTOMATIONS_PATH, AUTOMATION_PAGES, CHANNEL_NAME, META, type AutomationChannel, type MetaSource } from "@/lib/marketing/automation-pages";
import { pageMetadata } from "@/lib/marketing/seo";
import { SITE_NAME, absoluteUrl } from "@/lib/marketing/site";

export const metadata = pageMetadata({
  title: "Automations for Instagram, WhatsApp and web chat",
  description:
    "Every automation type: Instagram comment to DM, story replies, DM keywords and conversation starters, WhatsApp auto-reply and AI website chat.",
  path: AUTOMATIONS_PATH,
});

/** The rules every automation keeps, each from Meta's own page (lib/marketing/automation-pages META). */
const RULES: { icon: LucideIcon; title: string; body: string; source: MetaSource }[] = [
  {
    icon: MessageSquareReply,
    title: "One private reply per comment",
    body: "Instagram allows one private message in reply to a comment, within 7 days of it. More can follow once the person replies.",
    source: META.privateReplies,
  },
  {
    icon: Clock,
    title: "A 24-hour window for DMs",
    body: "On Instagram and WhatsApp a business can reply for 24 hours after the customer's last message. Each new message restarts it.",
    source: META.messaging,
  },
  {
    icon: ScrollText,
    title: "Templates after the window on WhatsApp",
    body: "Once WhatsApp's window closes, only templates Meta has approved can be sent, and Meta charges for them per message.",
    source: META.waWindow,
  },
  {
    icon: Gauge,
    title: "Sending limits",
    body: `Meta allows 750 private replies to comments an hour for each Instagram account. ${SITE_NAME} queues the rest and sends them as the limit allows.`,
    source: META.limits,
  },
];

/** One channel's pages, headed by the channel's mark. */
function Group({ channel }: { channel: AutomationChannel }) {
  const pages = AUTOMATION_PAGES.filter((page) => page.channel === channel);
  return (
    <section aria-labelledby={`ap-ch-${channel}`} className="ap-group">
      <h3 id={`ap-ch-${channel}`} className="ap-group-h">
        <ChannelMark channel={channel} />
        {CHANNEL_NAME[channel]}
      </h3>
      <ul className="g-cards">
        {pages.map((page) => (
          <li key={page.path}>
            <AutomationCard page={page} headingLevel={4} />
          </li>
        ))}
      </ul>
    </section>
  );
}

/**
 * /automations (C-163): the hub of the automation and channel pages. A split head, the pages as cards
 * by channel, the hero inbox they all hand off to, the Meta rules every automation keeps (each with
 * its source), and the night close. ItemList and breadcrumb structured data. Static; one idle island
 * plays the inbox's sort once as it arrives. The app's own automations live under /w/{slug}/automations,
 * so this path is free (C-163).
 */
export default function AutomationsHub() {
  const itemList = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name: "Automations",
    itemListElement: AUTOMATION_PAGES.map((page, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: page.name,
      url: absoluteUrl(page.path),
    })),
  };
  return (
    <main id="main" tabIndex={-1} className="guides xp ap ap-hub flex-1 outline-none">
      <BreadcrumbJsonLd name="Automations" path={AUTOMATIONS_PATH} />
      <JsonLd data={itemList} />
      <section className="page-head gi-head">
        <div className="wrap split-head">
          <div>
            <p className={SECTION_EYEBROW}>Automations</p>
            <h1 className="h-page">Automations for Instagram, WhatsApp and website chat</h1>
          </div>
          <div>
            <p className="lede">
              Answer comments, Story replies and keywords on Instagram, reply on WhatsApp inside its 24-hour window, and chat with
              visitors on your own site. Each page explains how one automation works, the rules Meta sets for it and what each
              plan includes.
            </p>
          </div>
        </div>
      </section>

      <section aria-labelledby="ap-types-title" className="gi-list ap-types">
        <div className="wrap">
          <h2 id="ap-types-title" className="sr-only">
            Every automation type
          </h2>
          <Group channel="instagram" />
          {/* WhatsApp and website chat have one page each: side by side from a tablet. */}
          <div className="ap-pair">
            <Group channel="whatsapp" />
            <Group channel="web" />
          </div>
        </div>
      </section>

      <section aria-labelledby="ap-inbox-title" className="ap-band">
        <div className="wrap ap-inbox">
          <div>
            <h2 id="ap-inbox-title" className="h-sec">
              Every automation hands off to one inbox
            </h2>
            <p className="lede">
              When an automation has done its part, the conversation carries on in the same inbox as everything else, where the AI
              drafts or sends the next reply from your knowledge and brings in a person when it should.
            </p>
          </div>
          <HubInbox />
        </div>
      </section>

      <section aria-labelledby="ap-rules-title" className="ap-rules-sec">
        <div className="wrap">
          <h2 id="ap-rules-title" className="h-sec">
            The rules every automation keeps
          </h2>
          <ul className="ap-rules">
            {RULES.map((rule) => (
              <li key={rule.title} className="ap-rule-card">
                <Ico icon={rule.icon} />
                <h3>{rule.title}</h3>
                <p>{rule.body}</p>
                <a href={rule.source.url} rel="noopener noreferrer" target="_blank" className="tlink">
                  {rule.source.label}
                  <span className="sr-only"> (Meta, opens in a new tab)</span>
                </a>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <FinalCta />
      <ExplainerMotion />
    </main>
  );
}
