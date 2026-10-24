import { assignColours, seriesStyle } from "@/components/charts/palette";
import { Card, CardTitle } from "@/components/ui/card";
import { INTENT_LABEL } from "@/lib/ai/format";
import type { Overview } from "@/lib/api/types";
import { cn } from "@/lib/utils";

import { formatCount } from "./format";

/** What customers wrote about most in the range (analysed messages; "other" and spam left out),
 * with how many messages these topics add up to. The bars are a chart on tokens, not Progress. */
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
  // A topic keeps its hue from range to range (the order of INTENT_LABEL); two shown never share one.
  const colours = assignColours(
    intents.map((item) => item.intent),
    Object.keys(INTENT_LABEL),
  );
  return (
    <Card asChild className="flex flex-col">
      <section aria-labelledby="home-intents">
        <CardTitle id="home-intents" className="mb-3">
          What customers asked about, {period}
        </CardTitle>
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
                    <div className={cn("h-full rounded-full", seriesStyle(colours.get(item.intent) ?? 0).bg)} style={{ width: `${(item.count / most) * 100}%` }} />
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
    </Card>
  );
}
