"use client";

import { useQueryClient } from "@tanstack/react-query";
import type { Route } from "next";
import Link from "next/link";
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo, useRef, useState, type ReactNode } from "react";
import { toast } from "sonner";

import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { Button } from "@/components/ui/button";
import { TOAST_ACTION_DURATION } from "@/components/ui/sonner";
import { Tabs, TabsContent } from "@/components/ui/tabs";
import {
  useConversations,
  useInboxCounts,
  useMarkUnread,
  useScheduledMessages,
  useSocialAccounts,
  useUpdateConversation,
} from "@/lib/api/queries";
import { keys, type ConversationFilters } from "@/lib/api/queries/keys";
import type { AiMode, Conversation, InboxView, Platform, SocialAccount } from "@/lib/api/types";
import { minWidth } from "@/lib/breakpoints";
import { inboxSearch } from "@/lib/inbox/url";
import { emptyStates, inboxFilterEmpty } from "@/lib/copy";
import { toastError } from "@/lib/toast-error";
import { useMediaQuery, useNow, useStoredFlag, useStoredString } from "@/lib/use-browser-state";
import { cn } from "@/lib/utils";
import { useCurrentWorkspace } from "@/lib/workspace";

import { ConversationList, RowSkeletons } from "./ConversationList";
import { DetailsPanel } from "./DetailsPanel";
import { InboxUiProvider, useInboxLayout, type InboxLayout, type InboxUi } from "./inbox-context";
import { ListHeader, VIEWS, type InboxTab } from "./ListHeader";
import { PlatformStrip, type PlatformChoice } from "./PlatformStrip";
import { ScheduledList } from "./ScheduledList";
import { ShortcutsDialog } from "./ShortcutsDialog";
import { useInboxShortcuts, useSingleKeyShortcuts } from "./use-inbox-shortcuts";

const PLATFORM_ORDER: Platform[] = ["instagram", "whatsapp"];

function viewFromLink(value: string | null): InboxView {
  return VIEWS.find((option) => option.value === value)?.value ?? "all";
}

/** Remembered per device (try/catch-guarded localStorage, lib/use-browser-state). */
export const CONTEXT_PANEL_KEY = "socialhood:inbox-details";

/** Accounts that can still hold conversations. */
function liveAccounts(accounts: SocialAccount[]): SocialAccount[] {
  return accounts.filter((account) => account.status !== "disconnected");
}

const LIST_WIDTH: Record<InboxLayout, string> = {
  wide: "w-[320px]",
  desktop: "w-[320px]",
  tablet: "w-[300px]",
  phone: "w-full",
};

/** A tab panel fills the list pane under the header; its focus outline is inset, as the pane clips. */
const PANEL = "flex min-h-0 flex-1 flex-col focus-visible:-outline-offset-2";

/**
 * The inbox (UX-INB-01…03, C-063): list pane, thread pane (the route's page) and the context
 * panel, laid out for the four widths. Filters live here, so switching conversations keeps the
 * list.
 */
export function InboxShell({ children }: { children: ReactNode }) {
  const workspace = useCurrentWorkspace();
  const accounts = useSocialAccounts(workspace.id);

  if (accounts.isPending) return <InboxFrame><RowSkeletons /></InboxFrame>;
  if (accounts.isError) {
    return (
      <InboxFrame>
        <ErrorState error={accounts.error} onRetry={() => void accounts.refetch()} />
      </InboxFrame>
    );
  }
  const live = liveAccounts(accounts.data);
  if (live.length === 0) {
    return (
      <InboxFrame>
        <EmptyState
          className="h-full"
          title={emptyStates.connections.title}
          body={emptyStates.connections.body}
          action={
            <Button asChild>
              <Link href={`/w/${workspace.slug}/settings/connections` as Route}>Connect an account</Link>
            </Button>
          }
        />
      </InboxFrame>
    );
  }
  return <Inbox accounts={live}>{children}</Inbox>;
}

/**
 * The inbox fills the height, inset like the sidebar, left corners rounded (UX-SH-03): it takes
 * what `<main>` has left under any banner (data-shell-fill, AppShell's ShellFrame).
 */
