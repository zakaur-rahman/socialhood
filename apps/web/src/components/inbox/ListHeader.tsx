"use client";

import { Keyboard } from "lucide-react";
import { useEffect, useState, type Ref } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SearchInput } from "@/components/ui/search-input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { InboxCounts, InboxView, SocialAccount } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { PANE_TITLE } from "@/styles/tokens";

export type InboxTab = "chats" | "scheduled";

/**
 * The chips, in order (FR-INB-01); "Needs you" is the escalated view (C-063). Archived is a plain
 * chip last, not a menu of one (D-15 item 4).
 */
export const CHIP_VIEWS: { value: InboxView; label: string }[] = [
  { value: "all", label: "All" },
  { value: "unread", label: "Unread" },
  { value: "needs_reply", label: "Needs reply" },
  { value: "needs_you", label: "Needs you" },
  { value: "leads", label: "Leads" },
  { value: "ai_handled", label: "AI handled" },
  { value: "archived", label: "Archived" },
];

export const VIEWS = CHIP_VIEWS;

export const SEARCH_DEBOUNCE_MS = 250;

/** The two chips that carry a count (the counts query is workspace-wide). */
const COUNTED: Partial<Record<InboxView, "needs_reply" | "needs_you">> = { needs_reply: "needs_reply", needs_you: "needs_you" };

/** The Scheduled count stops at 99, like the sidebar's. */
function countText(count: number): string {
  return count > 99 ? "99+" : String(count);
}

/**
 * UX-INB-03, re-arranged (C-063): "Inbox" with the Chats | Scheduled tabs, a full-width search
 * (debounced, server-side) with the account filter beside it, and the view chips. The Tabs root
 * and the two panels are InboxShell's, which renders the lists the tabs swap.
 */
export function ListHeader({
  tab,
  scheduledCount,
  view,
  onViewChange,
  counts,
  onShortcuts,
  search,
  onSearchChange,
  searchRef,
  accounts,
  accountId,
  onAccountChange,
}: {
  tab: InboxTab;
  scheduledCount: number;
  view: InboxView;
  onViewChange: (view: InboxView) => void;
  /** Open conversations waiting on a reply or on the owner; the two chips show them when above zero. */
  counts?: Pick<InboxCounts, "needs_reply" | "needs_you">;
  /** Opens the Keyboard shortcuts dialog (D-14). */
  onShortcuts?: () => void;
  search: string;
  onSearchChange: (q: string) => void;
  searchRef?: Ref<HTMLInputElement>;
  /** Accounts of the selected platform; the filter shows when there are several. */
  accounts: SocialAccount[];
  accountId: string | null;
  onAccountChange: (id: string | null) => void;
}) {
  const [text, setText] = useState(search);
  const [synced, setSynced] = useState(search);
  if (search !== synced) {
    // Cleared from outside ("Show all"): follow it.
    setSynced(search);
    setText(search);
  }

  useEffect(() => {
    if (text === search) return;
    const timer = window.setTimeout(() => {
      setSynced(text);
      onSearchChange(text);
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [text, search, onSearchChange]);

  return (
    <div className="space-y-3 border-b border-line bg-panel px-3 pt-3 pb-2.5">
      <div className="flex items-center justify-between gap-2">
        <h1 className={cn(PANE_TITLE, "sr-only md:not-sr-only")}>Inbox</h1>
        <div className="ml-auto flex items-center gap-1">
          {onShortcuts ? (
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="Keyboard shortcuts"
              aria-haspopup="dialog"
              aria-keyshortcuts="?"
              onClick={onShortcuts}
            >
              <Keyboard aria-hidden />
            </Button>
          ) : null}
          <TabsList size="sm" aria-label="Inbox sections">
            <TabsTrigger value="chats">Chats</TabsTrigger>
            {/* The count is part of the tab's name ("Scheduled, 3 to send"); the badge is decoration (UX-SH-01). */}
            <TabsTrigger
              value="scheduled"
              aria-label={scheduledCount > 0 ? `Scheduled, ${countText(scheduledCount)} to send` : undefined}
            >
              Scheduled
              {scheduledCount > 0 ? (
                <Badge tone="count" size="md" aria-hidden data-testid="scheduled-count">
                  {countText(scheduledCount)}
                </Badge>
              ) : null}
            </TabsTrigger>
          </TabsList>
        </div>
      </div>

      {tab === "chats" ? (
        <>
          {/* The SearchInput primitive (UI-031): Esc empties it first. `lg` (36 px) is the closest to the old
              38 px field; the account filter beside it is `lg` too, so the two line up. */}
          <div className="flex items-center gap-2">
            <SearchInput
              ref={searchRef}
              id="inbox-search"
              label="Search conversations"
              size="lg"
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder="Search people and messages"
              className="flex-1"
            />
            {accounts.length > 1 ? (
              <Select value={accountId ?? "all"} onValueChange={(value) => onAccountChange(value === "all" ? null : value)}>
                <SelectTrigger size="lg" aria-label="Account" className="max-w-32 shrink-0">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All accounts</SelectItem>
                  {accounts.map((account) => (
                    <SelectItem key={account.id} value={account.id}>
                      {account.username ? `@${account.username}` : (account.display_name ?? account.phone_number ?? "Account")}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : null}
          </div>
          {/* From md the chips wrap onto as many rows as they need; below it they stay one row that scrolls
              sideways, with the right edge fading out so a cut-off chip reads as "more" (UI-052). */}
          <div className="mask-fade-x -mx-3 overflow-x-auto pe-7 ps-3 scroll-pe-7 [scrollbar-width:none] md:mask-none md:overflow-visible md:pe-3">
            <ToggleGroup
              variant="chips"
              aria-label="Views"
              value={view}
              onValueChange={(value) => onViewChange(value as InboxView)}
              className="w-max flex-nowrap md:w-auto md:flex-wrap"
            >
              {CHIP_VIEWS.map((option) => {
                const count = counts && COUNTED[option.value] ? counts[COUNTED[option.value]!] : 0;
                return (
                  <ToggleGroupItem
                    key={option.value}
                    value={option.value}
                    // The count is part of the chip's name; the badge is decoration (as the Scheduled tab's).
                    aria-label={count > 0 ? `${option.label}, ${countText(count)}` : undefined}
                  >
                    {option.label}
                    {count > 0 ? (
                      <Badge tone="count" size="sm" aria-hidden data-testid={`count-${option.value}`}>
                        {countText(count)}
                      </Badge>
                    ) : null}
                  </ToggleGroupItem>
                );
              })}
            </ToggleGroup>
          </div>
        </>
      ) : null}
    </div>
  );
}
