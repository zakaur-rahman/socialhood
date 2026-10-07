"use client";

import { Clock, Trash2, Undo2, X } from "lucide-react";
import Link from "next/link";
import { useRef, useState, type FormEvent } from "react";
import { toast } from "sonner";

import { useReturnFocus } from "@/components/agent/use-return-focus";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
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
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useBulkScheduledPosts, useScheduledPostList } from "@/lib/api/queries/calendar";
import type { BulkScheduledPostRequest, ScheduledPostSummary, ScheduledPostView } from "@/lib/api/types";
import { emptyStates } from "@/lib/copy";
import { bulkResultMessage, captionLine, STATUS_GROUPS } from "@/lib/schedule/format";
import { toastError } from "@/lib/toast-error";
import { formatDayTime } from "@/lib/tz";
import { cn } from "@/lib/utils";

import { postLabel } from "./CalendarPostCard";
import { PostMenu, PostThumbnail, StatusChip, TargetAvatars } from "./post-parts";
import { useSchedule } from "./schedule-context";

const EMPTY: Record<ScheduledPostView, { title: string; body: string }> = {
  scheduled: emptyStates.schedule,
  drafts: { title: "No drafts", body: "Posts you start and don't schedule wait here." },
  published: { title: "Nothing published yet", body: "Posts appear here once Instagram publishes them." },
  failed: { title: "No failed posts", body: "If Instagram refuses a post, it shows here with the reason." },
};

/**
 * UX-SCR-04 List: tabs Scheduled, Drafts, Published and Failed; rows with a 48 px thumbnail,
 * caption, accounts, time and status; checkboxes for bulk shift, unschedule and delete (FR-PUB-14).
 */
