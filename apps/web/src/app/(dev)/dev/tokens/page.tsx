import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { colorTokens, gradientUtilities, typeRoles } from "@/styles/tokens";

export const metadata: Metadata = { title: "Design tokens" };

/** Development-only reference of every token in §4.2 (T0.6). Not available in production. */
export default function TokensPage() {
  if (process.env.NODE_ENV === "production") notFound();

  return (
    <main className="mx-auto max-w-5xl space-y-10 p-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Design tokens</h1>
        <p className="text-sm text-fg-secondary">
          Rendered from <code>src/styles/tokens.ts</code>; a test checks <code>globals.css</code>{" "}
          against the same list.
        </p>
      </header>

      <section className="space-y-3">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-fg-secondary">
          Colours
        </h2>
        <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {colorTokens.map((token) => (
            <li key={token.name} className="flex items-center gap-3 rounded-xl border border-line bg-panel p-3">
              <span
                className={`${token.swatch} size-10 shrink-0 rounded-lg border border-line-strong`}
                aria-hidden
              />
              <span className="min-w-0 text-sm">
                <span className="block font-medium">{token.name}</span>
                <span className="block font-mono text-xs tabular-nums text-fg-secondary">{token.value}</span>
                <span className="block truncate text-xs text-fg-secondary">{token.use}</span>
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-fg-secondary">
          Gradients
        </h2>
        <ul className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {gradientUtilities.map((g) => (
            <li key={g.name} className="rounded-xl border border-line bg-panel p-3">
              <span className={`${g.name} block h-12 rounded-lg`} aria-hidden />
              <span className="mt-2 block text-sm font-medium">{g.name}</span>
              <span className="block font-mono text-xs text-fg-secondary">{g.value}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-fg-secondary">Type</h2>
        <ul className="space-y-2 rounded-xl border border-line bg-panel p-4">
          {typeRoles.map((t) => (
            <li key={t.role} className="flex items-baseline justify-between gap-4">
              <span className={t.className}>{t.role}</span>
              <code className="text-xs text-fg-secondary">{t.className}</code>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
