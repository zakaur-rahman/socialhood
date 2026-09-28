"use client";

import { Search } from "lucide-react";
import { useEffect, useState, type Ref } from "react";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { InboxView, SocialAccount } from "@/lib/api/types";
import { cn } from "@/lib/utils";

export type InboxTab = "chats" | "scheduled";

export const VIEWS: { value: InboxView; label: string }[] = [
  { value: "all", label: "All" },
  { value: "unread", label: "Unread" },
  { value: "needs_reply", label: "Needs reply" },
  { value: "leads", label: "Leads" },
  { value: "ai_handled", label: "AI handled" },
  { value: "archived", label: "Archived" },
];

export const SEARCH_DEBOUNCE_MS = 250;

/**
 * UX-INB-03: "Inbox" with the account filter, the Chats | Scheduled segments, search
 * (debounced, server-side) and the view chips.
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

  return (
    <div className="space-y-3 border-b border-line bg-panel px-4 pt-3 pb-2">
      <div className="flex items-center justify-between gap-2">
        <h1 className="text-xl font-semibold">Inbox</h1>
        {accounts.length > 1 ? (
          <Select value={accountId ?? "all"} onValueChange={(value) => onAccountChange(value === "all" ? null : value)}>
            <SelectTrigger size="sm" aria-label="Account" className="max-w-40">
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

      <div role="tablist" aria-label="Inbox sections" className="grid grid-cols-2 gap-1 rounded-lg bg-field p-1">
        {(["chats", "scheduled"] as const).map((value) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={tab === value}
            onClick={() => onTabChange(value)}
            className={cn(
              "flex items-center justify-center gap-2 rounded-md py-2 text-sm font-medium",
              tab === value ? "bg-raised text-brand-fg shadow-sm" : "text-fg-secondary hover:text-fg",
            )}
          >
            {value === "chats" ? "Chats" : "Scheduled"}
            {value === "scheduled" && scheduledCount > 0 ? (
              <span
                className="bg-brand-gradient grid h-5 min-w-5 place-items-center rounded-full px-1.5 text-xs text-white tabular-nums"
                aria-label={`${scheduledCount} scheduled`}
              >
                {scheduledCount}
              </span>
            ) : null}
          </button>
        ))}
      </div>

      {tab === "chats" ? (
        <>
          <div className="relative">
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
              className="w-full rounded-lg border border-line bg-field py-2 pr-3 pl-10 text-sm outline-none focus:bg-raised"
            />
          </div>
          <div role="group" aria-label="Views" className="-mx-4 flex gap-1.5 overflow-x-auto px-4 pb-1 [scrollbar-width:none]">
            {VIEWS.map((option) => (
              <button
                key={option.value}
                type="button"
                aria-pressed={view === option.value}
                onClick={() => onViewChange(option.value)}
                className={cn(
                  "shrink-0 rounded-full px-3 py-1 text-xs font-medium",
                  view === option.value ? "bg-brand-soft text-brand-fg" : "text-fg-secondary hover:bg-white/5 hover:text-fg",
                )}
              >
                {option.label}
              </button>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}
