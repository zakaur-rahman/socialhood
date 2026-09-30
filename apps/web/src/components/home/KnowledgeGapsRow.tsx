import { ChevronRight, HelpCircle } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

/**
 * UX-SCR-01 / FR-KB-06: "{n} questions the AI couldn't answer", linking to Knowledge, with the
 * most asked ones below. Hidden at 0.
 */
export function KnowledgeGapsRow({ count, slug, topics = [] }: { count: number; slug: string; topics?: string[] }) {
  if (count <= 0) return null;
  return (
    <Link
      href={`/w/${slug}/knowledge` as Route}
      className="flex items-center gap-3 rounded-xl border border-line bg-panel p-4 outline-none hover:bg-white/5 focus-visible:ring-3 focus-visible:ring-ring/50"
    >
      <HelpCircle className="size-5 shrink-0 text-warning" aria-hidden />
      <span className="min-w-0 flex-1 text-sm">
        <span className="font-semibold tabular-nums">{count}</span>{" "}
        {count === 1 ? "question the AI couldn't answer" : "questions the AI couldn't answer"}
        {topics.length > 0 ? (
          <span className="mt-0.5 block truncate text-xs text-fg-secondary" data-testid="gap-topics">
            Most asked: {topics.join(" · ")}
          </span>
        ) : null}
      </span>
      <ChevronRight className="size-4 shrink-0 text-fg-secondary" aria-hidden />
    </Link>
  );
}
