"use client";

import { AlertTriangle, Funnel, SlidersHorizontal } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { ContactDrawer } from "@/components/contacts/ContactDrawer";
import { FiltersSheet } from "@/components/contacts/FiltersSheet";
import { TagChip } from "@/components/contacts/TagChip";
import { ContactAvatar } from "@/components/inbox/ContactAvatar";
import { PageFrame } from "@/components/shell/PageFrame";
import { EmptyState } from "@/components/states/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cardVariants } from "@/components/ui/card";
import { SearchInput } from "@/components/ui/search-input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useContacts, useLeadSettings, useLeadSummary, useSetLeadStage, useUpdateLeadSettings } from "@/lib/api/queries";
import type { ContactListItem, LeadStage, Platform } from "@/lib/api/types";
import { activeFilterCount, EMPTY_FILTERS, hasAnyFilter, type ContactFilters } from "@/lib/contacts/filters";
import { coldDayOptions, LEAD_STAGES, STAGE_LABEL } from "@/lib/leads/stages";
import { relativeTime } from "@/lib/time";
import { toastError } from "@/lib/toast-error";
import { useCurrentWorkspace } from "@/lib/workspace";
import { cn } from "@/lib/utils";

import { StageControl } from "./StageControl";

const SEARCH_DEBOUNCE_MS = 250;

/**
 * Leads (GR-18): the contacts, sorted by lead stage. From 1024 px it is a board with a column per
 * stage; below that it is one list at a time with the stages as buttons above it, so it works at
 * 375 px. Each column is the contacts list filtered to its stage, so search and the filters are
 * GR-17's, and a column shows the newest activity first. A card shows why the lead is where it is,
 * when they were last active, whether they have gone cold, one click to the conversation, and a
 * control to move the stage. Admins choose how many quiet days make a lead cold.
 */
