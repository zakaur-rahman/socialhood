import { HelpCircle, Sparkles } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { Button, buttonVariants } from "@/components/ui/button";
import type { OverviewGap } from "@/lib/api/types";
import { cn } from "@/lib/utils";

/**
 * UX-SCR-01 / FR-KB-06, only while questions are open: "{n} questions the AI couldn't answer",
 * the most asked ones, and the one asked most recently. View thread opens the conversation it came
 * from; Train AI (admins, who manage knowledge) opens Add to knowledge with the customer's
 * question, and saving answers the gap (components/home/HomeScreen, lib/knowledge/prefill).
 */
export function KnowledgeGapBanner({
  count,
  topics,
  latest,
  slug,
  canManage,
  onTrain,
}: {
  count: number;
  topics: string[];
  latest: OverviewGap | null;
  slug: string;
  canManage: boolean;
  onTrain: (gap: OverviewGap) => void;
}) {
  if (count <= 0) return null;
  const action = "min-h-10 md:min-h-8";
  return (
    <section
      aria-labelledby="home-gaps"
      data-testid="gap-banner"
      className="flex flex-col gap-4 rounded-xl border border-warning/40 bg-panel p-4 sm:flex-row sm:items-center"
    >
      <span className="grid size-10 shrink-0 place-items-center rounded-full bg-warning/15" aria-hidden>
        <HelpCircle className="size-5 text-warning" />
      </span>
      <div className="min-w-0 flex-1 space-y-0.5">
        <h2 id="home-gaps" className="text-sm font-semibold">
          <span className="tabular-nums">{count}</span>{" "}
          {count === 1 ? "question the AI couldn't answer" : "questions the AI couldn't answer"}
        </h2>
        {topics.length > 0 ? (
          <p className="truncate text-xs text-fg-secondary" data-testid="gap-topics">
            Most asked: <span className="text-fg">{topics.join(" · ")}</span>
          </p>
        ) : null}
        {latest ? (
          <p className="truncate text-xs text-fg-secondary" data-testid="gap-latest">
            Latest: “{latest.question}”
          </p>
        ) : null}
      </div>
      <div className="flex flex-wrap gap-2">
        {latest?.conversation_id ? (
          <Link
            href={`/w/${slug}/inbox/${latest.conversation_id}` as Route}
            className={cn(buttonVariants({ variant: "outline" }), action)}
          >
            View thread
          </Link>
        ) : null}
        {canManage && latest ? (
          <Button className={cn("bg-brand-gradient text-white", action)} onClick={() => onTrain(latest)}>
            <Sparkles aria-hidden /> Train AI
          </Button>
        ) : null}
        {canManage && !latest ? (
          <Link href={`/w/${slug}/knowledge` as Route} className={cn(buttonVariants({ variant: "outline" }), action)}>
            Open Knowledge
          </Link>
        ) : null}
      </div>
    </section>
  );
}
