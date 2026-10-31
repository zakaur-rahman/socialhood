import {
  AppWindow,
  CalendarClock,
  Globe,
  Inbox,
  type LucideIcon,
  ShoppingBag,
  Sparkles,
  UsersRound,
  Workflow,
} from "lucide-react";

import { InfoPage } from "@/components/marketing/InfoPage";
import { Ico } from "@/components/marketing/landing/Ico";
import { SUPPORT_EMAIL } from "@/lib/copy";
import { legalDate } from "@/lib/legal";
import { CHANGELOG_AREAS, CHANGELOG_PATH, type ChangelogArea, changelogByMonth } from "@/lib/marketing/changelog";
import { pageMetadata } from "@/lib/marketing/seo";
import { SITE_NAME } from "@/lib/marketing/site";

const PATH = CHANGELOG_PATH;

export const metadata = pageMetadata({
  title: "What's new",
  description: `What has shipped in ${SITE_NAME}, month by month: new features for the inbox, the AI, automations and publishing, with their dates.`,
  path: PATH,
});

/** Each area's icon (C-159). Iris only on the AI (an AI moment). */
const AREA_ICONS: Record<ChangelogArea, LucideIcon> = {
  inbox: Inbox,
  ai: Sparkles,
  automations: Workflow,
  publishing: CalendarClock,
  commerce: ShoppingBag,
  team: UsersRound,
  website: Globe,
  app: AppWindow,
};

/** "28 Oct": the date chip's short form; the full date is the `<time>`'s own value and title. */
function shortDate(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
}

/**
 * /changelog (C-156): shipped features by month, from lib/marketing/changelog.ts. C-159: a vertical
 * timeline; each month's heading sits on the line, each entry is a card with its date, its area and
 * Meta's approval where it applies. The cards rise in as they scroll into view (site.css).
 */
export default function ChangelogPage() {
  const months = changelogByMonth();
  return (
    <InfoPage
      name="What's new"
      path={PATH}
      className="changelog"
      eyebrow="Changelog"
      title="What's new"
      lede={`What has shipped in ${SITE_NAME}, newest first. A feature that still waits on Meta's approval says so.`}
      footer={
        <p>
          Something you&apos;d like to see? Write to <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>.
        </p>
      }
    >
      <div className="wrap">
        <div className="tl">
          {months.map((month) => (
            <section key={month.id} id={month.id} aria-labelledby={`${month.id}-title`} className="tl-month">
              <h2 id={`${month.id}-title`} className="tl-m">
                {month.month}
              </h2>
              {/* Articles, not a list: each entry is a card with its own heading. */}
              <div className="tl-list">
                {month.entries.map((entry) => (
                  <article key={`${entry.date}-${entry.title}`} className="tl-card">
                    <p className="tl-meta">
                      <time dateTime={entry.date} title={legalDate(entry.date) ?? entry.date} className="tl-date">
                        <span aria-hidden>{shortDate(entry.date)}</span>
                        <span className="sr-only">{legalDate(entry.date) ?? entry.date}</span>
                      </time>
                      <span className="tl-area">
                        <Ico icon={AREA_ICONS[entry.area]} className={entry.area === "ai" ? "ico-ai" : undefined} />
                        {CHANGELOG_AREAS[entry.area]}
                      </span>
                      {entry.status ? <span className="tag t-need">{entry.status}</span> : null}
                    </p>
                    <h3>{entry.title}</h3>
                    <p className="tl-body">{entry.body}</p>
                  </article>
                ))}
              </div>
            </section>
          ))}
        </div>
      </div>
    </InfoPage>
  );
}