export function ListView({
  accountIds,
  tab,
  onTabChange,
}: {
  accountIds: string[] | null;
  tab: ScheduledPostView;
  onTabChange: (tab: ScheduledPostView) => void;
}) {
  const schedule = useSchedule();
  const [selected, setSelected] = useState<Set<string>>(() => new Set());
  const [shifting, setShifting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const list = useScheduledPostList(schedule.wid, tab, accountIds);
  const bulk = useBulkScheduledPosts(schedule.wid);
  const items = list.data?.pages.flatMap((page) => page.items) ?? [];
  const chosen = items.filter((post) => selected.has(post.id));
  const selectAll = useRef<HTMLButtonElement>(null);

  /**
   * The bulk toolbar goes away with the selection, taking the focused button with it. Focus then
   * falls back to Select all, so the keyboard keeps its place (UX-A11Y-02).
   */
  const toSelectAllIfLost = () => {
    if (!document.activeElement || document.activeElement === document.body) selectAll.current?.focus();
  };
  const clearSelection = () => {
    setSelected(new Set());
    requestAnimationFrame(toSelectAllIfLost);
  };
  /** A bulk dialog closing: back to the button that opened it, or to Select all once that is gone. */
  const returnFocus = useReturnFocus();
  const dialogFocus = {
    onOpenAutoFocus: returnFocus.onOpenAutoFocus,
    onCloseAutoFocus: (event: Event) => {
      returnFocus.onCloseAutoFocus(event);
      toSelectAllIfLost();
    },
  };

  const changeTab = (value: string) => {
    onTabChange(value as ScheduledPostView);
    setSelected(new Set());
  };
  const toggle = (id: string, on: boolean) =>
    setSelected((current) => {
      const next = new Set(current);
      if (on) next.add(id);
      else next.delete(id);
      return next;
    });

  const run = (body: Omit<BulkScheduledPostRequest, "ids">, done?: () => void) =>
    bulk.mutate(
      { ...body, ids: chosen.map((post) => post.id) },
      {
        onSuccess: (result) => {
          const { message, skipped } = bulkResultMessage(body.action, result);
          toast.success(message);
          if (skipped) toast(skipped);
          clearSelection();
          done?.();
        },
        onError: (error) => toastError(error),
      },
    );

  let content;
  if (list.isPending) content = <ListSkeleton />;
  else if (list.isError) content = <ErrorState error={list.error} onRetry={() => void list.refetch()} />;
  else if (items.length === 0) {
    content = (
      <EmptyState
        className="rounded-xl border border-line bg-panel"
        {...EMPTY[tab]}
        action={
          tab === "scheduled" ? <Button onClick={() => schedule.actions.newPostAt(null)}>New post</Button> : undefined
        }
      />
    );
  } else {
    const allChosen = chosen.length === items.length;
    content = (
      <div className="space-y-3">
        <div className="flex min-h-10 flex-wrap items-center gap-2 px-1">
          <label className="flex min-h-8 items-center gap-2 text-sm text-fg-secondary">
            <Checkbox
              ref={selectAll}
              checked={allChosen ? true : chosen.length > 0 ? "indeterminate" : false}
              onCheckedChange={(value) => setSelected(value === true ? new Set(items.map((p) => p.id)) : new Set())}
              aria-label="Select all posts"
            />
            {chosen.length > 0 ? `${chosen.length} selected` : "Select all"}
          </label>
          {chosen.length > 0 ? (
            <div role="toolbar" aria-label="Bulk actions" className="ml-auto flex flex-wrap items-center gap-1">
              {tab === "scheduled" ? (
                <>
                  <Button variant="secondary" size="sm" onClick={() => setShifting(true)} disabled={bulk.isPending}>
                    <Clock aria-hidden /> Shift times
                  </Button>
                  <Button variant="secondary" size="sm" onClick={() => run({ action: "unschedule" })} disabled={bulk.isPending}>
                    <Undo2 aria-hidden /> Move to drafts
                  </Button>
                </>
              ) : null}
              {/* Opens the confirmation, so it is the destructive trigger, not the destructive action. */}
              <Button variant="destructive-ghost" size="sm" onClick={() => setConfirmDelete(true)} disabled={bulk.isPending}>
                <Trash2 aria-hidden /> Delete
              </Button>
              <Button variant="ghost" size="icon-sm" aria-label="Clear selection" onClick={clearSelection}>
                <X aria-hidden />
              </Button>
            </div>
          ) : null}
        </div>
        <ul aria-label={`${STATUS_GROUPS.find((g) => g.value === tab)?.label} posts`} className="divide-y divide-line-subtle overflow-hidden rounded-xl border border-line bg-panel">
          {items.map((post) => (
            <ListRow key={post.id} post={post} selected={selected.has(post.id)} onSelectedChange={(on) => toggle(post.id, on)} />
          ))}
        </ul>
        {list.hasNextPage ? (
          <div className="flex justify-center">
            <Button variant="secondary" onClick={() => void list.fetchNextPage()} disabled={list.isFetchingNextPage}>
              {list.isFetchingNextPage ? "Loading…" : "Show more posts"}
            </Button>
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <Tabs value={tab} onValueChange={changeTab}>
        <TabsList className="w-full md:w-auto md:self-start">
          {STATUS_GROUPS.map((group) => (
            <TabsTrigger key={group.value} value={group.value}>
              {group.label}
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value={tab}>{content}</TabsContent>
      </Tabs>
      <ShiftDialog
        open={shifting}
        onOpenChange={setShifting}
        count={chosen.length}
        pending={bulk.isPending}
        focus={dialogFocus}
        onShift={(minutes) => run({ action: "shift", shift_minutes: minutes }, () => setShifting(false))}
      />
      <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <AlertDialogContent {...dialogFocus}>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Delete {chosen.length} {chosen.length === 1 ? "post" : "posts"}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              Scheduled posts won&apos;t be published. Published posts stay on Instagram and in Comments.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep them</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={() => run({ action: "delete" })}>
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function ListRow({
  post,
  selected,
  onSelectedChange,
}: {
  post: ScheduledPostSummary;
  selected: boolean;
  onSelectedChange: (selected: boolean) => void;
}) {
  const schedule = useSchedule();
  const { timeZone, now } = schedule;
  const when = post.status === "published" || post.status === "partially_published" ? (post.published_at ?? post.publish_at) : post.publish_at;
  const failure = post.targets.find((target) => target.error)?.error?.message;
  return (
    <li data-post-id={post.id} className={cn("flex items-center gap-3 px-3 py-2.5", selected && "bg-raised")}>
      <Checkbox
        checked={selected}
        onCheckedChange={(value) => onSelectedChange(value === true)}
        aria-label={`Select ${captionLine(post.caption)}`}
        className="after:-inset-3"
      />
      <Link href={schedule.composerHref(post)} aria-label={postLabel(post, timeZone, now)} className="flex min-w-0 flex-1 items-center gap-3">
        <PostThumbnail post={post} size={48} />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium">{captionLine(post.caption)}</span>
          <span className="block text-xs text-fg-secondary tabular-nums">
            {when ? formatDayTime(when, timeZone, now) : "No time yet"}
          </span>
          {failure ? <span className="block truncate text-xs text-danger-fg">{failure}</span> : null}
        </span>
      </Link>
      <span className="hidden sm:flex">
        <TargetAvatars post={post} />
      </span>
      <StatusChip post={post} className="hidden sm:inline-flex" />
      <PostMenu post={post} size="lg" />
    </li>
  );
}

function ListSkeleton() {
  return (
    <ul aria-busy="true" aria-label="Loading posts" className="divide-y divide-line-subtle rounded-xl border border-line bg-panel">
      {Array.from({ length: 4 }, (_, i) => (
        <li key={i} className="flex items-center gap-3 px-3 py-2.5">
          <Skeleton className="size-12 rounded-lg" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3 w-1/3" />
            <Skeleton className="h-3 w-1/5" />
          </div>
        </li>
      ))}
    </ul>
  );
}

const UNITS = [
  { value: "minutes", label: "minutes", factor: 1 },
  { value: "hours", label: "hours", factor: 60 },
  { value: "days", label: "days", factor: 24 * 60 },
] as const;

/**
 * FR-PUB-14: move the selected posts later or earlier by the same amount. Opened from Shift times,
 * so focus goes back there when it closes, or to Select all once a shift has cleared the selection
 * (UX-A11Y-02; `focus` from ListView).
 */
function ShiftDialog({
  open,
  onOpenChange,
  count,
  pending,
  focus,
  onShift,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  count: number;
  pending: boolean;
  focus: { onOpenAutoFocus: () => void; onCloseAutoFocus: (event: Event) => void };
  onShift: (minutes: number) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="md" {...focus}>
        <ShiftForm count={count} pending={pending} onCancel={() => onOpenChange(false)} onShift={onShift} />
      </DialogContent>
    </Dialog>
  );
}

/** Inside the dialog's content, so each opening starts from 1 hour later. */
function ShiftForm({
  count: selectedCount,
  pending,
  onCancel,
  onShift,
}: {
  count: number;
  pending: boolean;
  onCancel: () => void;
  onShift: (minutes: number) => void;
}) {
  // A successful shift clears the selection; the dialog keeps the number it showed while it closes.
  const [count] = useState(selectedCount);
  const [amount, setAmount] = useState("1");
  const [unit, setUnit] = useState<(typeof UNITS)[number]["value"]>("hours");
  const [direction, setDirection] = useState<"later" | "earlier">("later");
  const [error, setError] = useState<string | null>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const value = Number(amount);
    if (!Number.isInteger(value) || value <= 0) return setError("Enter a whole number above 0.");
    const minutes = value * UNITS.find((u) => u.value === unit)!.factor * (direction === "later" ? 1 : -1);
    if (Math.abs(minutes) > 525_600) return setError("Shift by at most a year.");
    setError(null);
    onShift(minutes);
  };

  return (
    <form onSubmit={submit} className="grid gap-4">
      <DialogHeader>
        <DialogTitle>Shift times</DialogTitle>
        <DialogDescription>
          Move {count} {count === 1 ? "post" : "posts"} by the same amount. Posts that would land less than 5
          minutes from now stay where they are.
        </DialogDescription>
      </DialogHeader>
      <div className="grid grid-cols-3 gap-2">
        <div className="space-y-1">
          <Label htmlFor="shift-amount" className="text-xs text-fg-secondary">
            Amount
          </Label>
          <Input
            id="shift-amount"
            size="lg"
            inputMode="numeric"
            value={amount}
            aria-invalid={Boolean(error)}
            onChange={(event) => setAmount(event.target.value)}
            className="tabular-nums"
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="shift-unit" className="text-xs text-fg-secondary">
            Unit
          </Label>
          <Select value={unit} onValueChange={(value) => setUnit(value as typeof unit)}>
            <SelectTrigger id="shift-unit" size="lg" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {UNITS.map((u) => (
                <SelectItem key={u.value} value={u.value}>
                  {u.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="shift-direction" className="text-xs text-fg-secondary">
            Direction
          </Label>
          <Select value={direction} onValueChange={(value) => setDirection(value as typeof direction)}>
            <SelectTrigger id="shift-direction" size="lg" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="later">Later</SelectItem>
              <SelectItem value="earlier">Earlier</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      {error ? (
        <p role="alert" className="text-xs text-danger-fg">
          {error}
        </p>
      ) : null}
      <DialogFooter>
        <Button type="button" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={pending}>
          Shift {count} {count === 1 ? "post" : "posts"}
        </Button>
      </DialogFooter>
    </form>
  );
}
