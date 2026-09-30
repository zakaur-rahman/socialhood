import { INTENT_LABEL } from "@/lib/ai/format";
import type { Overview } from "@/lib/api/types";

import { formatCount, RANGE_LABEL, type OverviewRange } from "./format";

/** What customers wrote about most in the range (analysed messages; "other" and spam left out). */
export function TopIntentsCard({ intents, range }: { intents: Overview["top_intents"]; range: OverviewRange }) {
  const days = RANGE_LABEL[range];
  const most = Math.max(1, ...intents.map((item) => item.count));
  return (
    <section aria-labelledby="home-intents" className="rounded-xl border border-line bg-panel p-4">
      <h2 id="home-intents" className="mb-3 text-base font-semibold">
        What customers asked about, {days}
      </h2>
      {intents.length === 0 ? (
        <p className="text-sm text-fg-secondary">Topics appear once the AI has read messages from the last {days}.</p>
      ) : (
        <ol className="space-y-2.5">
          {intents.map((item) => (
            <li key={item.intent} data-testid="top-intent" className="space-y-1">
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span>{INTENT_LABEL[item.intent]}</span>
                <span className="text-xs text-fg-secondary tabular-nums">
                  {formatCount(item.count)} {item.count === 1 ? "message" : "messages"}
                </span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-raised" aria-hidden>
                <div className="bg-brand-gradient-decor h-full rounded-full" style={{ width: `${(item.count / most) * 100}%` }} />
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
