"use client";

import { AlertTriangle, Download, SlidersHorizontal, Tag, Users } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { ContactAvatar } from "@/components/inbox/ContactAvatar";
import { STAGE_LABEL, STAGE_TONE } from "@/lib/leads/stages";
import { PageFrame } from "@/components/shell/PageFrame";
import { EmptyState } from "@/components/states/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cardVariants } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { SearchInput } from "@/components/ui/search-input";
import { useContactCount, useContacts, useExportContacts } from "@/lib/api/queries";
import type { ContactListItem, Platform } from "@/lib/api/types";
import { activeFilterCount, EMPTY_FILTERS, hasAnyFilter, type ContactFilters } from "@/lib/contacts/filters";
import { relativeTime } from "@/lib/time";
import { toastError } from "@/lib/toast-error";
import { useCurrentWorkspace } from "@/lib/workspace";
import { cn } from "@/lib/utils";

import { BulkTagDialog } from "./BulkTagDialog";
import { ContactDrawer } from "./ContactDrawer";
import { FiltersSheet } from "./FiltersSheet";
import { SegmentBar } from "./SegmentBar";
import { TagChip } from "./TagChip";
import { ListCardSkeleton, SkeletonRegion } from "@/components/states/skeletons";

export const SEARCH_DEBOUNCE_MS = 250;

