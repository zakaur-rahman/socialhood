"use client";

import {
  ChevronRight,
  FileText,
  Globe,
  HelpCircle,
  Network,
  Pencil,
  Plus,
  StickyNote,
  Trash2,
  type LucideIcon,
} from "lucide-react";
import { Fragment, useRef, useState } from "react";
import { toast } from "sonner";

import { useReturnFocus } from "@/components/agent/use-return-focus";
import { knowledgeUpgrade } from "@/components/billing/upgrade-requests";
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
import { useUpgradeDialog } from "@/lib/api/provider";
import { isProcessing, useApproveKnowledgeSource, useDeleteKnowledgeSource } from "@/lib/api/queries";
import type { KnowledgeCreateType, KnowledgeSource, KnowledgeSourceList, KnowledgeType } from "@/lib/api/types";
import { emptyStates, knowledgeLimitReached } from "@/lib/copy";
import { waitingFirst, waitingLine } from "@/lib/knowledge/approval";
import { PERMISSION, useCan } from "@/lib/permissions";
import { relativeTime } from "@/lib/time";
import { cn } from "@/lib/utils";
import { toastError } from "@/lib/toast-error";
import { useCurrentWorkspace } from "@/lib/workspace";

import { SitePages } from "./SitePages";
import { SOURCE_TYPE_LABEL } from "./SourceSheet";

const TYPE_ICON: Record<KnowledgeType, LucideIcon> = {
  faq: HelpCircle,
  text: StickyNote,
  url: Globe,
  file: FileText,
  site: Network,
  page: Globe,
};

const ADD_ORDER: KnowledgeCreateType[] = ["faq", "text", "url", "site", "file"];
/** A waiting source longer than this starts cut short, with "Show all". */
const LONG_BODY = 400;
const count = new Intl.NumberFormat("en-US");

