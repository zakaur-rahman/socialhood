"use client";

import { ChevronDown, Search } from "lucide-react";
import { useEffect, useState, type Ref } from "react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
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

const CHIP = "shrink-0 rounded-full border px-3 py-1 text-xs font-medium";
const CHIP_ON = "border-brand-line bg-brand-soft text-brand-fg";
const CHIP_OFF = "border-line text-fg-secondary hover:bg-white/5 hover:text-fg";

/**
 * UX-INB-03, re-arranged (C-063): "Inbox" with the Chats | Scheduled segments, a full-width
 * search (debounced, server-side) with the account filter beside it, and the view chips.
 */
export function ListHeader({
  tab,
  onTabChange,
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
  onTabChange: (tab: InboxTab) => void;
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
        <div role="tablist" aria-label="Inbox sections" className="flex gap-0.5 rounded-lg border border-line bg-field p-0.5">
          {(["chats", "scheduled"] as const).map((value) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={tab === value}
              onClick={() => onTabChange(value)}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-3 py-1 text-xs font-medium",
                tab === value ? "bg-raised text-fg shadow-sm" : "text-fg-secondary hover:text-fg",
              )}
            >
              {value === "chats" ? "Chats" : "Scheduled"}
              {value === "scheduled" && scheduledCount > 0 ? (
                <span
                  className="bg-brand-gradient grid h-4 min-w-4 place-items-center rounded-full px-1 text-[10px] text-white tabular-nums"
                  aria-label={`${scheduledCount} scheduled`}
                >
                  {scheduledCount}
                </span>
              ) : null}
            </button>
          ))}
        </div>
      </div>

      {tab === "chats" ? (
        <>
          <div className="flex items-center gap-2">
            <div className="relative min-w-0 flex-1">
              <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-fg-secondary" aria-hidden />
              <label htmlFor="inbox-search" className="sr-only">
                Search conversations
              </label>
              <input
                ref={searchRef}
                id="inbox-search"
                type="search"
                value={text}
                onChange={(event) => setText(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Escape" && text) {
                    event.preventDefault();
                    setText("");
                  }
                }}
                placeholder="Search people and messages"
                autoComplete="off"
                className="w-full rounded-lg border border-line bg-field py-2 pr-3 pl-9 text-sm outline-none focus:bg-raised"
              />
            </div>
            {accounts.length > 1 ? (
              <Select value={accountId ?? "all"} onValueChange={(value) => onAccountChange(value === "all" ? null : value)}>
                <SelectTrigger size="sm" aria-label="Account" className="max-w-32 shrink-0">
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
          <div role="group" aria-label="Views" className="-mx-3 flex gap-1.5 overflow-x-auto px-3 pb-0.5 [scrollbar-width:none]">
            {CHIP_VIEWS.map((option) => (
              <button
                key={option.value}
                type="button"
                aria-pressed={view === option.value}
                onClick={() => onViewChange(option.value)}
                className={cn(CHIP, view === option.value ? CHIP_ON : CHIP_OFF)}
              >
                {option.label}
              </button>
            ))}
            {/* Not modal: the list stays usable while it is open. */}
            <DropdownMenu modal={false}>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  aria-label={more ? `More views: ${more.label}` : "More views"}
                  data-active={Boolean(more)}
                  className={cn(CHIP, "inline-flex items-center gap-0.5", more ? CHIP_ON : CHIP_OFF)}
                >
                  {more ? more.label : "More"}
                  <ChevronDown className="size-3" aria-hidden />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-40 border-line bg-panel shadow-xl">
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
