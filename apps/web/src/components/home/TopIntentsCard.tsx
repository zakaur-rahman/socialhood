import { INTENT_LABEL } from "@/lib/ai/format";
import type { Overview } from "@/lib/api/types";

import { formatCount } from "./format";

/** What customers wrote about most in the range (analysed messages; "other" and spam left out),
 * with how many messages these topics add up to. */
export function TopIntentsCard({
  intents,
  period,
  within,
}: {
  intents: Overview["top_intents"];
  period: string;
  within: string;
}) {
  const most = Math.max(1, ...intents.map((item) => item.count));
  const total = intents.reduce((sum, item) => sum + item.count, 0);
  return (
    <section aria-labelledby="home-intents" className="flex flex-col rounded-xl border border-line bg-panel p-4">
      <h2 id="home-intents" className="mb-3 text-base font-semibold">
        What customers asked about, {period}
      </h2>
      {intents.length === 0 ? (
        <p className="text-sm text-fg-secondary">Topics appear once the AI has read messages from {within}.</p>
      ) : (
        <>
          <ol className="mb-4 space-y-3">
            {intents.map((item) => (
              <li key={item.intent} data-testid="top-intent" className="space-y-1.5">
                <div className="flex items-baseline justify-between gap-3 text-sm">
                  <span className="font-medium">{INTENT_LABEL[item.intent]}</span>
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
          <p data-testid="intents-total" className="mt-auto border-t border-line-subtle pt-3 text-xs text-fg-secondary">
            <span className="font-medium text-fg tabular-nums">{formatCount(total)}</span>{" "}
            {total === 1 ? "message" : "messages"} in these topics
          </p>
        </>
      )}
    </section>
  );
}
