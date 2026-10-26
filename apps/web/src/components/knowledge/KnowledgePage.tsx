"use client";

import { useState } from "react";
import { toast } from "sonner";

import { PageFrame } from "@/components/shell/PageFrame";
import { ErrorState } from "@/components/states/ErrorState";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAiSettings, useDismissKnowledgeGap, useKnowledgeGaps, useKnowledgeSources } from "@/lib/api/queries";
import type { KnowledgeGap } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { toastError } from "@/lib/toast-error";
import { useNow } from "@/lib/use-browser-state";
import { useCurrentWorkspace } from "@/lib/workspace";

import { BrandVoiceCard } from "./BrandVoiceCard";
import { KnowledgeGapsCard } from "./KnowledgeGapsCard";
import { SourceSheet, type KnowledgeUploader, type SourceSheetMode } from "./SourceSheet";
import { AddKnowledgeMenu, SourcesCard } from "./SourcesCard";
import { TestBox } from "./TestBox";

function CardSkeleton({ label, rows = 2 }: { label: string; rows?: number }) {
  return (
    <Card padding="roomy" className="space-y-3" role="status" aria-busy="true" aria-label={label}>
      <Skeleton className="h-4 w-40" />
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-3 w-full" />
      ))}
    </Card>
  );
}

/**
 * UX-SCR-06 / F-14, F-17: open questions the AI couldn't answer (when there are any), the
 * sources with their status and the plan usage, brand voice collapsed to a summary (UI-ISS-089),
 * and the test box (sticky on the right at ≥ 1280 px, below on smaller screens).
 */
export function KnowledgePage({ upload }: { upload?: KnowledgeUploader }) {
  const workspace = useCurrentWorkspace();
  const wid = workspace.id;
  const now = useNow();
  const settings = useAiSettings(wid);
  const sources = useKnowledgeSources(wid);
  const gaps = useKnowledgeGaps(wid);
  const dismissGap = useDismissKnowledgeGap(wid);
  const [sheet, setSheet] = useState<SourceSheetMode | null>(null);

  const openGaps = gaps.data?.items ?? [];
  const answering = sheet?.kind === "create" ? (sheet.gapId ?? null) : null;

  const addAnswer = (gap: KnowledgeGap) =>
    setSheet({ kind: "create", type: "faq", question: gap.examples[0]?.text ?? gap.topic, gapId: gap.id });

  const dismiss = (gap: KnowledgeGap) =>
    dismissGap.mutate(gap.id, {
      onSuccess: () => toast.success("Dismissed. It comes back if a customer asks again."),
      onError: (error) => toastError(error),
    });

  const gapsCard = (
    <KnowledgeGapsCard
      gaps={openGaps}
      now={now}
      onAddAnswer={addAnswer}
      onDismiss={dismiss}
      busyId={answering ?? (dismissGap.isPending ? dismissGap.variables : null)}
    />
  );

  // The cards below are shown together once all three requests have answered, so one arriving
  // earlier doesn't push another (or the test box under them on a phone) while the page settles.
  const ready = !sources.isPending && !settings.isPending && !gaps.isPending;

  return (
    <PageFrame title="Knowledge" actions={<AddKnowledgeMenu onChoose={(type) => setSheet({ kind: "create", type })} />}>
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-6">
          {gaps.isError ? <ErrorState error={gaps.error} onRetry={() => void gaps.refetch()} /> : null}
          {openGaps.length > 0 ? gapsCard : null}

          {!ready ? (
            <CardSkeleton label="Loading sources" rows={4} />
          ) : sources.isError ? (
            <ErrorState error={sources.error} onRetry={() => void sources.refetch()} />
          ) : (
            <SourcesCard
              data={sources.data}
              now={now}
              onAdd={(type) => setSheet({ kind: "create", type })}
              onEdit={(source) => setSheet({ kind: "edit", source })}
            />
          )}

          {!ready ? (
            <CardSkeleton label="Loading brand voice" rows={2} />
          ) : settings.isError ? (
            <ErrorState error={settings.error} onRetry={() => void settings.refetch()} />
          ) : (
            <BrandVoiceCard wid={wid} settings={settings.data} workspaceName={workspace.name} />
          )}

          {gaps.isSuccess && openGaps.length === 0 ? gapsCard : null}
        </div>
        <aside aria-label="Try the AI" className={cn("xl:sticky xl:top-6 xl:self-start", !ready && "max-xl:hidden")}>
          <TestBox wid={wid} onAddAnswer={(question) => setSheet({ kind: "create", type: "faq", question })} />
        </aside>
      </div>
      <SourceSheet mode={sheet} onOpenChange={(open) => (open ? undefined : setSheet(null))} upload={upload} />
    </PageFrame>
  );
}
