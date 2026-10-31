import { ArrowRight, Clapperboard, Coins, Store } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { StatusChip } from "@/components/site/StatusChip";
import { TocNav, type TocItem } from "@/components/site/TocNav";
import { PLAN_NAME } from "@/lib/copy";
import type { FeatureDepth, GtmPage } from "@/lib/marketing/gtm-pages";
import { SITE_NAME } from "@/lib/marketing/site";

import { Faq } from "./Faq";
import { FeatureSceneView } from "./feature-scenes";
import { Ico } from "./landing/Ico";

/** The ids of a feature page's deeper sections (C-163). */
export const FEATURE_IDS = {
  what: "what-it-does",
  how: "how-it-works",
  plans: "plans-and-credits",
  notYet: "not-yet",
  who: "who-its-for",
  faq: "faq",
} as const;

/** The feature page's sections in page order, for the "On this page" bar. */
export function featureToc(page: GtmPage): TocItem[] {
  return [
    { id: FEATURE_IDS.what, label: "What it does" },
    ...page.blocks.map((block) => ({ id: block.id, label: block.title })),
    { id: FEATURE_IDS.how, label: "How it works" },
    { id: FEATURE_IDS.plans, label: "Plans and credits" },
    { id: FEATURE_IDS.notYet, label: "Not yet" },
    { id: FEATURE_IDS.who, label: "Who it's for" },
    { id: FEATURE_IDS.faq, label: "Questions" },
  ];
}

/** "The AI inbox" → "the AI inbox": a name inside a sentence. */
const inSentence = (name: string) => name.charAt(0).toLowerCase() + name.slice(1);

const creditWords = (n: number) => (n === 0 ? "No credits" : `${n} ${n === 1 ? "credit" : "credits"}`);

/**
 * The top of a feature page's depth (C-163): the "On this page" bar (sticky under the header on a wide
 * screen, a scrolling row on a phone; toc-spy marks the section being read), then "What it does" as
 * prose beside the page's product scene.
 */
export function FeatureIntro({ page, feature }: { page: GtmPage; feature: FeatureDepth }) {
  return (
    <>
      <div className="fp-bar">
        <div className="wrap">
          <TocNav items={featureToc(page)} className="fp-jump" />
        </div>
      </div>
      <section id={FEATURE_IDS.what} aria-labelledby="what-title" className="band fp-sec">
        <div className="wrap fp-what">
          <div>
            <h2 id="what-title" className="h-sec">
              What it does
            </h2>
            {feature.whatItDoes.paragraphs.map((paragraph) => (
              <p key={paragraph} className="fp-p">
                {paragraph}
              </p>
            ))}
          </div>
          <FeatureSceneView scene={feature.whatItDoes.scene} />
        </div>
      </section>
    </>
  );
}

/**
 * The rest of a feature page's depth (C-163), after its cards: how it works as an ordered line of
 * steps, the plan limits (plan-table.json) beside the credit costs, what it doesn't do yet with each
 * status chip, who it's for (linking the two audience pages) and the page's own questions.
 */
export function FeatureDetail({ page, feature }: { page: GtmPage; feature: FeatureDepth }) {
  return (
    <>
      <section id={FEATURE_IDS.how} aria-labelledby="how-title" className="band fp-sec fp-how-band">
        <div className="wrap">
          <h2 id="how-title" className="h-sec">
            How it works
          </h2>
          <ol className="fp-steps after-head">
            {feature.steps.map((step) => (
              <li key={step.title} data-rise="">
                <h3>{step.title}</h3>
                <p>{step.body}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section id={FEATURE_IDS.plans} aria-labelledby="plans-title" className="band fp-sec">
        <div className="wrap">
          <div className="split-head">
            <h2 id="plans-title" className="h-sec">
              Plans and credits
            </h2>
            <p className="lede">
              The limits come from the same table as the <Link href="/pricing">pricing page</Link>, and AI features use credits from your
              monthly allowance.
            </p>
          </div>
          <div className="fp-plans after-head">
            <div className="xp-lim-box">
              <table className="xp-lim">
                <caption className="sr-only">
                  {page.name}: limits on each plan
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Limit</th>
                    <th scope="col">{PLAN_NAME.free}</th>
                    <th scope="col">{PLAN_NAME.pro}</th>
                    <th scope="col">{PLAN_NAME.max}</th>
                  </tr>
                </thead>
                <tbody>
                  {feature.limits.map((row) => (
                    <tr key={row.label}>
                      <th scope="row">{row.label}</th>
                      <td className="num">{row.free}</td>
                      <td className="num">{row.pro}</td>
                      <td className="num">{row.max}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="fp-credits">
              <h3>
                <Ico icon={Coins} />
                <span>AI credits</span>
              </h3>
              <dl>
                {feature.credits.map((row) => (
                  <div key={row.label}>
                    <dt>{row.label}</dt>
                    <dd>
                      <b className="num">{creditWords(row.credits)}</b>
                      {row.per ? <span> {row.per}</span> : null}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>
        </div>
      </section>

      <section id={FEATURE_IDS.notYet} aria-labelledby="not-yet-title" className="band fp-sec">
        <div className="wrap">
          <div className="split-head">
            <h2 id="not-yet-title" className="h-sec">
              What it doesn&apos;t do yet
            </h2>
            <p className="lede">Said plainly, so you can decide. A feature that waits on Meta says so.</p>
          </div>
          <ul className="fp-notyet after-head">
            {feature.notYet.map((item) => (
              <li key={item.title} data-rise="">
                <h3>{item.title}</h3>
                <StatusChip status={item.status} />
                <p>{item.body}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section id={FEATURE_IDS.who} aria-labelledby="who-title" className="band fp-sec">
        <div className="wrap">
          <h2 id="who-title" className="h-sec">
            Who it&apos;s for
          </h2>
          <ul className="fp-aud after-head">
            <li data-rise="">
              <h3>
                <Ico icon={Clapperboard} />
                <span>Creators</span>
              </h3>
              <p>{feature.audience.creators}</p>
              <Link href={"/for-creators" as Route} className="tlink">
                {SITE_NAME} for creators
                <ArrowRight className="size-4" aria-hidden />
              </Link>
            </li>
            <li data-rise="">
              <h3>
                <Ico icon={Store} />
                <span>Businesses</span>
              </h3>
              <p>{feature.audience.businesses}</p>
              <Link href={"/for-businesses" as Route} className="tlink">
                {SITE_NAME} for businesses
                <ArrowRight className="size-4" aria-hidden />
              </Link>
            </li>
          </ul>
        </div>
      </section>

      <Faq
        items={feature.faq}
        id={FEATURE_IDS.faq}
        title={`Questions about ${inSentence(page.name)}`}
        lede={`Answers about ${inSentence(page.name)} in particular.`}
        allLink
      />
    </>
  );
}
