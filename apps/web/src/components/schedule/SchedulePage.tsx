"use client";

import { ChevronLeft, ChevronRight, ListFilter, ListPlus, PanelRight, Plus } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useMemo, useState } from "react";
import { toast } from "sonner";

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
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useSocialAccounts } from "@/lib/api/queries";
import {
  useCalendar,
  useCreateScheduledPost,
  useDeleteScheduledPost,
  useDuplicateScheduledPost,
  useQueuePost,
  useReschedulePost,
  useSchedulePost,
  useScheduledPostList,
  useUnschedulePost,
} from "@/lib/api/queries/calendar";
import type { ScheduledPostSummary, ScheduledPostView } from "@/lib/api/types";
import { accountLabel, instagramAccounts } from "@/lib/automations/accounts";
import { isPlanLimitError } from "@/lib/api/errors";
import { emptyStates, errorMessage } from "@/lib/copy";
import { toastError } from "@/lib/toast-error";
import {
  CALENDAR_VIEWS,
  instantAt,
  rangeFor,
  rangeLabel,
  shiftAnchor,
  shortDay,
  todayKey,
  TOO_SOON_MESSAGE,
  tooSoon,
  withTimeOf,
  zoneLabel,
  type CalendarView,
} from "@/lib/schedule/dates";
import {
  accountColors,
  captionLine,
  firstProblem,
  lockedMessage,
  moveErrorMessage,
  needsComposer,
  POST_STATUS,
  STATUS_GROUPS,
} from "@/lib/schedule/format";
import { formatDayTime } from "@/lib/tz";
import { useMediaQuery, useNow, useStoredString } from "@/lib/use-browser-state";
import { cn } from "@/lib/utils";
import { useCurrentWorkspace } from "@/lib/workspace";

import { AgendaView } from "./AgendaView";
import { CalendarDndProvider, type DragSource, type DropTarget } from "./calendar-dnd";
import { HashtagGroupsDialog } from "./HashtagGroupsDialog";
import { ListView } from "./ListView";
import { MonthView } from "./MonthView";
import { MoveToDialog, type MoveRequest } from "./MoveToDialog";
import { AccountAvatar } from "./post-parts";
import { PostingTimesDrawer } from "./PostingTimesDrawer";
import { ScheduleProvider, type PostActions, type ScheduleContextValue } from "./schedule-context";
import { ScheduleRail } from "./ScheduleRail";
import { WeekView } from "./WeekView";

const VIEW_KEY = "socialhood:schedule-view";
const VIEW_LABEL: Record<CalendarView, string> = { month: "Month", week: "Week", list: "List" };
const ALL_GROUPS = new Set<ScheduledPostView>(STATUS_GROUPS.map((g) => g.value));

/** UX-SCR-04 / FR-PUB-08: the Schedule page. Owners and admins only (§2.15). */
export function SchedulePage({ now }: { now?: Date } = {}) {
  const workspace = useCurrentWorkspace();
  if (workspace.role === "agent") {
    return (
      <EmptyState
        className="min-h-[60vh]"
        title="Schedule is for owners and admins"
        body="Ask an owner or admin of this workspace to plan posts."
        action={
          <Link href={`/w/${workspace.slug}/home` as Route} className="text-sm text-brand-fg underline-offset-4 hover:underline">
            Go to Home
          </Link>
        }
      />
    );
  }
  return <ScheduleScreen fixedNow={now} />;
}

