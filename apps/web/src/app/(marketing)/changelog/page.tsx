import { InfoPage } from "@/components/marketing/InfoPage";
import { SUPPORT_EMAIL } from "@/lib/copy";
import { legalDate } from "@/lib/legal";
import { CHANGELOG_PATH, changelogByMonth } from "@/lib/marketing/changelog";
import { pageMetadata } from "@/lib/marketing/seo";
import { SITE_NAME } from "@/lib/marketing/site";

const PATH = CHANGELOG_PATH;

export const metadata = pageMetadata({
  title: "What's new",
  description: `What has shipped in ${SITE_NAME}, month by month: new features for the inbox, the AI, automations and publishing, with their dates.`,
  path: PATH,
});

/** /changelog (C-156): shipped features by month, from lib/marketing/changelog.ts. */
export default function ChangelogPage() {
  const months = changelogByMonth();
  return (
    <InfoPage
      name="What's new"
      path={PATH}
      eyebrow="Changelog"
      title="What's new"
      lede={`What has shipped in ${SITE_NAME}, newest first. A feature that still waits on Meta's approval says so.`}
      footer={
        <p>
          Something you&apos;d like to see? Write to <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>.
        </p>
      }
    >
      {months.map((month) => (
        <section key={month.id} id={month.id} aria-labelledby={`${month.id}-title`}>
          <h2 id={`${month.id}-title`}>{month.month}</h2>
          {/* Articles, not a list: the reading column styles lists with bullets. */}
          {month.entries.map((entry) => (
            <article key={`${entry.date}-${entry.title}`}>
              <h3>{entry.title}</h3>
              <p className="text-sm">
                  <time dateTime={entry.date}>{legalDate(entry.date) ?? entry.date}</time>
                  {entry.status ? <span className="tag t-need ml-2">{entry.status}</span> : null}
                </p>
              <p>{entry.body}</p>
            </article>
          ))}
        </section>
      ))}
    </InfoPage>
  );
}
