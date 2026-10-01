import type { Metadata } from "next";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import {
  EYEBROW,
  META,
  PAGE_TITLE,
  breakpoints,
  colorTokens,
  easings,
  fontSizes,
  gradientUtilities,
  motionDurations,
  otherUtilities,
  shadcnAliases,
  typeRoles,
} from "@/styles/tokens";

export const metadata: Metadata = { title: "Design tokens" };

const CARD = "rounded-xl border border-line bg-panel";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className={EYEBROW}>{title}</h2>
      {children}
    </section>
  );
}

/** One row of a name, its value and its use, for the lists below. */
function Row({ name, value, use }: { name: string; value: string; use: string }) {
  return (
    <li className="flex flex-col gap-0.5 px-4 py-3 md:flex-row md:gap-4">
      <code className="text-sm font-medium md:w-48 md:shrink-0">{name}</code>
      <span className="min-w-0">
        <span className="block font-mono text-xs break-words text-fg-secondary">{value}</span>
        <span className="block text-xs text-fg-secondary">{use}</span>
      </span>
    </li>
  );
}

/**
 * Development-only reference of every token in §4.2 and the UI audit's design system (T0.6,
 * UI-001). Not available in production.
 */
export default function TokensPage() {
  if (process.env.NODE_ENV === "production") notFound();

  return (
    <main className="mx-auto max-w-5xl space-y-10 p-4 md:p-6">
      <header className="space-y-1">
        <h1 className={PAGE_TITLE}>Design tokens</h1>
        <p className="text-sm text-fg-secondary">
          Rendered from <code>src/styles/tokens.ts</code>; a test checks <code>globals.css</code> against the same
          lists. The rules are in <code>docs/ui-audit/DESIGN_SYSTEM.md</code>.
        </p>
      </header>

      <Section title="Colours">
        <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {colorTokens.map((token) => (
            <li key={token.name} className={`${CARD} flex items-center gap-3 p-3`}>
              <span className={`${token.swatch} size-10 shrink-0 rounded-lg border border-line-strong`} aria-hidden />
              <span className="min-w-0 text-sm">
                <span className="block font-medium">{token.name}</span>
                <span className="block font-mono text-xs tabular-nums text-fg-secondary">{token.value}</span>
                <span className="block truncate text-xs text-fg-secondary">{token.use}</span>
              </span>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="shadcn aliases">
        <p className={META}>Inside components/ui only; app code uses the tokens.</p>
        <ul className={`${CARD} grid grid-cols-1 gap-x-6 p-4 text-sm sm:grid-cols-2 lg:grid-cols-3`}>
          {shadcnAliases.map(({ alias, token }) => (
            <li key={alias} className="flex justify-between gap-3 py-1">
              <code>--{alias}</code>
              <code className="text-fg-secondary">{token}</code>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Gradients">
        <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {gradientUtilities.map((g) => (
            <li key={g.name} className={`${CARD} p-3`}>
              <span className={`${g.name} block h-12 rounded-lg`} aria-hidden />
              <span className="mt-2 block text-sm font-medium">{g.name}</span>
              <span className="block font-mono text-xs break-words text-fg-secondary">{g.value}</span>
              <span className="block text-xs text-fg-secondary">{g.use}</span>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Type roles">
        <ul className={`${CARD} divide-y divide-line-subtle`}>
          {typeRoles.map((t) => (
            <li key={t.name} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 px-4 py-3">
              <span className={t.className}>{t.role}</span>
              <code className="text-xs text-fg-secondary">
                {t.name}: {t.className}
              </code>
            </li>
          ))}
        </ul>
        <ul className={`${CARD} divide-y divide-line-subtle`}>
          {fontSizes.map((f) => (
            <Row key={f.name} name={f.name} value={`${f.size} / ${f.lineHeight} (${f.px} px)`} use={f.use} />
          ))}
        </ul>
      </Section>

      <Section title="Motion">
        <ul className={`${CARD} divide-y divide-line-subtle`}>
          {motionDurations.map((d) => (
            <Row key={d.name} name={d.name} value={`${d.variable}: ${d.value}`} use={d.use} />
          ))}
          {easings.map((e) => (
            <Row key={e.name} name={e.name} value={e.value} use={e.use} />
          ))}
        </ul>
        <p className={META}>Under reduced motion, overlays, their scrims and skeletons appear and leave at once.</p>
      </Section>

      <Section title="Breakpoints">
        <ul className={`${CARD} divide-y divide-line-subtle`}>
          {breakpoints.map((b) => (
            <Row key={b.name} name={`${b.name}:`} value={`${b.value} (${b.px} px)${b.custom ? ", added" : ""}`} use={b.use} />
          ))}
        </ul>
      </Section>

      <Section title="Utilities">
        <ul className={`${CARD} divide-y divide-line-subtle`}>
          {otherUtilities.map((u) => (
            <Row key={u.name} name={u.name} value={u.value} use={u.use} />
          ))}
        </ul>
        <div
          role="group"
          aria-label="mask-fade-x example"
          tabIndex={0}
          className="mask-fade-x flex gap-2 overflow-x-auto pe-4 [scrollbar-width:none]"
        >
          {["All", "Unread", "Needs reply", "Leads", "AI handled", "Instagram", "WhatsApp", "Archived", "More"].map((label) => (
            <span key={label} className="shrink-0 rounded-full border border-line bg-panel px-3 py-1 text-sm">
              {label}
            </span>
          ))}
        </div>
      </Section>
    </main>
  );
}
