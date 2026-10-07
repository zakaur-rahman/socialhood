"use client";

import {
  ArrowDown,
  ArrowUp,
  Clock,
  Copy,
  EllipsisVertical,
  GripVertical,
  MessageCircle,
  MessagesSquare,
  Pause,
  Play,
  Send,
  Sparkles,
  Trash2,
} from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useRef, useState, type HTMLAttributes, type Ref } from "react";

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
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Switch } from "@/components/ui/switch";
import type { Automation, TriggerName } from "@/lib/api/types";
import {
  actionBadge,
  formatCount,
  lastRunText,
  queueBadge,
  STATUS_LABEL,
  statusText,
  triggerSummary,
} from "@/lib/automations/format";
import { cn } from "@/lib/utils";

import { TrendLine } from "./TrendLine";

const TRIGGER_ICON: Record<TriggerName, typeof Send> = {
  comment_keyword: MessageCircle,
  comment_any: MessagesSquare,
  dm_keyword: Send,
};

const MAX_CHIPS = 3;

export type RowReorder = {
  /** The drag handle's pointer handlers and the keyboard alternative (arrow keys). */
  handleProps: HTMLAttributes<HTMLButtonElement>;
  canMoveUp: boolean;
  canMoveDown: boolean;
  onMove: (direction: -1 | 1) => void;
  /** Where a dragged row would land: a brand line above or below this row. */
  dropMarker: "before" | "after" | null;
  dragging: boolean;
  hintId: string;
};

type Props = {
  automation: Automation;
  href: Route;
  timeZone: string;
  now: Date;
  selected: boolean;
  /** Some row is selected: checkboxes stay visible. */
  selecting: boolean;
  onSelectedChange: (selected: boolean) => void;
  onActiveChange: (active: boolean) => void;
  statusPending: boolean;
  onDuplicate: () => void;
  onDelete: () => void;
  /** Present when the list shows the account's automations in priority order. */
  reorder?: RowReorder;
  rowRef?: Ref<HTMLLIElement>;
};

/**
 * UX-SCR-02 row: switch, name, trigger, keywords, action, 7-day runs with the trend line, last
 * run, queue and status, and the row menu. The name is the link; the whole row follows it.
 * Below 768 px it becomes a card with the switch at the top right.
 */
