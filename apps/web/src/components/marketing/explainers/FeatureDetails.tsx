import { ArrowRight } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { Callout } from "@/components/site/Callout";
import { TocNav } from "@/components/site/TocNav";
import { PLAN_NAME } from "@/lib/copy";
import type { PlanCard, Pricing } from "@/lib/marketing/plans";

import { Ico } from "../landing/Ico";
import { CellChip } from "./BentoGrid";
import { DETAILS } from "./content";

/**
 * A plan's state today, from the plans API only (as /ai-info): never a price written into the page.
 * Without the API (the fallback list) only Free's state is said.
 */
export function planState(card: PlanCard | undefined): string {
  if (!card) return "isn't available yet";
  if (card.plan === "free") return "is available now, with no card needed";
  return card.available ? "is on sale now" : "is coming soon";
}

/**
 * "In detail" on /features (C-160): each feature group with a fuller explanation, its specifics and its
 * limits on each plan (plan-table.json, the API's table), beside a sticky side nav on a wide screen
 * (the current group marked by toc-spy). Plan states come from the plans API.
 */
export function FeatureDetails({ pricing }: { pricing: Pricing }) {
  const card = (plan: "free" | "pro" | "max") => pricing.plans.find((item) => item.plan === plan);
  return (
    <section className="band xp-detail-band" aria-labelledby="detail-title">
      <div className="wrap">
        <div className="xp-detail-head">
          <h2 id="detail-title" className="h2-sm">
            In detail
          </h2>
          <Callout tone="info" className="xp-plans-note">
            <p>
              Limits for each plan come from the same table as the pricing page. {PLAN_NAME.free} {planState(card("free"))}
              {pricing.source === "api" ? (
                <>
                  ; {PLAN_NAME.pro} {planState(card("pro"))}; {PLAN_NAME.max} {planState(card("max"))}
                </>
              ) : null}
              . See <Link href="/pricing">pricing</Link> for every limit.
            </p>
          </Callout>
        </div>
        <div className="xp-detail">
          <aside className="xp-track">
            <TocNav items={DETAILS.map((group) => ({ id: group.id, label: group.title }))} label="Feature groups" />
          </aside>
          <div className="xp-groups">
            {DETAILS.map((group) => (
              <section key={group.id} id={group.id} aria-labelledby={`${group.id}-title`} className="xp-group" data-rise="">
                <h3 id={`${group.id}-title`} className="xp-group-h">
                  <Ico icon={group.icon} className={group.ai ? "ico-ai" : undefined} />
                  <span>{group.title}</span>
                  {group.status ? <CellChip status={group.status} /> : null}
                </h3>
                <p className="xp-group-p">{group.body}</p>
                <ul className="xp-points">
                  {group.points.map((point) => (
                    <li key={point}>{point}</li>
                  ))}
                </ul>
                {group.limits?.length ? (
                  <div className="xp-lim-box">
                    <table className="xp-lim">
                      <caption className="sr-only">{group.title}: limits on each plan</caption>
                      <thead>
                        <tr>
                          <th scope="col">Limit</th>
                          <th scope="col">{PLAN_NAME.free}</th>
                          <th scope="col">{PLAN_NAME.pro}</th>
                          <th scope="col">{PLAN_NAME.max}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {group.limits.map((row) => (
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
                ) : null}
                {group.links?.length ? (
                  <p className="xp-more">
                    {group.links.map((link) => (
                      <Link key={link.href} href={link.href as Route} className="tlink">
                        {link.label}
                        <ArrowRight className="size-4" aria-hidden />
                      </Link>
                    ))}
                  </p>
                ) : null}
              </section>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
