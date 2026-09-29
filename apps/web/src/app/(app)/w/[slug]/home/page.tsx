"use client";

import { toast } from "sonner";

import { Checklist } from "@/components/home/Checklist";
import { KnowledgeGapsRow } from "@/components/home/KnowledgeGapsRow";
import { PageFrame } from "@/components/shell/PageFrame";
import { ErrorState } from "@/components/states/ErrorState";
import { Skeleton } from "@/components/ui/skeleton";
import { useMe, useOverview, useUpdateWorkspace } from "@/lib/api/queries";
import { errorMessage, greeting } from "@/lib/copy";
import { useCurrentWorkspace } from "@/lib/workspace";

// UX-SCR-01 tiles. Their numbers come with the overview metrics (T9.1); until there is data a
// tile shows "—" and a hint, never a fake chart.
const TILES = [
  { label: "Needs reply", hint: "Conversations waiting for you." },
  { label: "Messages today", hint: "Counted once an account is connected." },
  { label: "Handled by AI, 7 days", hint: "Share of replies sent by the AI." },
  { label: "Median first response, 7 days", hint: "How fast customers hear back." },
] as const;

export default function HomePage() {
  const workspace = useCurrentWorkspace();
  const me = useMe();
  const overview = useOverview(workspace.id);
  const update = useUpdateWorkspace(workspace.id);

  const firstName = me.data?.name?.split(" ")[0];
  const title = me.data ? greeting(new Date(), firstName) : "Home";

  const dismiss = () =>
    update.mutate(
      { checklist_dismissed: true },
      { onError: (error) => toast.error(errorMessage(error)) },
    );

  return (
    <PageFrame title={title}>
      <div className="space-y-6">
        {overview.isPending ? (
          <Skeleton className="h-48 w-full rounded-xl bg-panel" />
        ) : overview.isError ? (
          <ErrorState error={overview.error} onRetry={() => void overview.refetch()} />
        ) : overview.data.checklist.dismissed ? null : (
          <Checklist
            steps={overview.data.checklist.steps}
            slug={workspace.slug}
            onDismiss={dismiss}
            dismissing={update.isPending}
          />
        )}

        <section aria-label="This week" className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {TILES.map((tile) => (
            <div key={tile.label} className="rounded-xl border border-line bg-panel p-4">
              <p className="text-xs text-fg-secondary">{tile.label}</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums">—</p>
              <p className="mt-1 text-xs text-fg-secondary">{tile.hint}</p>
            </div>
          ))}
        </section>

        {overview.data && workspace.role !== "agent" ? (
          <KnowledgeGapsRow count={overview.data.knowledge_gaps_open ?? 0} slug={workspace.slug} />
        ) : null}
      </div>
    </PageFrame>
  );
}
