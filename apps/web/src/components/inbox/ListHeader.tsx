"use client";

import { ChevronDown } from "lucide-react";
import { useEffect, useState, type Ref } from "react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Badge } from "@/components/ui/badge";
import { SearchInput } from "@/components/ui/search-input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { InboxView, SocialAccount } from "@/lib/api/types";
import { cn } from "@/lib/utils";

export type InboxTab = "chats" | "scheduled";

/** The chips, in order (FR-INB-01); "Needs you" is the escalated view (C-063). */
export const CHIP_VIEWS: { value: InboxView; label: string }[] = [
  { value: "all", label: "All" },
  { value: "unread", label: "Unread" },
  { value: "needs_reply", label: "Needs reply" },
  { value: "needs_you", label: "Needs you" },
  { value: "leads", label: "Leads" },
  { value: "ai_handled", label: "AI handled" },
];

/** Views behind the "More" chip. */
export const MORE_VIEWS: { value: InboxView; label: string }[] = [{ value: "archived", label: "Archived" }];

export const VIEWS = [...CHIP_VIEWS, ...MORE_VIEWS];

export const SEARCH_DEBOUNCE_MS = 250;

/**
 * The "More" chip opens a menu, so it can't be a ToggleGroupItem: it copies the chip's look from
 * `ui/toggle-group` (height, edge, hover, inset focus, 40 px on coarse pointers), and the chosen
 * look while one of its views is on.
 */
const MORE_CHIP =
  "inline-flex h-7 shrink-0 items-center justify-center gap-0.5 rounded-full border px-3 text-xs font-medium whitespace-nowrap transition-[color,background-color,border-color] duration-fast ease-standard focus-visible:-outline-offset-2 pointer-coarse:min-h-10";
const MORE_ON = "border-brand-line bg-brand-soft text-brand-fg";
const MORE_OFF = "border-line text-fg-secondary hover:bg-hover hover:text-fg";

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

  const more = MORE_VIEWS.find((option) => option.value === view) ?? null;

  return (
    <div className="space-y-3 border-b border-line bg-panel px-3 pt-3 pb-2.5">
      <div className="flex items-center justify-between gap-2">
        <h1 className="text-lg font-semibold">Inbox</h1>
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
          {/* One row that scrolls sideways (UI-052 wraps it from md, with an edge fade below). */}
          <div className="-mx-3 flex gap-1.5 overflow-x-auto px-3 pb-0.5 [scrollbar-width:none]">
            <ToggleGroup
              variant="chips"
              aria-label="Views"
              value={view}
              onValueChange={(value) => onViewChange(value as InboxView)}
              className="flex-nowrap"
            >
              {CHIP_VIEWS.map((option) => (
                <ToggleGroupItem key={option.value} value={option.value}>
                  {option.label}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  aria-label={more ? `More views: ${more.label}` : "More views"}
                  data-active={Boolean(more)}
                  className={cn(MORE_CHIP, more ? MORE_ON : MORE_OFF)}
                >
                  {more ? more.label : "More"}
                  <ChevronDown className="size-3" aria-hidden />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuRadioGroup value={view} onValueChange={(value) => onViewChange(value as InboxView)}>
                  {MORE_VIEWS.map((option) => (
                    <DropdownMenuRadioItem key={option.value} value={option.value}>
                      {option.label}
                    </DropdownMenuRadioItem>
                  ))}
                </DropdownMenuRadioGroup>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </>
      ) : null}
    </div>
  );
}