export function AutomationRow({
  automation,
  href,
  timeZone,
  now,
  selected,
  selecting,
  onSelectedChange,
  onActiveChange,
  statusPending,
  onDuplicate,
  onDelete,
  reorder,
  rowRef,
}: Props) {
  const [confirmDelete, setConfirmDelete] = useState(false);
  // The confirmation opens from a menu item, which is gone by the time it closes, so focus goes
  // back to the row's ⋯ button (UX-A11Y-02).
  const menuTrigger = useRef<HTMLButtonElement>(null);
  const active = automation.status === "active";
  const TriggerIcon = automation.trigger ? TRIGGER_ICON[automation.trigger] : MessageCircle;
  const chips = automation.keywords.slice(0, MAX_CHIPS);
  const more = automation.keywords.length - chips.length;
  const action = actionBadge(automation);
  const queue = queueBadge(automation.queue);
  const status = statusText(automation, timeZone);
  const name = automation.name;
  const resumeLabel = automation.status === "draft" ? "Activate" : "Resume";

  return (
    <li
      ref={rowRef}
      data-automation={automation.id}
      className={cn(
        "group/row relative rounded-xl border border-line bg-panel motion-safe:transition-opacity",
        reorder?.dragging && "opacity-60",
        reorder?.dropMarker === "before" &&
          "before:absolute before:inset-x-2 before:-top-[5px] before:h-0.5 before:rounded-full before:bg-brand",
        reorder?.dropMarker === "after" &&
          "after:absolute after:inset-x-2 after:-bottom-[5px] after:h-0.5 after:rounded-full after:bg-brand",
      )}
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-3 p-4 md:flex-nowrap md:py-3">
        {/* Revealed on hover only with a mouse: on touch the checkbox and the handle always show (UI-ISS-057). */}
        <div
          className={cn(
            "relative z-10 hidden items-center md:order-1 md:flex",
            !selecting &&
              "pointer-fine:opacity-0 pointer-fine:group-hover/row:opacity-100 pointer-fine:focus-within:opacity-100",
          )}
        >
          <Checkbox
            checked={selected}
            onCheckedChange={(value) => onSelectedChange(value === true)}
            aria-label={`Select ${name}`}
          />
        </div>

        {reorder ? (
          <Button
            variant="ghost"
            size="icon"
            aria-label={`Reorder ${name}`}
            aria-describedby={reorder.hintId}
            {...reorder.handleProps}
            className="relative z-10 order-first cursor-grab touch-none text-fg-secondary focus-visible:opacity-100 active:cursor-grabbing md:order-2 md:pointer-fine:opacity-0 md:pointer-fine:group-hover/row:opacity-100"
          >
            <GripVertical aria-hidden />
          </Button>
        ) : null}

        <div className="relative z-10 order-3 flex items-center md:order-3">
          <Switch
            checked={active}
            disabled={statusPending}
            onCheckedChange={onActiveChange}
            aria-label={`Active: ${name}`}
          />
        </div>

        <div className="order-2 min-w-0 flex-1 md:order-4">
          <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
            <Link
              href={href}
              // The name stretches over the row, so the row draws the focus outline (the global recipe).
              className="truncate text-sm font-semibold after:absolute after:inset-0 after:rounded-xl hover:underline focus-visible:outline-none focus-visible:after:outline-2 focus-visible:after:outline-offset-2 focus-visible:after:outline-brand"
            >
              {name}
            </Link>
            {automation.display_status === "draft" ? (
              <span className="rounded-full bg-raised px-2 py-0.5 text-2xs font-medium text-fg-secondary">
                {STATUS_LABEL.draft}
              </span>
            ) : null}
            {status ? <span className="text-xs text-fg-secondary">{status}</span> : null}
            {queue ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-brand-soft px-2 py-0.5 text-2xs font-medium text-brand-fg tabular-nums">
                <Clock className="size-3" aria-hidden />
                {queue}
              </span>
            ) : null}
          </div>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs text-fg-secondary">
            <span className="inline-flex items-center gap-1">
              <TriggerIcon className="size-3.5" aria-hidden />
              {triggerSummary(automation)}
            </span>
            {chips.length > 0 ? (
              <span data-testid="keyword-chips" className="flex flex-wrap items-center gap-1">
                <span className="sr-only">Keywords: {automation.keywords.join(", ")}</span>
                {chips.map((keyword) => (
                  <span key={keyword} aria-hidden className="rounded-full bg-field px-2 py-0.5 text-fg">
                    {keyword}
                  </span>
                ))}
                {more > 0 ? (
                  <span aria-hidden className="px-1">
                    +{more}
                  </span>
                ) : null}
              </span>
            ) : null}
            {action ? (
              <span className="inline-flex items-center gap-1 rounded-full border border-line px-2 py-0.5 text-fg">
                {automation.action === "ai_reply" ? <Sparkles className="size-3 text-brand-fg" aria-hidden /> : null}
                {action}
              </span>
            ) : null}
          </div>
        </div>

        <div className="order-last flex w-full items-center gap-4 md:order-5 md:w-auto">
          <div className="flex items-center gap-2">
            <TrendLine values={automation.stats.daily_7d} />
            <p className="text-xs whitespace-nowrap">
              <span className="font-medium text-fg tabular-nums">
                {formatCount(automation.stats.runs_7d)} {automation.stats.runs_7d === 1 ? "run" : "runs"}
              </span>
              <span className="text-fg-secondary"> in 7 days</span>
            </p>
          </div>
          <p className="ml-auto text-xs whitespace-nowrap text-fg-secondary md:ml-0 md:w-20 md:text-right">
            {lastRunText(automation.stats.last_run_at ?? automation.last_run_at, now)}
          </p>
        </div>

        <div className="relative z-10 order-4 md:order-6">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button ref={menuTrigger} variant="ghost" size="icon-lg" aria-label={`More actions for ${name}`}>
                <EllipsisVertical aria-hidden />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onSelect={onDuplicate}>
                <Copy aria-hidden /> Duplicate
              </DropdownMenuItem>
              <DropdownMenuItem disabled={statusPending} onSelect={() => onActiveChange(!active)}>
                {active ? <Pause aria-hidden /> : <Play aria-hidden />} {active ? "Pause" : resumeLabel}
              </DropdownMenuItem>
              {reorder ? (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem disabled={!reorder.canMoveUp} onSelect={() => reorder.onMove(-1)}>
                    <ArrowUp aria-hidden /> Move up
                  </DropdownMenuItem>
                  <DropdownMenuItem disabled={!reorder.canMoveDown} onSelect={() => reorder.onMove(1)}>
                    <ArrowDown aria-hidden /> Move down
                  </DropdownMenuItem>
                </>
              ) : null}
              <DropdownMenuSeparator />
              <DropdownMenuItem variant="destructive" onSelect={() => setConfirmDelete(true)}>
                <Trash2 aria-hidden /> Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <AlertDialogContent
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            menuTrigger.current?.focus();
          }}
        >
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {name}?</AlertDialogTitle>
            <AlertDialogDescription>
              It stops answering at once and can&apos;t be restored. Messages it already sent stay in the inbox.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={onDelete}>
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </li>
  );
}