/** UX-SCR-06 "Add knowledge": FAQ, Note, Web page, Website or File, each opening its form in a sheet. */
export function AddKnowledgeMenu({
  onChoose,
  label = "Add knowledge",
  size,
  variant,
}: {
  onChoose: (type: KnowledgeCreateType) => void;
  label?: string;
  /** `sm` in a compact empty state. */
  size?: "sm";
  /** `secondary` when the page header already holds the one primary (D-10). */
  variant?: "secondary";
}) {
  // The sheet opens once the menu has closed and handed focus back to this button, so the sheet
  // remembers the button and returns focus to it (UX-A11Y-02). Opened from the item itself, it
  // remembered nothing (the item was gone) and focus fell to <body> on close.
  const chosen = useRef<KnowledgeCreateType | null>(null);
  return (
    // Not modal (the menu's default), so the sheet can open from it.
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button size={size} variant={variant}>
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
  if (source.status === "awaiting_approval") {
    return (
      <Badge tone="warning" size="md" className={className}>
        Waiting for approval
      </Badge>
    );
  }
  if (isProcessing(source)) {
    return (
      <Badge tone="neutral" size="md" className={className}>
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
  if (source.type === "url" || source.type === "site") return source.url ?? null;
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
  onAdd: (type: KnowledgeCreateType) => void;
  onEdit: (source: KnowledgeSource) => void;
}) {
  const workspace = useCurrentWorkspace();
  const remove = useDeleteKnowledgeSource(workspace.id);
  const approve = useApproveKnowledgeSource(workspace.id);
  const { can } = useCan();
  const upgradeDialog = useUpgradeDialog();
  const [deleting, setDeleting] = useState<KnowledgeSource | null>(null);
  // GR-35: the websites whose pages are open under their row.
  const [open, setOpen] = useState<Record<string, boolean>>({});
  // The confirmation opens from a row's Delete without a Radix trigger: Cancel or Esc returns focus there.
  const returnFocus = useReturnFocus();
  // A confirmed delete removes the row focus was returned to; the heading takes focus then.
  const headingRef = useRef<HTMLHeadingElement>(null);
  const removedRef = useRef(false);
  const { items, usage } = data;
  const canManage = can(PERMISSION.manageKnowledge);
  const waiting = items.filter((source) => source.status === "awaiting_approval").length;

  return (
    <Card asChild padding="roomy">
      <section aria-labelledby="sources-title">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <CardHeader>
            <CardTitle id="sources-title" ref={headingRef} tabIndex={-1}>
              Sources
            </CardTitle>
            <CardDescription>
              What the AI may use to answer. Nothing else counts as a fact.
              {canManage && waiting > 0 ? (
                <span className="block font-medium text-fg" data-testid="waiting-count">
                  {waitingLine(waiting)}
                </span>
              ) : null}
            </CardDescription>
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
                  <Button type="button" variant="link" size="xs" onClick={() => upgradeDialog.open(knowledgeUpgrade(usage.characters_limit))}>
                    Upgrade
                  </Button>
                )
              }
            />
          </div>
        </div>
        {/* A container, so the columns follow the room the table has, not the screen: beside the
        Test box (from 1280 px) the table is about 640 px, and Updated would leave the name 12 characters. */}
        <CardBleed className="@container mt-5 border-t border-line">
          {items.length === 0 ? (
            <div className="p-(--card-padding)">
              <EmptyState
                size="compact"
                title={emptyStates.knowledge.title}
                body={emptyStates.knowledge.body}
                action={<AddKnowledgeMenu onChoose={onAdd} size="sm" variant="secondary" />}
              />
            </div>
          ) : (
            <Table>
              <TableCaption className="sr-only">Knowledge sources</TableCaption>
              <TableHeader>
                <TableRow>
                  <TableHead>Source</TableHead>
                  <TableHead className="hidden @lg:table-cell">Status</TableHead>
                  <TableHead className="hidden text-right @xl:table-cell">Characters</TableHead>
                  <TableHead className="hidden @3xl:table-cell">Updated</TableHead>
                  <TableHead className="text-right">
                    <span className="sr-only">Actions</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {waitingFirst(items).map((source) => {
                  const Icon = TYPE_ICON[source.type];
                  const sub = detail(source);
                  const isSite = source.type === "site";
                  const pagesOpen = isSite && open[source.id] === true;
                  const long = (source.body?.length ?? 0) > LONG_BODY;
                  const full = open[`body-${source.id}`] === true;
                  const characters = isSite ? (source.site?.char_count ?? 0) : source.char_count;
                  const chunks = isSite ? (source.site?.chunk_count ?? 0) : source.chunk_count;
                  return (
                    <Fragment key={source.id}>
                    <TableRow data-status={source.status} className={source.status === "awaiting_approval" ? "border-b-0" : undefined}>
                      {/* The name takes the room the other columns leave, and truncates in it. Below 512 px of table the
                      status sits under the name, so the name keeps the Status column's 75 px (at 320 px it
                      had about 35 px beside the status and two 40 px buttons). */}
                      <TableCell className="w-full max-w-0">
                        <div className="flex items-start gap-3">
                          {isSite ? (
                            <Button
                              variant="ghost"
                              size="icon"
                              className="-my-1 -ml-2 size-8 shrink-0"
                              aria-label={`${pagesOpen ? "Hide" : "Show"} pages of ${source.title}`}
                              aria-expanded={pagesOpen}
                              aria-controls={`site-pages-${source.id}`}
                              onClick={() => setOpen((current) => ({ ...current, [source.id]: !pagesOpen }))}
                            >
                              <ChevronRight className={pagesOpen ? "rotate-90 motion-safe:transition-transform" : "motion-safe:transition-transform"} aria-hidden />
                            </Button>
                          ) : (
                            <Icon className="mt-0.5 size-4 shrink-0 text-fg-secondary" aria-hidden />
                          )}
                          <div className="min-w-0">
                            <p className={source.status === "awaiting_approval" ? "line-clamp-2 font-medium" : "truncate font-medium"}>
                              <span className="sr-only">{SOURCE_TYPE_LABEL[source.type]}: </span>
                              {source.title}
                            </p>
                            {sub ? <p className="truncate text-xs text-fg-secondary">{sub}</p> : null}
                            {isSite && source.site ? (
                              <p className="text-xs text-fg-secondary">
                                {source.site.pages_found} {source.site.pages_found === 1 ? "page" : "pages"}
                                {source.site.pages_failed > 0 ? `, ${source.site.pages_failed} failed` : ""}
                              </p>
                            ) : null}
                            <StatusChip source={source} className="mt-1 @lg:hidden" />
                            {source.status === "failed" && source.error ? (
                              <p className="text-xs text-danger-fg">{source.error}</p>
                            ) : null}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="hidden @lg:table-cell">
                        <StatusChip source={source} />
                      </TableCell>
                      <TableCell className="hidden text-right @xl:table-cell">
                        {source.status === "ready" ? (
                          <>
                            {count.format(characters)}
                            <span className="block text-xs text-fg-secondary">
                              {chunks} {chunks === 1 ? "chunk" : "chunks"}
                            </span>
                          </>
                        ) : (
                          <span className="text-fg-secondary">—</span>
                        )}
                      </TableCell>
                      <TableCell className="hidden text-fg-secondary @3xl:table-cell">
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
                    {source.status === "awaiting_approval" ? (
                      <TableRow data-awaiting-approval={source.id}>
                        <TableCell colSpan={5} className="whitespace-normal">
                          <p className="text-xs text-fg-secondary">
                            Added by an AI app. Your AI won&apos;t use it until it&apos;s approved.
                          </p>
                          {source.question && source.question !== source.title ? <p className="mt-2 font-medium break-words">{source.question}</p> : null}
                          {source.body ? (
                            <>
                              {/* Focusable so the keyboard can scroll it: Safari doesn't make scrollers focusable. */}
                              <div className="relative mt-1">
                                <div
                                  role="group"
                                  tabIndex={0}
                                  aria-label={`Content of ${source.title}`}
                                  className={cn(
                                    "max-w-prose overflow-y-auto break-words whitespace-pre-wrap",
                                    long && !full ? "max-h-32 overflow-hidden" : !long && "max-h-64",
                                  )}
                                >
                                  {source.body}
                                </div>
                                {long && !full ? (
                                  <div aria-hidden className="pointer-events-none absolute inset-x-0 bottom-0 h-10 bg-linear-to-t from-panel to-transparent" />
                                ) : null}
                              </div>
                              {long && !full ? (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  className="mt-1"
                                  aria-label={`Show all of ${source.title}`}
                                  onClick={() => setOpen((current) => ({ ...current, [`body-${source.id}`]: true }))}
                                >
                                  Show all
                                </Button>
                              ) : null}
                            </>
                          ) : null}
                          {canManage ? (
                            <div className="mt-3 flex flex-wrap gap-2">
                              <Button
                                size="sm"
                                variant="secondary"
                                aria-label={`Approve ${source.title}`}
                                loading={approve.isPending && approve.variables === source.id}
                                disabled={remove.isPending && remove.variables === source.id}
                                onClick={() =>
                                  approve.mutate(source.id, {
                                    onSuccess: () => {
                                      toast.success(`Approved “${source.title}”`);
                                      // The row's buttons go with the approval.
                                      headingRef.current?.focus();
                                    },
                                    onError: (error) => toastError(error),
                                  })
                                }
                              >
                                Approve
                              </Button>
                              <Button
                                size="sm"
                                variant="destructive-ghost"
                                aria-label={`Reject ${source.title}`}
                                loading={remove.isPending && remove.variables === source.id}
                                disabled={approve.isPending && approve.variables === source.id}
                                onClick={() => setDeleting(source)}
                              >
                                Reject
                              </Button>
                            </div>
                          ) : null}
                        </TableCell>
                      </TableRow>
                    ) : null}
                    {pagesOpen ? (
                      <TableRow data-site-pages={source.id}>
                        <TableCell colSpan={5} className="p-0 whitespace-normal">
                          <SitePages site={source} now={now} />
                        </TableCell>
                      </TableRow>
                    ) : null}
                    </Fragment>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardBleed>

        <AlertDialog open={Boolean(deleting)} onOpenChange={(open) => (open ? undefined : setDeleting(null))}>
          <AlertDialogContent
            {...returnFocus}
            onCloseAutoFocus={(event) => {
              // The deleted row is gone (or about to be): the dialog's focus return would land on it.
              if (removedRef.current) {
                removedRef.current = false;
                event.preventDefault();
                headingRef.current?.focus();
              } else returnFocus.onCloseAutoFocus(event);
            }}
          >
            <AlertDialogHeader>
              <AlertDialogTitle>
                {deleting?.status === "awaiting_approval" ? "Reject" : "Delete"} “{deleting?.title}”?
              </AlertDialogTitle>
              <AlertDialogDescription>
                {deleting?.status === "awaiting_approval"
                  ? "The AI never used it. This can't be undone."
                  : deleting?.type === "site"
                    ? "The AI stops using the site and all its pages right away. This can't be undone."
                    : "The AI stops using it right away. This can't be undone."}
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
                      toast.success(`${source.status === "awaiting_approval" ? "Rejected" : "Deleted"} “${source.title}”`);
                      // Closing still ahead: the dialog's own focus return must not win.
                      removedRef.current = document.querySelector("[role=alertdialog]") !== null;
                      // Focus may still be inside the closing dialog or on the vanished row: take it.
                      const active = document.activeElement;
                      if (
                        !active ||
                        active === document.body ||
                        !active.isConnected ||
                        active.closest("[role=alertdialog]")
                      ) {
                        headingRef.current?.focus();
                      }
                    },
                    onError: (error) => toastError(error),
                  });
                }}
              >
                {deleting?.status === "awaiting_approval" ? "Reject" : "Delete"}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </section>
    </Card>
  );
}
