"use client";

import { FileText, Globe, HelpCircle, Loader2, Pencil, Plus, StickyNote, Trash2, type LucideIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { UsageMeter } from "@/components/billing/UsageMeter";
import { BILLING_HREF } from "@/components/shell/nav";
import { EmptyState } from "@/components/states/EmptyState";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { isProcessing, useDeleteKnowledgeSource } from "@/lib/api/queries";
import type { KnowledgeSource, KnowledgeSourceList, KnowledgeType } from "@/lib/api/types";
import { emptyStates, knowledgeLimitReached } from "@/lib/copy";
import { TONE_CLASS } from "@/lib/inbox/format";
import { relativeTime } from "@/lib/time";
import { toastError } from "@/lib/toast-error";
import { cn } from "@/lib/utils";
import { useCurrentWorkspace } from "@/lib/workspace";

import { SOURCE_TYPE_LABEL } from "./SourceSheet";

const TYPE_ICON: Record<KnowledgeType, LucideIcon> = {
  faq: HelpCircle,
  text: StickyNote,
  url: Globe,
  file: FileText,
};

const ADD_ORDER: KnowledgeType[] = ["faq", "text", "url", "file"];
const count = new Intl.NumberFormat("en-US");

/** UX-SCR-06 "Add knowledge": FAQ, Note, Web page or File, each opening its form in a sheet. */
export function AddKnowledgeMenu({ onChoose, label = "Add knowledge" }: { onChoose: (type: KnowledgeType) => void; label?: string }) {
  return (
    // Not modal: the sheet opens from it.
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger asChild>
        <Button className="bg-brand-gradient text-white">
          <Plus aria-hidden /> {label}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-44 border-line bg-panel shadow-xl">
        {ADD_ORDER.map((type) => {
          const Icon = TYPE_ICON[type];
          return (
            <DropdownMenuItem key={type} onSelect={() => onChoose(type)}>
              <Icon aria-hidden /> {SOURCE_TYPE_LABEL[type]}
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** FR-KB-02: Processing (with a spinner), Ready, or Failed with the reason. */
export function StatusChip({ source }: { source: KnowledgeSource }) {
  if (isProcessing(source)) {
    return (
      <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium", TONE_CLASS.brand)}>
        <Loader2 className="size-3 animate-spin" aria-hidden /> Processing
      </span>
    );
  }
  if (source.status === "failed") {
    return <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", TONE_CLASS.danger)}>Failed</span>;
  }
  return <span className="rounded-full bg-success/15 px-2 py-0.5 text-xs font-medium text-success">Ready</span>;
}

function detail(source: KnowledgeSource): string | null {
  if (source.type === "url") return source.url ?? null;
  if (source.type === "file") return source.file_name ?? null;
  return null;
}

/** UX-SCR-06: the sources table and the plan's character usage. */
export function SourcesCard({
  data,
  now,
  onAdd,
  onEdit,
}: {
  data: KnowledgeSourceList;
  now: Date;
  onAdd: (type: KnowledgeType) => void;
  onEdit: (source: KnowledgeSource) => void;
}) {
  const workspace = useCurrentWorkspace();
  const remove = useDeleteKnowledgeSource(workspace.id);
  const [deleting, setDeleting] = useState<KnowledgeSource | null>(null);
  const { items, usage } = data;

  return (
    // The table runs edge to edge; --card-padding (the header strip's 20 px) lines its edge cells up
    // with the title until this card moves onto Card (UI-039).
    <section aria-labelledby="sources-title" className="rounded-xl border border-line bg-panel [--card-padding:--spacing(5)]">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-line p-5">
        <div>
          <h2 id="sources-title" className="text-base font-semibold">
            Sources
          </h2>
          <p className="text-xs text-fg-secondary">What the AI may use to answer. Nothing else counts as a fact.</p>
        </div>
        <div className="w-full sm:w-64">
          <UsageMeter
            label="Knowledge used"
            used={usage.characters_used}
            limit={usage.characters_limit}
            unit="characters"
            fullMessage={knowledgeLimitReached(usage.characters_limit)}
            upgradeHref={workspace.role === "agent" ? undefined : BILLING_HREF(workspace.slug)}
          />
        </div>
      </div>
      {items.length === 0 ? (
        <EmptyState
          title={emptyStates.knowledge.title}
          body={emptyStates.knowledge.body}
          action={<AddKnowledgeMenu onChoose={onAdd} />}
        />
      ) : (
        <Table>
          <TableCaption className="sr-only">Knowledge sources</TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead>Source</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="hidden text-right sm:table-cell">Characters</TableHead>
              <TableHead className="hidden md:table-cell">Updated</TableHead>
              <TableHead className="text-right">
                <span className="sr-only">Actions</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((source) => {
              const Icon = TYPE_ICON[source.type];
              const sub = detail(source);
              return (
                <TableRow key={source.id} data-status={source.status}>
                  {/* The name takes the room the other columns leave, and truncates in it. */}
                  <TableCell className="w-full max-w-0">
                    <div className="flex items-start gap-3">
                      <Icon className="mt-0.5 size-4 shrink-0 text-fg-secondary" aria-hidden />
                      <div className="min-w-0">
                        <p className="truncate font-medium">
                          <span className="sr-only">{SOURCE_TYPE_LABEL[source.type]}: </span>
                          {source.title}
                        </p>
                        {sub ? <p className="truncate text-xs text-fg-secondary">{sub}</p> : null}
                        {source.status === "failed" && source.error ? (
                          <p className="text-xs text-danger-fg">{source.error}</p>
                        ) : null}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <StatusChip source={source} />
                  </TableCell>
                  <TableCell className="hidden text-right sm:table-cell">
                    {source.status === "ready" ? (
                      <>
                        {count.format(source.char_count)}
                        <span className="block text-xs text-fg-secondary">
                          {source.chunk_count} {source.chunk_count === 1 ? "chunk" : "chunks"}
                        </span>
                      </>
                    ) : (
                      <span className="text-fg-secondary">—</span>
                    )}
                  </TableCell>
                  <TableCell className="hidden text-fg-secondary md:table-cell">
                    {relativeTime(source.updated_at, now)}
                  </TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon-lg"
                        className="size-10 md:size-8"
                        aria-label={`Edit ${source.title}`}
                        onClick={() => onEdit(source)}
                      >
                        <Pencil aria-hidden />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-lg"
                        className="size-10 text-danger-fg hover:text-danger-fg md:size-8"
                        aria-label={`Delete ${source.title}`}
                        disabled={remove.isPending && remove.variables === source.id}
                        onClick={() => setDeleting(source)}
                      >
                        <Trash2 aria-hidden />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}

      <AlertDialog open={Boolean(deleting)} onOpenChange={(open) => (open ? undefined : setDeleting(null))}>
        <AlertDialogContent className="border-line bg-panel">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete “{deleting?.title}”?</AlertDialogTitle>
            <AlertDialogDescription className="text-fg-secondary">
              The AI stops using it right away. This can&apos;t be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-danger-fill text-white hover:bg-danger-fill/90"
              onClick={() => {
                const source = deleting;
                if (!source) return;
                remove.mutate(source.id, {
                  onSuccess: () => toast.success(`Deleted “${source.title}”`),
                  onError: (error) => toastError(error),
                });
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}