function ScheduleScreen({ fixedNow }: { fixedNow?: Date }) {
  const workspace = useCurrentWorkspace();
  const wid = workspace.id;
  const router = useRouter();
  const liveNow = useNow();
  const now = fixedNow ?? liveNow;
  const clock = useCallback(() => fixedNow ?? new Date(), [fixedNow]);

  const phone = !useMediaQuery("(min-width: 768px)");
  const wide = useMediaQuery("(min-width: 1440px)");

  // ---- view and range (UX-SCR-04: the view is remembered per browser)
  const [storedView, setView] = useStoredString<CalendarView>(VIEW_KEY, "week");
  const view: CalendarView = (CALENDAR_VIEWS as readonly string[]).includes(storedView) ? (storedView as CalendarView) : "week";
  const [anchor, setAnchor] = useState(() => todayKey(now, workspace.timezone));
  const [listTab, setListTab] = useState<ScheduledPostView>("scheduled");
  const range = rangeFor(view === "month" ? "month" : "week", anchor);

  // ---- data
  const allAccounts = useSocialAccounts(wid);
  const accounts = useMemo(() => instagramAccounts(allAccounts.data ?? []), [allAccounts.data]);
  // Read in the List view too: the right rail's figures come from it.
  const calendar = useCalendar(wid, range.from, range.to);
  const drafts = useScheduledPostList(wid, "drafts");
  const timeZone = calendar.data?.timezone ?? workspace.timezone;

  // ---- filters (FR-PUB-08: accounts and status; the Messages layer)
  const [hidden, setHidden] = useState<Set<string>>(() => new Set());
  const [groups, setGroups] = useState<Set<ScheduledPostView>>(() => new Set(ALL_GROUPS));
  const [showMessages, setShowMessages] = useState(true);
  const [showSlots, setShowSlots] = useState(true);

  const posts = useMemo(
    () =>
      (calendar.data?.posts ?? []).filter(
        (post) =>
          groups.has(POST_STATUS[post.status].group) &&
          (post.targets.length === 0 || post.targets.some((t) => !hidden.has(t.social_account_id))),
      ),
    [calendar.data, groups, hidden],
  );
  const messages = useMemo(
    () => (showMessages ? (calendar.data?.messages ?? []).filter((m) => !hidden.has(m.social_account_id)) : []),
    [calendar.data, showMessages, hidden],
  );
  const slots = useMemo(
    () => (showSlots ? (calendar.data?.slots ?? []).filter((s) => !hidden.has(s.social_account_id)) : []),
    [calendar.data, showSlots, hidden],
  );
  const listAccounts = hidden.size > 0 ? accounts.filter((a) => !hidden.has(a.id)).map((a) => a.id) : null;

  // ---- dialogs
  const [railOpen, setRailOpen] = useState(false);
  const [postingOpen, setPostingOpen] = useState(false);
  const [hashtagsOpen, setHashtagsOpen] = useState(false);
  // Move to… stays mounted and keeps its last request while it closes (its exit plays).
  const [moveRequest, setMoveRequest] = useState<MoveRequest | null>(null);
  const [moveOpen, setMoveOpen] = useState(false);
  const openMove = (request: MoveRequest) => {
    setMoveRequest(request);
    setMoveOpen(true);
  };
  const [deleteRequest, setDeleteRequest] = useState<MoveRequest | null>(null);
  const [announcement, setAnnouncement] = useState("");

  // ---- mutations
  const create = useCreateScheduledPost(wid);
  const reschedule = useReschedulePost(wid);
  const scheduleDraft = useSchedulePost(wid);
  const queue = useQueuePost(wid);
  const unschedule = useUnschedulePost(wid);
  const duplicate = useDuplicateScheduledPost(wid);
  const remove = useDeleteScheduledPost(wid);

  const composerHref = useCallback(
    (post: Pick<ScheduledPostSummary, "id">) => `/w/${workspace.slug}/schedule/${post.id}` as Route,
    [workspace.slug],
  );
  const openComposer = useCallback(
    (post: Pick<ScheduledPostSummary, "id">, query = "") => router.push(`${composerHref(post)}${query}` as Route),
    [composerHref, router],
  );
  const say = (message: string) => setAnnouncement(message);

  /** A move or schedule the API accepted; a refusal puts the card back (F-13 "Calendar moves"). */
  const move = (post: ScheduledPostSummary, at: Date): Promise<string | null> => {
    const when = formatDayTime(at, timeZone, now);
    if (post.status === "draft") {
      return scheduleDraft
        .mutateAsync({ post, publishAt: at.toISOString() })
        .then(() => {
          toast.success(`Scheduled for ${when}`);
          say(`${captionLine(post.caption)} scheduled for ${when}.`);
          return null;
        })
        .catch((error: unknown) => {
          // Over the plan's scheduled posts (402): the card goes back and the upgrade dialog says why.
          if (isPlanLimitError(error)) return null;
          if (!needsComposer(error)) return moveErrorMessage(error);
          // Not ready: the composer opens with its failing checklist items (F-13).
          toast.error("Finish this post to schedule it. The checklist shows what's missing.");
          openComposer(post);
          return null;
        });
    }
    return reschedule
      .mutateAsync({ post, publishAt: at.toISOString() })
      .then(() => {
        toast.success(`Moved to ${when}`);
        say(`${captionLine(post.caption)} moved to ${when}.`);
        return null;
      })
      .catch((error: unknown) => (isPlanLimitError(error) ? null : moveErrorMessage(error)));
  };

  /** Where a drop lands: the target time, or the post's own time on another day (Month). */
  const dropTime = (post: ScheduledPostSummary, target: DropTarget): Date | null => {
    if (target.minutes !== null) return instantAt(target.day, target.minutes, timeZone);
    return post.publish_at ? withTimeOf(target.day, post.publish_at, timeZone) : null;
  };

  const onDrop = (source: DragSource, target: DropTarget) => {
    const { post } = source;
    const at = dropTime(post, target);
    if (!at) {
      openMove({ post, day: target.day });
      return;
    }
    if (post.publish_at && new Date(post.publish_at).getTime() === at.getTime() && post.status === "scheduled") return;
    if (tooSoon(at, clock())) {
      toast.error(TOO_SOON_MESSAGE);
      say(`Not moved. ${TOO_SOON_MESSAGE}`);
      return;
    }
    void move(post, at).then((problem) => {
      if (problem) {
        toast.error(problem);
        say(`Not moved. ${problem}`);
      }
    });
  };

  const describeDrag = (source: DragSource, target: DropTarget | null) => {
    if (!target) return { text: `${captionLine(source.post.caption)}: drop on the calendar`, ok: true };
    const at = dropTime(source.post, target);
    if (!at) return { text: `${shortDay(target.day)}: pick a time next`, ok: true };
    if (tooSoon(at, clock())) return { text: TOO_SOON_MESSAGE, ok: false };
    return { text: formatDayTime(at, timeZone, now), ok: true };
  };

  const onLocked = (post: ScheduledPostSummary) => {
    toast.error(lockedMessage(post));
    say(lockedMessage(post));
  };

  const newPost = (at: Date | null, query = "") => {
    if (create.isPending) return;
    create.mutate(
      { publishAt: at ? at.toISOString() : null },
      {
        onSuccess: (post) => openComposer(post, query),
        onError: (error) => toast.error(errorMessage(error)),
      },
    );
  };

  const actions: PostActions = {
    moveTo: (post, returnFocus, day) => openMove({ post, returnFocus, day }),
    queue: (post) =>
      queue.mutate(post, {
        onSuccess: (saved) => {
          const when = saved.publish_at ? formatDayTime(saved.publish_at, timeZone, now) : "the next free time";
          toast.success(`Added to the queue for ${when}`);
          say(`${captionLine(post.caption)} added to the queue for ${when}.`);
        },
        onError: (error) => {
          if (needsComposer(error, ["publish_at", "targets"])) {
            toast.error("Finish this post to schedule it. The checklist shows what's missing.");
            openComposer(post);
          } else toastError(error, firstProblem(error));
        },
      }),
    unschedule: (post) =>
      unschedule.mutate(post, {
        onSuccess: () => toast.success("Moved to drafts. It keeps its time."),
        onError: (error) => toast.error(moveErrorMessage(error)),
      }),
    duplicate: (post) =>
      duplicate.mutate(post, {
        onSuccess: (copy) =>
          toast.success("Duplicated as a draft", { action: { label: "Open", onClick: () => openComposer(copy) } }),
        onError: (error) => toast.error(errorMessage(error)),
      }),
    remove: (post, returnFocus) => setDeleteRequest({ post, returnFocus }),
    newPostAt: (at) => newPost(at),
  };

  const busyIds = new Set<string>(
    [
      reschedule.isPending ? reschedule.variables?.post.id : undefined,
      scheduleDraft.isPending ? scheduleDraft.variables?.post.id : undefined,
      queue.isPending ? queue.variables?.id : undefined,
      unschedule.isPending ? unschedule.variables?.id : undefined,
      remove.isPending ? remove.variables?.id : undefined,
    ].filter((id): id is string => Boolean(id)),
  );

  const context: ScheduleContextValue = {
    wid,
    slug: workspace.slug,
    timeZone,
    now,
    accounts: new Map((allAccounts.data ?? []).map((a) => [a.id, a])),
    colors: accountColors(accounts),
    actions,
    composerHref,
    busyIds,
  };

  const today = todayKey(now, timeZone);
  const unit = view === "month" ? "month" : "week";
  const hiddenCount = ALL_GROUPS.size - groups.size + (showMessages ? 0 : 1) + (showSlots ? 0 : 1);
  const draftCount = drafts.data?.pages[0]?.items.length ?? 0;
  const emptyRange =
    calendar.isSuccess && calendar.data.posts.length === 0 && drafts.isSuccess && draftCount === 0;

  const rail = (inline: boolean) => (
    <ScheduleRail
      calendar={calendar.data}
      drafts={drafts}
      accounts={accounts}
      dragEnabled={inline && !phone}
      onEditPostingTimes={() => {
        setRailOpen(false);
        setPostingOpen(true);
      }}
      onHashtagGroups={() => {
        setRailOpen(false);
        setHashtagsOpen(true);
      }}
      onShowAllDrafts={() => {
        setRailOpen(false);
        setListTab("drafts");
        setView("list");
      }}
    />
  );

  let main;
  if (view === "list") {
    main = <ListView accountIds={listAccounts} tab={listTab} onTabChange={setListTab} />;
  } else if (calendar.isPending) {
    main = <CalendarSkeleton />;
  } else if (calendar.isError && !calendar.data) {
    main = <ErrorState error={calendar.error} onRetry={() => void calendar.refetch()} />;
  } else if (phone) {
    main = <AgendaView days={range.days} posts={posts} messages={messages} />;
  } else if (view === "month") {
    main = (
      <MonthView
        anchor={anchor}
        days={range.days}
        posts={posts}
        messages={messages}
        onOpenWeek={(day) => {
          setAnchor(day);
          setView("week");
        }}
      />
    );
  } else {
    main = <WeekView days={range.days} posts={posts} messages={messages} slots={slots} />;
  }

  return (
    <ScheduleProvider value={context}>
      <CalendarDndProvider enabled={!phone} onDrop={onDrop} onLocked={onLocked} describe={describeDrag}>
        <div className="w-full p-4 md:p-6">
          <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">Schedule</h1>
              <p className="text-xs text-fg-secondary">Times in {zoneLabel(timeZone)}</p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                className="min-h-10 md:min-h-8"
                onClick={() => newPost(null, "?when=queue")}
                disabled={create.isPending}
              >
                <ListPlus aria-hidden /> Add to queue
              </Button>
              <Button
                className="min-h-10 bg-brand-gradient text-white md:min-h-8"
                onClick={() => newPost(null)}
                disabled={create.isPending}
              >
                <Plus aria-hidden /> New post
              </Button>
            </div>
          </header>

          <div className="mb-3 flex flex-wrap items-center gap-2">
            <ToggleGroup value={view} onValueChange={(value) => setView(value as CalendarView)} aria-label="View" className="w-auto">
              {CALENDAR_VIEWS.map((value) => (
                <ToggleGroupItem key={value} value={value} className="min-h-10 px-3 md:min-h-7">
                  {VIEW_LABEL[value]}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>

            {view !== "list" ? (
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-10 md:size-8"
                  aria-label={`Previous ${unit}`}
                  onClick={() => setAnchor(shiftAnchor(view, anchor, -1))}
                >
                  <ChevronLeft aria-hidden />
                </Button>
                <span className="min-w-28 text-center text-sm font-medium tabular-nums" aria-live="polite">
                  {rangeLabel(view, anchor, today)}
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-10 md:size-8"
                  aria-label={`Next ${unit}`}
                  onClick={() => setAnchor(shiftAnchor(view, anchor, 1))}
                >
                  <ChevronRight aria-hidden />
                </Button>
                <Button variant="secondary" size="sm" className="min-h-10 md:min-h-7" onClick={() => setAnchor(today)}>
                  Today
                </Button>
              </div>
            ) : null}

            {accounts.length > 1 ? (
              <div role="group" aria-label="Accounts" className="flex items-center gap-1">
                {accounts.map((account) => {
                  const shown = !hidden.has(account.id);
                  return (
                    <button
                      key={account.id}
                      type="button"
                      aria-pressed={shown}
                      aria-label={accountLabel(account)}
                      title={accountLabel(account)}
                      onClick={() =>
                        setHidden((current) => {
                          const next = new Set(current);
                          if (shown) next.add(account.id);
                          else next.delete(account.id);
                          return next;
                        })
                      }
                      className={cn(
                        "grid size-10 place-items-center rounded-full transition-opacity md:size-8",
                        !shown && "opacity-40 grayscale",
                      )}
                    >
                      <AccountAvatar account={account} accountId={account.id} />
                    </button>
                  );
                })}
              </div>
            ) : null}

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="secondary" size="sm" className="min-h-10 md:min-h-7">
                  <ListFilter aria-hidden />
                  {hiddenCount > 0 ? `Show (${hiddenCount} hidden)` : "Show"}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-56 border-line bg-panel shadow-xl">
                <DropdownMenuLabel className="text-xs text-fg-secondary">Posts</DropdownMenuLabel>
                {STATUS_GROUPS.map((group) => (
                  <DropdownMenuCheckboxItem
                    key={group.value}
                    checked={groups.has(group.value)}
                    onSelect={(event) => event.preventDefault()}
                    onCheckedChange={(checked) =>
                      setGroups((current) => {
                        const next = new Set(current);
                        if (checked) next.add(group.value);
                        else next.delete(group.value);
                        return next;
                      })
                    }
                  >
                    {group.label}
                  </DropdownMenuCheckboxItem>
                ))}
                <DropdownMenuSeparator />
                <DropdownMenuLabel className="text-xs text-fg-secondary">Layers</DropdownMenuLabel>
                <DropdownMenuCheckboxItem
                  checked={showMessages}
                  onSelect={(event) => event.preventDefault()}
                  onCheckedChange={(checked) => setShowMessages(checked === true)}
                >
                  Scheduled DMs
                </DropdownMenuCheckboxItem>
                <DropdownMenuCheckboxItem
                  checked={showSlots}
                  onSelect={(event) => event.preventDefault()}
                  onCheckedChange={(checked) => setShowSlots(checked === true)}
                >
                  Free queue times
                </DropdownMenuCheckboxItem>
              </DropdownMenuContent>
            </DropdownMenu>

            {!wide ? (
              <Button variant="secondary" size="sm" className="ml-auto min-h-10 md:min-h-7" onClick={() => setRailOpen(true)}>
                <PanelRight aria-hidden /> Drafts and queue
              </Button>
            ) : null}
          </div>

          {emptyRange && view !== "list" ? (
            <EmptyState
              className="mb-3 rounded-xl border border-line bg-panel py-6"
              {...emptyStates.schedule}
              action={
                <Button className="min-h-10 bg-brand-gradient text-white md:min-h-8" onClick={() => newPost(null)}>
                  New post
                </Button>
              }
            />
          ) : null}

          <div className="flex gap-4">
            <div className="min-w-0 flex-1">{main}</div>
            {wide ? (
              <aside aria-label="Drafts and queue" className="w-[250px] shrink-0">
                {rail(true)}
              </aside>
            ) : null}
          </div>
        </div>

        {!wide ? (
          <Sheet open={railOpen} onOpenChange={setRailOpen}>
            <SheetContent side="right" className="w-[300px] overflow-y-auto border-line bg-panel sm:max-w-[300px]">
              <SheetHeader className="px-0 pt-0">
                <SheetTitle className="text-base font-semibold">Drafts and queue</SheetTitle>
                <SheetDescription className="text-fg-secondary">
                  Schedule a draft from its menu, or add it to the queue.
                </SheetDescription>
              </SheetHeader>
              {rail(false)}
            </SheetContent>
          </Sheet>
        ) : null}

        <PostingTimesDrawer open={postingOpen} onOpenChange={setPostingOpen} accounts={accounts} />
        <HashtagGroupsDialog open={hashtagsOpen} onOpenChange={setHashtagsOpen} />

        <MoveToDialog
          open={moveOpen}
          request={moveRequest}
          timeZone={timeZone}
          now={clock()}
          onClose={() => setMoveOpen(false)}
          onMove={async (at) => {
            if (!moveRequest) return null;
            const problem = await move(moveRequest.post, at);
            if (!problem) setMoveOpen(false);
            return problem;
          }}
        />

        <AlertDialog open={Boolean(deleteRequest)} onOpenChange={(open) => (open ? undefined : setDeleteRequest(null))}>
          <AlertDialogContent
            className="border-line bg-panel"
            onCloseAutoFocus={(event) => {
              if (deleteRequest?.returnFocus?.isConnected) {
                event.preventDefault();
                deleteRequest.returnFocus.focus();
              }
            }}
          >
            <AlertDialogHeader>
              <AlertDialogTitle>Delete this post?</AlertDialogTitle>
              <AlertDialogDescription className="text-fg-secondary">
                {deleteRequest ? deleteDescription(deleteRequest.post) : null}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Keep post</AlertDialogCancel>
              <AlertDialogAction
                className="bg-danger-fill text-white hover:bg-danger-fill/90"
                onClick={() => {
                  const post = deleteRequest?.post;
                  if (!post) return;
                  remove.mutate(post, {
                    onSuccess: () => toast.success("Post deleted"),
                    onError: (error) => toast.error(moveErrorMessage(error)),
                  });
                }}
              >
                Delete post
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        <p role="status" aria-live="polite" className="sr-only">
          {announcement}
        </p>
      </CalendarDndProvider>
    </ScheduleProvider>
  );
}

function deleteDescription(post: ScheduledPostSummary): string {
  switch (post.status) {
    case "scheduled":
      return `"${captionLine(post.caption)}" won't be published.`;
    case "published":
    case "partially_published":
      return "It stays on Instagram and in Comments.";
    case "failed":
    case "canceled":
      return "It won't be retried.";
    default:
      return `The draft "${captionLine(post.caption)}" is removed.`;
  }
}

function CalendarSkeleton() {
  return (
    <div className="space-y-2 rounded-xl border border-line bg-panel p-3" aria-busy="true" aria-label="Loading the calendar">
      <Skeleton className="h-6 w-full bg-raised" />
      {Array.from({ length: 6 }, (_, i) => (
        <Skeleton key={i} className="h-16 w-full bg-raised" />
      ))}
    </div>
  );
}