/** Save a blob as a file through a temporary link. */
function saveBlob(blob: Blob, name: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

/**
 * Contacts (GR-17): everyone who has messaged or commented, newest activity first, filtered on the
 * server and loaded in pages. Search, filters (tag, email, phone, platform, consent, lead score,
 * lead stage, last activity, custom fields), saved segments, bulk tagging (the ticked rows, or everyone the
 * filters match) and a CSV export for admins. A row opens the contact drawer, a full-screen panel
 * on a phone. It fills the width of the screen.
 */
export function ContactsPage() {
  const { id: wid, role } = useCurrentWorkspace();
  const admin = role !== "agent";
  const params = useSearchParams();
  const [filters, setFilters] = useState<ContactFilters>(EMPTY_FILTERS);
  const [text, setText] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [openId, setOpenId] = useState<string | null>(params.get("contact"));
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
  const [allMatching, setAllMatching] = useState(false);
  const [tagging, setTagging] = useState(false);

  const list = useContacts(wid, filters);
  const count = useContactCount(wid, filters);
  const exporter = useExportContacts(wid);
  const items = list.data?.pages.flatMap((page) => page.items) ?? [];
  const total = count.data ?? null;

  // Typing waits a moment before it asks the server; a new filter starts a fresh selection.
  useEffect(() => {
    if (text === filters.q) return;
    const timer = window.setTimeout(() => {
      setFilters((current) => ({ ...current, q: text }));
      setSelected(new Set());
      setAllMatching(false);
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [text, filters.q]);

  function applyFilters(next: ContactFilters) {
    setFilters(next);
    setText(next.q);
    setSelected(new Set());
    setAllMatching(false);
  }

  function toggle(id: string, on: boolean) {
    setAllMatching(false);
    setSelected((current) => {
      const next = new Set(current);
      if (on) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  const pageSelected = items.length > 0 && items.every((item) => selected.has(item.id));
  const anySelected = selected.size > 0;

  function exportCsv() {
    exporter.mutate(filters, {
      onSuccess: (blob) => saveBlob(blob, `contacts-${new Date().toISOString().slice(0, 10)}.csv`),
      onError: (error) => toastError(error),
    });
  }

  const filterCount = activeFilterCount(filters);
  const filtered = hasAnyFilter(filters);

  return (
    <PageFrame
      title="Contacts"
      actions={
        admin ? (
          <Button variant="secondary" loading={exporter.isPending} onClick={exportCsv}>
            <Download aria-hidden /> Export CSV
          </Button>
        ) : null
      }
    >
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <SearchInput
            label="Search contacts"
            placeholder="Name, @username, email or phone"
            value={text}
            onChange={(event) => setText(event.target.value)}
            className="min-w-48 flex-1 sm:max-w-96"
          />
          <Button variant="secondary" onClick={() => setFiltersOpen(true)}>
            <SlidersHorizontal aria-hidden /> Filters
            {filterCount > 0 ? (
              <Badge tone="count" aria-label={`${filterCount} on`}>
                {filterCount}
              </Badge>
            ) : null}
          </Button>
          {filtered ? (
            <Button variant="ghost" onClick={() => applyFilters(EMPTY_FILTERS)}>
              Clear
            </Button>
          ) : null}
        </div>

        <SegmentBar filters={filters} onApply={(next) => applyFilters(next)} />

        <div className="flex min-h-9 flex-wrap items-center justify-between gap-2 text-sm text-fg-secondary" aria-live="polite">
          <p data-testid="contact-count">
            {total === null ? "Counting" : `${total.toLocaleString()} ${total === 1 ? "contact" : "contacts"}`}
            {filtered ? " match" : ""}
          </p>
          {anySelected ? (
            <div className="flex flex-wrap items-center gap-2 text-fg">
              <span data-testid="selection">
                {allMatching && total !== null ? `All ${total.toLocaleString()} selected` : `${selected.size} selected`}
              </span>
              <Button size="sm" onClick={() => setTagging(true)}>
                <Tag aria-hidden /> Tag
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  setSelected(new Set());
                  setAllMatching(false);
                }}
              >
                Clear selection
              </Button>
            </div>
          ) : null}
        </div>

        {pageSelected && !allMatching && total !== null && total > items.length ? (
          <p className="rounded-lg bg-raised px-3 py-2 text-sm">
            {items.length} on this page are selected.{" "}
            <Button variant="link" size="xs" className="px-0" onClick={() => setAllMatching(true)}>
              Select all {total.toLocaleString()} {filtered ? "that match" : "contacts"}
            </Button>
          </p>
        ) : null}

        {list.isPending ? (
          <SkeletonRegion label="Loading contacts">
            <ListCardSkeleton />
          </SkeletonRegion>
        ) : list.isError ? (
          <EmptyState
            icon={<AlertTriangle />}
            title="Contacts did not load"
            body="Check your connection and try again."
            action={
              <Button variant="secondary" onClick={() => void list.refetch()}>
                Try again
              </Button>
            }
          />
        ) : items.length === 0 ? (
          <EmptyState
            icon={<Users />}
            title={filtered ? "No contacts match" : "No contacts yet"}
            body={
              filtered
                ? "Try fewer filters, or clear them to see everyone."
                : "People appear here when they message you or comment on a post."
            }
            action={
              filtered ? (
                <Button variant="secondary" onClick={() => applyFilters(EMPTY_FILTERS)}>
                  Clear filters
                </Button>
              ) : undefined
            }
          />
        ) : (
          <>
            <div className={cn(cardVariants(), "overflow-hidden p-0")}>
              <div className="flex items-center gap-3 border-b border-line px-3 py-2 text-xs text-fg-secondary">
                <Checkbox
                  aria-label="Select all on this page"
                  checked={pageSelected ? true : anySelected ? "indeterminate" : false}
                  onCheckedChange={(on) => {
                    setAllMatching(false);
                    setSelected(on === true ? new Set(items.map((item) => item.id)) : new Set());
                  }}
                />
                <div className="hidden min-w-0 flex-1 md:grid md:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_minmax(0,1.2fr)_4.5rem_5rem] md:gap-4">
                  <span>Contact</span>
                  <span>Tags</span>
                  <span>Email and phone</span>
                  <span>Lead score</span>
                  <span>Last active</span>
                </div>
                <span className="md:hidden">Contacts</span>
              </div>
              <ul aria-label="Contacts">
                {items.map((item) => (
                  <ContactRow
                    key={item.id}
                    item={item}
                    selected={allMatching || selected.has(item.id)}
                    onToggle={(on) => toggle(item.id, on)}
                    onOpen={() => setOpenId(item.id)}
                  />
                ))}
              </ul>
            </div>
            {list.hasNextPage ? (
              <div className="flex justify-center">
                <Button variant="secondary" loading={list.isFetchingNextPage} onClick={() => void list.fetchNextPage()}>
                  Show more
                </Button>
              </div>
            ) : null}
          </>
        )}
      </div>

      <FiltersSheet open={filtersOpen} onOpenChange={setFiltersOpen} filters={filters} onChange={applyFilters} />
      <ContactDrawer contactId={openId} onClose={() => setOpenId(null)} />
      <BulkTagDialog
        open={tagging}
        onOpenChange={setTagging}
        target={
          allMatching && total !== null
            ? { kind: "filter", filters, count: total }
            : { kind: "ids", ids: [...selected] }
        }
        onDone={() => {
          setSelected(new Set());
          setAllMatching(false);
        }}
      />
      {exporter.isSuccess ? <span className="sr-only" role="status">Export ready</span> : null}
    </PageFrame>
  );
}

function ContactRow({
  item,
  selected,
  onToggle,
  onOpen,
}: {
  item: ContactListItem;
  selected: boolean;
  onToggle: (on: boolean) => void;
  onOpen: () => void;
}) {
  const reach = [item.email, item.phone].filter(Boolean).join(" · ");
  return (
    <li data-testid="contact-row" className="flex items-start gap-3 border-b border-line px-3 py-3 last:border-b-0 hover:bg-hover md:items-center">
      <Checkbox aria-label={`Select ${item.name}`} checked={selected} onCheckedChange={(on) => onToggle(on === true)} className="mt-1 md:mt-0" />
      <button
        type="button"
        onClick={onOpen}
        aria-label={`Open ${item.name}`}
        className="flex min-w-0 flex-1 flex-col gap-2 text-left md:grid md:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_minmax(0,1.2fr)_4.5rem_5rem] md:items-center md:gap-4"
      >
        <span className="flex min-w-0 items-center gap-3">
          <ContactAvatar id={item.id} name={item.name} pictureUrl={item.profile_picture_url} platform={item.platform as Platform} size={32} />
          <span className="min-w-0">
            <span className="block truncate font-medium">{item.name}</span>
            {item.username ? <span className="block truncate text-xs text-fg-secondary">@{item.username}</span> : null}
            <Badge tone={STAGE_TONE[item.lead_stage]} className="mt-1" data-testid="contact-stage">
              {STAGE_LABEL[item.lead_stage]}
            </Badge>
          </span>
        </span>
        <span className="flex min-w-0 flex-wrap gap-1">
          {item.tags.map((tag) => (
            <TagChip key={tag.id} tag={tag} />
          ))}
        </span>
        <span className="truncate text-sm text-fg-secondary">{reach || "No email or phone"}</span>
        <span className="text-sm md:text-left">
          <span className="text-xs text-fg-secondary md:hidden">Lead score </span>
          {item.lead_score ?? "None"}
        </span>
        <span className="text-xs text-fg-secondary">
          {item.last_activity_at ? (relativeTime(item.last_activity_at) === "now" ? "Just now" : `${relativeTime(item.last_activity_at)} ago`) : "None"}
        </span>
      </button>
    </li>
  );
}
