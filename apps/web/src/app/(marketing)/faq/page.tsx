import { FaqMotion } from "@/components/marketing/FaqMotion";
import { BreadcrumbJsonLd, JsonLd } from "@/components/marketing/JsonLd";
import { Ico } from "@/components/marketing/landing/Ico";
import { FAQ_GROUP_ICONS } from "@/components/marketing/page-icons";
import { SUPPORT_EMAIL } from "@/lib/copy";
import { FAQ_ALL, FAQ_GROUPS, FAQ_PATH } from "@/lib/marketing/faq";
import { faqPageJsonLd, pageMetadata } from "@/lib/marketing/seo";
import { SITE_NAME, absoluteUrl, siteUrl } from "@/lib/marketing/site";

export const metadata = pageMetadata({
  title: "Common questions",
  description: `Answers about ${SITE_NAME}'s AI replies, Instagram and WhatsApp, plans, AI credits and support, in one place.`,
  path: FAQ_PATH,
});

/**
 * Every question the site answers (C-157), grouped, as native disclosures. The landing page shows the
 * eight most asked and links here. The FAQPage JSON-LD lists the same questions, in the same order and
 * words, from lib/marketing/faq.ts.
 *
 * C-159 look: one band, the groups in a sticky nav on a wide screen (plain anchors, no script), each
 * group headed by its icon, the questions as the landing's C-157 accordion (FaqMotion).
 */
export default function FaqPage() {
  const origin = siteUrl();
  return (
    <main id="main" tabIndex={-1} className="pp flex-1 outline-none">
      <BreadcrumbJsonLd name="Common questions" path={FAQ_PATH} />
      <JsonLd data={{ "@context": "https://schema.org", ...faqPageJsonLd(FAQ_ALL, origin, `${absoluteUrl(FAQ_PATH, origin)}#faq`) }} />
      <section className="page-head">
        <div className="wrap">
          <h1 className="h-page">Common questions</h1>
          <p className="lede">
            Short answers about the AI, Instagram and WhatsApp, the plans and the app. Something missing? Write to{" "}
            <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>.
          </p>
        </div>
      </section>
      <div className="band faq-sec faqp-band">
        <div className="wrap faqp">
          <nav className="faqp-nav" aria-label="Question groups">
            <ul>
              {FAQ_GROUPS.map((group) => {
                const icon = FAQ_GROUP_ICONS[group.id];
                return (
                  <li key={group.id}>
                    <a href={`#${group.id}`}>
                      {icon ? <Ico icon={icon} /> : null}
                      <span>{group.title}</span>
                      <span className="faqp-n num">{group.items.length}</span>
                    </a>
                  </li>
                );
              })}
            </ul>
          </nav>
          <div className="faqp-groups">
            {FAQ_GROUPS.map((group) => {
              const icon = FAQ_GROUP_ICONS[group.id];
              return (
                <section key={group.id} className="faqp-group scroll-mt-24" id={group.id} aria-labelledby={`${group.id}-title`}>
                  <h2 id={`${group.id}-title`} className="faqp-h">
                    {icon ? <Ico icon={icon} /> : null}
                    {group.title}
                  </h2>
                  <div className="faq-list">
                    {group.items.map((item) => (
                      <details key={item.question} className="qa">
                        <summary>
                          <h3>{item.question}</h3>
                          <span className="pm" aria-hidden>
                            <i />
                            <i />
                          </span>
                        </summary>
                        <p>{item.answer}</p>
                      </details>
                    ))}
                  </div>
                </section>
              );
            })}
          </div>
        </div>
      </div>
      <FaqMotion />
    </main>
  );
}
