import type { CSSProperties } from "react";

import table from "@/lib/marketing/plan-table.json";

import { Container } from "./primitives";

const number = new Intl.NumberFormat("en-IN");

/** The Free plan's allowances come from plan-table.json (the API's plan table), never typed here. */
export const FREE = {
  aiCredits: table.entitlements.ai_credits_monthly.free,
  automations: table.entitlements.active_automations.free,
};

/**
 * A few plain facts about the product, in big type (C-138). Only things that are true by
 * construction: what is built, and what the Free plan includes. No customer counts, no speed or
 * setup-time claims we can't back.
 */
export const STATS: { value: string; label: string }[] = [
  { value: "1", label: "inbox for Instagram, WhatsApp and your website chat" },
  { value: "3", label: "languages the AI replies in: English, Hindi and Hinglish" },
  { value: number.format(FREE.aiCredits), label: "AI credits every month on the Free plan" },
  { value: number.format(FREE.automations), label: "comment and DM automations on the Free plan" },
];

export function Stats() {
  return (
    <section aria-label="The product in numbers" className="border-t border-line-subtle bg-panel-glass py-14 sm:py-16">
      <Container>
        <ul className="mx-auto grid max-w-5xl grid-cols-2 gap-x-6 gap-y-10 lg:grid-cols-4">
          {STATS.map((stat, index) => (
            <li key={stat.label} data-reveal style={{ "--reveal-delay": `${index * 80}ms` } as CSSProperties} className="text-center">
              <span className="block text-5xl font-semibold tracking-tight text-brand-fg tabular-nums sm:text-6xl">{stat.value}</span>
              <span className="mx-auto mt-3 block max-w-[16rem] text-sm leading-relaxed text-fg-secondary">{stat.label}</span>
            </li>
          ))}
        </ul>
      </Container>
    </section>
  );
}