function InboxFrame({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        "flex min-h-0 flex-1 overflow-hidden bg-panel md:m-4 md:rounded-xl md:border md:border-line",
        className,
      )}
      data-testid="inbox"
      data-shell-fill
    >
      {children}
    </div>
  );
}

function Inbox({ accounts, children }: { accounts: SocialAccount[]; children: ReactNode }) {
  const workspace = useCurrentWorkspace();
  const wid = workspace.id;
  const slug = workspace.slug;
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const params = useParams<{ id?: string }>();
  const selectedId = params.id ?? null;
  const layout = useInboxLayout();
  const now = useNow();

  // ---- filters (FR-INB-01)
  const platforms = useMemo(
    () => PLATFORM_ORDER.filter((p) => accounts.some((account) => account.platform === p)),
    [accounts],
  );
  // `view` and `platform` live in the address (UI-052): Back, refresh and Home's link land on the same list.
  // The state follows the address when it changes (Back, a link while the inbox is mounted) and
  // leads it when a chip is pressed, so the list answers before the navigation settles.
  const [storedPlatform, setStoredPlatform] = useStoredString<PlatformChoice>(`socialhood:inbox-platform:${wid}`, "all");
  const urlView = viewFromLink(searchParams.get("view"));
  const [view, setView] = useState<InboxView>(urlView);
  const [seenUrlView, setSeenUrlView] = useState(urlView);
  if (urlView !== seenUrlView) {
    setSeenUrlView(urlView);
    setView(urlView);
  }
  const urlPlatform = searchParams.get("platform");
  const [chosenPlatform, setChosenPlatform] = useState<string | null>(urlPlatform);
  const [seenUrlPlatform, setSeenUrlPlatform] = useState(urlPlatform);
  if (urlPlatform !== seenUrlPlatform) {
    setSeenUrlPlatform(urlPlatform);
    setChosenPlatform(urlPlatform);
  }
  // The address wins over the device's remembered platform; a platform no account has falls back to all.
  const rawPlatform = chosenPlatform ?? storedPlatform;
  const platform: PlatformChoice = platforms.includes(rawPlatform as Platform) ? (rawPlatform as Platform) : "all";
  const [accountId, setAccountId] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [tab, setTab] = useState<InboxTab>("chats");
  /** The filters as an address query, kept on the way to a conversation so Back returns to this list. */
  const listQuery = inboxSearch("", { view, platform: chosenPlatform });
  const changeView = useCallback(
    (next: InboxView) => {
      setView(next);
      router.push(`${pathname}${inboxSearch(searchParams, { view: next })}` as Route, { scroll: false });
    },
    [pathname, router, searchParams],
  );
  const changePlatform = useCallback(
    (choice: PlatformChoice) => {
      setStoredPlatform(choice);
      setChosenPlatform(choice);
      setAccountId(null);
      router.push(`${pathname}${inboxSearch(searchParams, { platform: choice })}` as Route, { scroll: false });
    },
    [pathname, router, searchParams, setStoredPlatform],
  );
  const platformAccounts = platform === "all" ? [] : accounts.filter((account) => account.platform === platform);
  const effectiveAccountId = platformAccounts.some((account) => account.id === accountId) ? accountId : null;

  const filters: ConversationFilters = {
    view,
    platform: platform === "all" ? null : platform,
    accountId: effectiveAccountId,
    q,
  };
  const conversations = useConversations(wid, filters);
  const items = useMemo(() => conversations.data?.pages.flatMap((page) => page.items) ?? [], [conversations.data]);
  const scheduled = useScheduledMessages(wid);
  // The Scheduled tab follows the platform filter, so its count does too (the account filter can't apply: a
  // scheduled message carries no account).
  const scheduledCount =
    scheduled.data?.pages.reduce(
      (sum, page) => sum + page.items.filter((s) => s.status === "scheduled" && (platform === "all" || s.platform === platform)).length,
      0,
    ) ?? 0;
  const counts = useInboxCounts(wid).data;
  const accountModes = useMemo(
    () => Object.fromEntries(accounts.map((account) => [account.id, account.ai_mode])) as Record<string, AiMode>,
    [accounts],
  );

  // ---- context panel: inline at ≥ 1280 px, a sheet below. Collapsible from the header; the
  // choice is remembered per device, and until there is one it starts open only from `wide`
  // (1440 px). Server value: collapsed, as on every narrower screen; the panel is inline only
  // from 1280 px, so a wrong guess can't cover a phone's thread.
  const roomy = useMediaQuery(minWidth("wide"), false);
  const [inlineDetails, setInlineDetails] = useStoredFlag(CONTEXT_PANEL_KEY, roomy);
  const [sheetDetails, setSheetDetails] = useState(false);
  const detailsOpen = layout === "wide" ? inlineDetails : sheetDetails;
  const toggleDetails = useCallback(() => {
    if (layout === "wide") setInlineDetails(!inlineDetails);
    else setSheetDetails((open) => !open);
  }, [layout, inlineDetails, setInlineDetails]);
  const closeDetails = useCallback(() => {
    if (layout === "wide") setInlineDetails(false);
    else setSheetDetails(false);
  }, [layout, setInlineDetails]);

  // ---- actions shared by the thread header, the menu and the shortcuts
  const queryClient = useQueryClient();
  const update = useUpdateConversation(wid);
  const unread = useMarkUnread(wid);
  const [manualUnreadId, setManualUnreadId] = useState<string | null>(null);
  const [previousSelected, setPreviousSelected] = useState(selectedId);
  if (previousSelected !== selectedId) {
    // Opening a conversation again marks it read again.
    setPreviousSelected(selectedId);
    setManualUnreadId(null);
  }

  const open = useCallback((id: string | null) => {
    router.push((id ? `/w/${slug}/inbox/${id}${listQuery}` : `/w/${slug}/inbox${listQuery}`) as Route);
  }, [router, slug, listQuery]);

  const archive = useCallback(
    (id: string, archived: boolean) => {
      const index = items.findIndex((item) => item.id === id);
      update.mutate(
        { id, patch: { status: archived ? "archived" : "open" } },
        {
          onSuccess: () => {
            toast.success(archived ? "Conversation archived" : "Conversation moved to the inbox", {
              action: { label: "Undo", onClick: () => update.mutate({ id, patch: { status: archived ? "open" : "archived" } }) },
              duration: TOAST_ACTION_DURATION,
            });
          },
          onError: (error) => toastError(error),
        },
      );
      // Archiving the open conversation moves on to the next one, as mail apps do.
      if (archived && id === selectedId && view !== "archived") {
        const next = items[index + 1] ?? items[index - 1];
        open(next && next.id !== id ? next.id : null);
      }
    },
    [items, open, selectedId, update, view],
  );

  const markUnread = useCallback(
    (id: string) => {
      setManualUnreadId(id);
      unread.mutate(id, { onError: (error) => toastError(error) });
    },
    [unread],
  );

  const searchRef = useRef<HTMLInputElement>(null);
  // D-14: the per-device switch for the single-key shortcuts lives in the Keyboard shortcuts dialog, which the
  // list header's keyboard button and "?" open.
  const [singleKeys] = useSingleKeyShortcuts();
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  useInboxShortcuts({
    move: (step) => {
      const index = selectedId ? items.findIndex((item) => item.id === selectedId) : -1;
      const next = index === -1 ? (step === 1 ? 0 : -1) : index + step;
      if (next >= 0 && next < items.length) open(items[next].id);
      if (next >= items.length - 3 && conversations.hasNextPage && !conversations.isFetchingNextPage) {
        void conversations.fetchNextPage();
      }
    },
    focusSearch: () => {
      setTab("chats");
      requestAnimationFrame(() => searchRef.current?.focus());
    },
    archive: () => {
      if (!selectedId) return;
      const status =
        queryClient.getQueryData<Conversation>(keys.conversation(wid, selectedId))?.status ??
        items.find((item) => item.id === selectedId)?.status;
      archive(selectedId, status !== "archived");
    },
    markUnread: () => {
      if (selectedId) markUnread(selectedId);
    },
    help: () => setShortcutsOpen(true),
    escape: () => {
      if (detailsOpen) closeDetails();
      else if (layout === "phone" && selectedId) open(null);
    },
  }, singleKeys);

  const ui: InboxUi = {
    layout,
    slug,
    selectedId,
    detailsOpen,
    toggleDetails,
    closeDetails,
    setTab,
    manualUnreadId,
    markUnread,
    archive,
  };

  const showList = layout !== "phone" || !selectedId;
  const showThread = layout !== "phone" || Boolean(selectedId);
  const viewLabel = VIEWS.find((option) => option.value === view)?.label ?? view;
  const filtered = view !== "all" || q.trim() !== "";

  return (
    <InboxUiProvider value={ui}>
      <ShortcutsDialog open={shortcutsOpen} onOpenChange={setShortcutsOpen} />
      <InboxFrame>
        {showList ? (
          <section
            aria-label="Conversation list"
            data-pane="list"
            className={cn("flex shrink-0 flex-col border-r border-line bg-panel", LIST_WIDTH[layout], layout === "phone" && "border-r-0")}
          >
            <PlatformStrip
              platforms={platforms}
              value={platform}
              onChange={changePlatform}
            />
            {/* Chats | Scheduled swap the list below (UX-INB-03): the tabs are in ListHeader, the panels here. */}
            <Tabs value={tab} onValueChange={(value) => setTab(value as InboxTab)} className="min-h-0 flex-1 gap-0">
              <ListHeader
                tab={tab}
                scheduledCount={scheduledCount}
                view={view}
                onViewChange={changeView}
                counts={counts}
                onShortcuts={() => setShortcutsOpen(true)}
                search={q}
                onSearchChange={setQ}
                searchRef={searchRef}
                accounts={platformAccounts}
                accountId={effectiveAccountId}
                onAccountChange={setAccountId}
              />
              <TabsContent value="chats" className={PANEL}>
                {conversations.isPending ? (
                  <RowSkeletons />
                ) : conversations.isError ? (
                  <ErrorState error={conversations.error} onRetry={() => void conversations.refetch()} />
                ) : items.length === 0 ? (
                  filtered ? (
                    <EmptyState
                      {...inboxFilterEmpty(q.trim() || viewLabel)}
                      action={
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => {
                            changeView("all");
                            setQ("");
                          }}
                        >
                          Show all
                        </Button>
                      }
                    />
                  ) : (
                    <EmptyState {...emptyStates.inboxNoConversations} />
                  )
                ) : (
                  <ConversationList
                    // A new filter is a new list: scroll to the top, forget what was announced.
                    key={JSON.stringify(filters)}
                    items={items}
                    slug={slug}
                    selectedId={selectedId}
                    now={now}
                    hasNextPage={conversations.hasNextPage}
                    isFetchingNextPage={conversations.isFetchingNextPage}
                    fetchNextPage={() => void conversations.fetchNextPage()}
                    accountModes={accountModes}
                    query={listQuery}
                  />
                )}
              </TabsContent>
              <TabsContent value="scheduled" className={PANEL}>
                <ScheduledList onOpen={(id) => open(id)} now={now} platform={platform === "all" ? null : platform} />
              </TabsContent>
            </Tabs>
          </section>
        ) : null}

        {showThread ? (
          <section aria-label="Conversation" data-pane="thread" className="flex min-w-0 flex-1 flex-col bg-canvas">
            {children}
          </section>
        ) : null}

        {selectedId && detailsOpen && layout === "wide" ? (
          <aside aria-label="Details" data-pane="details" className="w-[300px] shrink-0 overflow-y-auto border-l border-line bg-panel wide:w-[320px]">
            <DetailsPanel conversationId={selectedId} />
          </aside>
        ) : null}
      </InboxFrame>

      {/* Below 1280 px the details are a side panel (DESIGN_SYSTEM §8.2): full screen on phones, 420 px beside the thread above.
          The title row holds the sheet's close button, so the panel's first row (Open in Instagram) starts under it
          instead of under the button (UI-031); only the panel below the title row scrolls. */}
      {layout !== "wide" ? (
        <Sheet open={Boolean(selectedId) && detailsOpen} onOpenChange={(value) => (value ? undefined : closeDetails())}>
          <SheetContent side="right" size="panel" data-pane="details" className="gap-0 p-0">
            <SheetHeader className="shrink-0 border-b border-line">
              <SheetTitle>Details</SheetTitle>
            </SheetHeader>
            <div className="min-h-0 flex-1 overflow-y-auto" data-testid="details-scroll">
              {selectedId ? <DetailsPanel conversationId={selectedId} /> : null}
            </div>
          </SheetContent>
        </Sheet>
      ) : null}
    </InboxUiProvider>
  );
}
