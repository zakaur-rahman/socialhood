"use client";

import { FileText, Globe, HelpCircle, Pencil, Plus, StickyNote, Trash2, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { useReturnFocus } from "@/components/agent/use-return-focus";
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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBleed, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Meter } from "@/components/ui/meter";
import { Spinner } from "@/components/ui/spinner";
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { isProcessing, useDeleteKnowledgeSource } from "@/lib/api/queries";
import type { KnowledgeSource, KnowledgeSourceList, KnowledgeType } from "@/lib/api/types";
import { emptyStates, knowledgeLimitReached } from "@/lib/copy";
import { relativeTime } from "@/lib/time";
import { toastError } from "@/lib/toast-error";
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
export function AddKnowledgeMenu({
  onChoose,
  label = "Add knowledge",
  size,
}: {
  onChoose: (type: KnowledgeType) => void;
  label?: string;
  /** `sm` in a compact empty state. */
  size?: "sm";
}) {
  // The sheet opens once the menu has closed and handed focus back to this button, so the sheet
  // remembers the button and returns focus to it (UX-A11Y-02). Opened from the item itself, it
  // remembered nothing (the item was gone) and focus fell to <body> on close.
  const chosen = useRef<KnowledgeType | null>(null);
  return (
    // Not modal (the menu's default), so the sheet can open from it.
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button size={size}>
          <Plus aria-hidden /> {label}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        onCloseAutoFocus={() => {
          const type = chosen.current;
          chosen.current = null;
          if (type) onChoose(type);
        }}
      >
        {ADD_ORDER.map((type) => {
          const Icon = TYPE_ICON[type];
          return (
            <DropdownMenuItem key={type} onSelect={() => (chosen.current = type)}>
              <Icon aria-hidden /> {SOURCE_TYPE_LABEL[type]}
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** FR-KB-02: Processing (with a spinner), Ready, or Failed with the reason. */
export function StatusChip({ source, className }: { source: KnowledgeSource; className?: string }) {
  if (isProcessing(source)) {
    return (
      <Badge tone="brand" size="md" className={className}>
        <Spinner size="xs" /> Processing
      </Badge>
    );
  }
  if (source.status === "failed") {
    return (
      <Badge tone="danger" size="md" className={className}>
        Failed
      </Badge>
    );
  }
  return (
    <Badge tone="success" size="md" className={className}>
      Ready
    </Badge>
  );
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
  // The confirmation opens from a row's Delete without a Radix trigger: Cancel or Esc returns focus there.
  const returnFocus = useReturnFocus();
  // A confirmed delete removes the row focus was returned to; the heading takes focus then.
  const headingRef = useRef<HTMLHeadingElement>(null);
  const { items, usage } = data;

  return (
    <Card asChild padding="roomy">
      <section aria-labelledby="sources-title">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <CardHeader>
            <CardTitle id="sources-title" ref={headingRef} tabIndex={-1}>
              Sources
            </CardTitle>
            <CardDescription>What the AI may use to answer. Nothing else counts as a fact.</CardDescription>
          </CardHeader>
          <div className="w-full sm:w-64">
            <Meter
              label="Knowledge used"
              value={usage.characters_used}
              max={usage.characters_limit}
              unit="characters"
              fullMessage={knowledgeLimitReached(usage.characters_limit)}
              action={
                workspace.role === "agent" ? undefined : (
                  <Button asChild variant="link" size="xs">
                    <Link href={BILLING_HREF(workspace.slug)}>Upgrade</Link>
                  </Button>
                )
              }
            />
          </div>
        </div>
        <CardBleed className="mt-5 border-t border-line">
          {items.length === 0 ? (
            <div className="p-(--card-padding)">
              <EmptyState
                size="compact"
                title={emptyStates.knowledge.title}
                body={emptyStates.knowledge.body}
                action={<AddKnowledgeMenu onChoose={onAdd} size="sm" />}
              />
            </div>
          ) : (
            <Table>
              <TableCaption className="sr-only">Knowledge sources</TableCaption>
              <TableHeader>
                <TableRow>
                  <TableHead>Source</TableHead>
                  <TableHead className="hidden md:table-cell">Status</TableHead>
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
                      {/* The name takes the room the other columns leave, and truncates in it. Below 768 px the
                      status sits under the name, so the name keeps the Status column's 75 px (at 320 px it
                      had about 35 px beside the status and two 40 px buttons). */}
                      <TableCell className="w-full max-w-0">
                        <div className="flex items-start gap-3">
                          <Icon className="mt-0.5 size-4 shrink-0 text-fg-secondary" aria-hidden />
                          <div className="min-w-0">
                            <p className="truncate font-medium">
                              <span className="sr-only">{SOURCE_TYPE_LABEL[source.type]}: </span>
                              {source.title}
                            </p>
                            {sub ? <p className="truncate text-xs text-fg-secondary">{sub}</p> : null}
                            <StatusChip source={source} className="mt-1 md:hidden" />
                            {source.status === "failed" && source.error ? (
                              <p className="text-xs text-danger-fg">{source.error}</p>
                            ) : null}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
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
                            size="icon"
                            aria-label={`Edit ${source.title}`}
                            onClick={() => onEdit(source)}
                          >
                            <Pencil aria-hidden />
                          </Button>
                          <Button
                            variant="destructive-ghost"
                            size="icon"
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
        </CardBleed>

        <AlertDialog open={Boolean(deleting)} onOpenChange={(open) => (open ? undefined : setDeleting(null))}>
          <AlertDialogContent {...returnFocus}>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete “{deleting?.title}”?</AlertDialogTitle>
              <AlertDialogDescription>
                The AI stops using it right away. This can&apos;t be undone.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                variant="destructive"
                onClick={() => {
                  const source = deleting;
                  if (!source) return;
                  remove.mutate(source.id, {
                    onSuccess: () => {
                      toast.success(`Deleted “${source.title}”`);
                      const active = document.activeElement;
                      if (!active || active === document.body || !active.isConnected) headingRef.current?.focus();
                    },
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
    </Card>
  );
}
