import { ChevronRight, HelpCircle } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

/** UX-SCR-01 / FR-KB-06: "{n} questions the AI couldn't answer", linking to Knowledge. Hidden at 0. */
export function KnowledgeGapsRow({ count, slug }: { count: number; slug: string }) {
  if (count <= 0) return null;
  return (
    <Link
      href={`/w/${slug}/knowledge` as Route}
      className="flex items-center gap-3 rounded-xl border border-line bg-panel p-4 hover:bg-white/5"
    >
      <HelpCircle className="size-5 shrink-0 text-warning" aria-hidden />
      <span className="flex-1 text-sm">
        <span className="font-semibold tabular-nums">{count}</span>{" "}
        {count === 1 ? "question the AI couldn't answer" : "questions the AI couldn't answer"}
      </span>
      <ChevronRight className="size-4 text-fg-secondary" aria-hidden />
    </Link>
  );
}
