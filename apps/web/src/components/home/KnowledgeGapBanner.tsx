import { HelpCircle, Sparkles } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/ui/alert";
import type { OverviewGap } from "@/lib/api/types";

/**
 * UX-SCR-01 / FR-KB-06, only while questions are open: "{n} questions the AI couldn't answer",
 * the most asked ones, and the one asked most recently. View thread opens the conversation it came
 * from; Train AI (admins, who manage knowledge) opens Add to knowledge with the customer's
 * question, and saving answers the gap (components/home/HomeScreen, lib/knowledge/prefill).
 * An Alert with the warning edge; its actions are the Alert's secondary buttons.
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
  return (
    <Alert
      tone="warning"
      variant="outline"
      aria-labelledby="home-gaps"
      data-testid="gap-banner"
      icon={<HelpCircle />}
      action={
        <div className="flex flex-wrap gap-2">
          {latest?.conversation_id ? (
            <AlertAction asChild>
              <Link href={`/w/${slug}/inbox/${latest.conversation_id}` as Route}>Open conversation</Link>
            </AlertAction>
          ) : null}
          {canManage && latest ? (
            <AlertAction onClick={() => onTrain(latest)}>
              <Sparkles aria-hidden /> Add answer
            </AlertAction>
          ) : null}
          {canManage && !latest ? (
            <AlertAction asChild>
              <Link href={`/w/${slug}/knowledge` as Route}>Open Knowledge</Link>
            </AlertAction>
          ) : null}
        </div>
      }
    >
      <AlertTitle>
        <h2 id="home-gaps">
          <span className="tabular-nums">{count}</span>{" "}
          {count === 1 ? "question the AI couldn't answer" : "questions the AI couldn't answer"}
        </h2>
      </AlertTitle>
      {topics.length > 0 ? (
        <AlertDescription className="truncate text-xs" data-testid="gap-topics">
          Most asked: <span className="text-fg">{topics.join(" · ")}</span>
        </AlertDescription>
      ) : null}
      {latest ? (
        <AlertDescription className="truncate text-xs" data-testid="gap-latest">
          Latest: “{latest.question}”
        </AlertDescription>
      ) : null}
    </Alert>
  );
}