export function LeadsPage() {
  const { id: wid, role } = useCurrentWorkspace();
  const admin = role !== "agent";
  const [filters, setFilters] = useState<ContactFilters>(EMPTY_FILTERS);
  const [text, setText] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);
  const [shown, setShown] = useState<LeadStage>("new");
  const summary = useLeadSummary(wid);

  // Typing waits a moment before it asks the server.
  useEffect(() => {
    if (text === filters.q) return;
    const timer = window.setTimeout(() => setFilters((current) => ({ ...current, q: text })), SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [text, filters.q]);

  function applyFilters(next: ContactFilters) {
    setFilters(next);
    setText(next.q);
  }

  const filtered = hasAnyFilter(filters);
  const filterCount = activeFilterCount(filters);
  const counts = useMemo(
    () => Object.fromEntries((summary.data?.stages ?? []).map((s) => [s.stage, s.count])) as Partial<Record<LeadStage, number>>,
    [summary.data],
  );
  const cold = summary.data?.cold ?? 0;

  return (
    <PageFrame title="Leads" actions={admin ? <ColdSetting /> : null}>
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <SearchInput
            label="Search leads"
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

        {cold > 0 ? (
          <p className="rounded-lg bg-warning-soft px-3 py-2 text-sm text-warning" data-testid="cold-note">
            {cold === 1 ? "1 lead has" : `${cold.toLocaleString()} leads have`} gone cold: no reply for {summary.data?.cold_after_days}{" "}
            days or more.
          </p>
        ) : null}

        <div role="group" aria-label="Show a stage" className="flex flex-wrap gap-2 lg:hidden">
          {LEAD_STAGES.map((stage) => (
            <Button
              key={stage.value}
              size="sm"
              variant={shown === stage.value ? "secondary" : "ghost"}
              aria-pressed={shown === stage.value}
              onClick={() => setShown(stage.value)}
            >
              {stage.label}
              {!filtered && counts[stage.value] !== undefined ? (
                <span className="text-xs text-fg-secondary tabular-nums">{counts[stage.value]}</span>
              ) : null}
            </Button>
          ))}
        </div>

        <div className="grid gap-4 lg:grid-cols-5">
          {LEAD_STAGES.map((stage) => (
            <StageColumn
              key={stage.value}
              stage={stage.value}
              filters={filters}
              count={filtered ? undefined : counts[stage.value]}
              visibleBelowLarge={shown === stage.value}
              onOpen={setOpenId}
            />
          ))}
        </div>
      </div>

      <FiltersSheet open={filtersOpen} onOpenChange={setFiltersOpen} filters={filters} onChange={applyFilters} hideStage />
      <ContactDrawer contactId={openId} onClose={() => setOpenId(null)} />
    </PageFrame>
  );
}

/** Admins: days without a customer message before a qualified or follow-up lead goes cold. */
function ColdSetting() {
  const { id: wid } = useCurrentWorkspace();
  const settings = useLeadSettings(wid);
  const update = useUpdateLeadSettings(wid);
  if (!settings.data) return null;
  const days = settings.data.cold_after_days;
  return (
    <Select
      value={String(days)}
      onValueChange={(next) =>
        update.mutate(Number(next), {
          onSuccess: () => toast.success("Saved"),
          onError: (error) => toastError(error),
        })
      }
      disabled={update.isPending}
    >
      <SelectTrigger aria-label="Gone cold after" className="w-full sm:w-56">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {coldDayOptions(days).map((choice) => (
          <SelectItem key={choice} value={String(choice)}>
            Gone cold after {choice} days
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

function StageColumn({
  stage,
  filters,
  count,
  visibleBelowLarge,
  onOpen,
}: {
  stage: LeadStage;
  filters: ContactFilters;
  count: number | undefined;
  visibleBelowLarge: boolean;
  onOpen: (id: string) => void;
}) {
  const { id: wid } = useCurrentWorkspace();
  const columnFilters = useMemo<ContactFilters>(() => ({ ...filters, stages: [stage] }), [filters, stage]);
  const list = useContacts(wid, columnFilters);
  const items = list.data?.pages.flatMap((page) => page.items) ?? [];
  const label = STAGE_LABEL[stage];

  return (
    <section aria-label={`${label} leads`} className={cn("min-w-0 space-y-3", visibleBelowLarge ? "block" : "hidden lg:block")}>
      <h2 className="hidden items-center gap-2 text-sm font-medium lg:flex">
        {label}
        {count !== undefined ? <span className="text-xs text-fg-secondary tabular-nums">{count}</span> : null}
      </h2>
      {list.isPending ? (
        <div role="status" aria-label={`Loading ${label.toLowerCase()} leads`} className="space-y-2">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : list.isError ? (
        <EmptyState
          size="compact"
          icon={<AlertTriangle />}
          title={`${label} leads did not load`}
          body="Check your connection and try again."
          action={
            <Button variant="secondary" onClick={() => void list.refetch()}>
              Try again
            </Button>
          }
        />
      ) : items.length === 0 ? (
        <EmptyState size="compact" icon={<Funnel />} title="No leads here" body={hasAnyFilter(filters) ? "Nothing matches the filters." : undefined} />
      ) : (
        <>
          <ul aria-label={`${label} leads list`} className="space-y-2">
            {items.map((item) => (
              <LeadCard key={item.id} item={item} onOpen={() => onOpen(item.id)} />
            ))}
          </ul>
          {list.hasNextPage ? (
            <Button variant="secondary" size="sm" loading={list.isFetchingNextPage} onClick={() => void list.fetchNextPage()}>
              Show more
            </Button>
          ) : null}
        </>
      )}
    </section>
  );
}

function LeadCard({ item, onOpen }: { item: ContactListItem; onOpen: () => void }) {
  const { id: wid, slug } = useCurrentWorkspace();
  const move = useSetLeadStage(wid);
  const last = item.last_activity_at ? relativeTime(item.last_activity_at) : null;
  return (
    <li data-testid="lead-card" className={cn(cardVariants(), "space-y-2 p-3")}>
      <div className="flex items-start gap-3">
        <ContactAvatar id={item.id} name={item.name} pictureUrl={item.profile_picture_url} platform={item.platform as Platform} size={32} />
        <div className="min-w-0 flex-1">
          <button type="button" onClick={onOpen} aria-label={`Open ${item.name}`} className="block max-w-full truncate text-left font-medium hover:underline">
            {item.name}
          </button>
          <p className="truncate text-xs text-fg-secondary">
            {[item.lead_score !== null && item.lead_score !== undefined ? `Score ${item.lead_score}` : null, last ? (last === "now" ? "Active just now" : `Active ${last} ago`) : null]
              .filter(Boolean)
              .join(" · ") || "No activity yet"}
          </p>
        </div>
        {item.lead_cold ? (
          <Badge tone="warning" data-testid="cold-chip">
            Gone cold
          </Badge>
        ) : null}
      </div>
      {item.lead_stage_reason ? <p className="text-xs text-fg-secondary">{item.lead_stage_reason}</p> : null}
      {item.tags.length > 0 ? (
        <div className="flex flex-wrap gap-1">
          {item.tags.slice(0, 3).map((tag) => (
            <TagChip key={tag.id} tag={tag} />
          ))}
        </div>
      ) : null}
      <div className="flex items-center gap-2">
        <StageControl
          value={item.lead_stage}
          label={`Stage for ${item.name}`}
          disabled={move.isPending}
          onChange={(stage) =>
            move.mutate(
              { id: item.id, stage },
              { onSuccess: () => toast.success(`Moved to ${STAGE_LABEL[stage]}`), onError: (error) => toastError(error) },
            )
          }
        />
        {item.conversation_id ? (
          <Link
            href={`/w/${slug}/inbox/${item.conversation_id}` as Route}
            className="shrink-0 text-sm text-brand-fg underline-offset-4 hover:underline"
            aria-label={`Open the conversation with ${item.name}`}
          >
            Conversation
          </Link>
        ) : null}
      </div>
    </li>
  );
}
