import type { Route } from "next";
import type { ReactNode } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import type { Overview } from "@/lib/api/types";

import {
  countTrend,
  DASH,
  formatCount,
  formatPercent,
  formatWait,
  RANGE_LABEL,
  rateTrend,
  waitTrend,
} from "./format";
import { MetricTile, TrendChip } from "./MetricTile";

type Props = {
  overview: Overview;
  slug: string;
  /** No account connected yet: every tile shows "—" and how it gets a value. */
  connected: boolean;
};

/**
 * UX-SCR-01's metric row: Needs reply (to that inbox view), Messages today, Handled by AI and
 * Median first response over the range, each compared with the period before it.
 */
export function MetricTiles({ overview, slug, connected }: Props) {
  const { current, previous, range } = overview;
  const days = RANGE_LABEL[range];
  const inboxHref = `/w/${slug}/inbox?view=needs_reply` as Route;

  if (!connected) {
    return (
      <Row>
        <MetricTile label="Needs reply" value={DASH} hint="Conversations waiting for you." />
        <MetricTile label="Messages today" value={DASH} hint="Counted once an account is connected." />
        <MetricTile label={`Handled by AI, ${days}`} value={DASH} hint="Share of conversations the AI answered." />
        <MetricTile label={`Median first response, ${days}`} value={DASH} hint="How fast customers hear back." />
      </Row>
    );
  }

  const received = countTrend(current.messages_received, previous.messages_received, range);
  const replied = current.conversations_replied;
  return (
    <Row>
      <MetricTile
        label="Needs reply"
        value={formatCount(overview.needs_reply)}
        href={inboxHref}
        hint={
          overview.needs_you > 0 ? (
            <span className="font-medium text-danger-fg">
              {formatCount(overview.needs_you)} {overview.needs_you === 1 ? "needs" : "need"} you
            </span>
          ) : (
            "Conversations waiting for a reply."
          )
        }
      />
      <MetricTile
        label="Messages today"
        value={formatCount(overview.messages_today)}
        hint={
          <span className="inline-flex flex-wrap items-center gap-x-1.5">
            <span>
              {formatCount(current.messages_received)} in {days}
            </span>
            {received ? <TrendChip trend={received} /> : null}
          </span>
        }
      />
      <MetricTile
        label={`Handled by AI, ${days}`}
        value={formatPercent(current.handled_by_ai_rate)}
        trend={rateTrend(current.handled_by_ai_rate, previous.handled_by_ai_rate, range, "neither")}
        hint={
          replied > 0
            ? `${formatCount(current.handled_by_ai)} of ${formatCount(replied)} replied ${replied === 1 ? "conversation" : "conversations"}`
            : `No replies in the last ${days} yet.`
        }
      />
      <MetricTile
        label={`Median first response, ${days}`}
        value={formatWait(current.median_first_response_s)}
        trend={waitTrend(current.median_first_response_s, previous.median_first_response_s, range)}
        hint={
          current.first_responses > 0
            ? `Across ${formatCount(current.first_responses)} first ${current.first_responses === 1 ? "reply" : "replies"}`
            : `No answered messages in the last ${days} yet.`
        }
      />
    </Row>
  );
}

function Row({ children }: { children: ReactNode }) {
  return (
    <section aria-label="Key numbers" className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2 lg:grid-cols-4">
      {children}
    </section>
  );
}

export function MetricTilesSkeleton() {
  return (
    <div aria-hidden className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2 lg:grid-cols-4">
      {[0, 1, 2, 3].map((i) => (
        <Skeleton key={i} className="h-[108px] rounded-xl bg-panel" />
      ))}
    </div>
  );
}
