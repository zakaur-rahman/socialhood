"use client";

import { Pause, Plus, Search, X } from "lucide-react";
import type { Route } from "next";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { PageFrame } from "@/components/shell/PageFrame";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/errors";
import {
  useActivateAutomation,
  useAutomations,
  useAutomationsSummary,
  useAutomationTemplates,
  useBulkPause,
  useDeleteAutomation,
  useDuplicateAutomation,
  usePauseAutomation,
  useSocialAccounts,
  useUpdatePriorities,
  type AutomationFilters,
} from "@/lib/api/queries";
import type { Automation, AutomationSort, AutomationStatus, SocialAccount, TriggerName } from "@/lib/api/types";
import { accountLabel, instagramAccounts } from "@/lib/automations/accounts";
import { etaText, formatCount, TRIGGER_LABEL } from "@/lib/automations/format";
import { emptyStates, errorMessage } from "@/lib/copy";
import { useNow } from "@/lib/use-browser-state";
import { useCurrentWorkspace } from "@/lib/workspace";

import { AccountGroup, type GroupActions } from "./AccountGroup";
import { editorHref, TemplateCard, TemplateGallery, useStartAutomation, type Choice } from "./TemplateGallery";

export const SEARCH_DEBOUNCE_MS = 250;

/** "priority" is the order automations run in (FR-AUT-15): the API's order, sorted here. */
export type ListSort = "priority" | AutomationSort;

const SORTS: { value: ListSort; label: string }[] = [
  { value: "priority", label: "Priority" },
  { value: "recent_runs", label: "Recent runs" },
  { value: "name", label: "Name" },
  { value: "created", label: "Created" },
];

const STATUSES: { value: AutomationStatus; label: string }[] = [
  { value: "active", label: "Active" },
  { value: "paused", label: "Paused" },
  { value: "draft", label: "Draft" },
];

const TRIGGERS: TriggerName[] = ["comment_keyword", "comment_any", "dm_keyword"];
const ALL = "all";

function byPriority(a: Automation, b: Automation): number {
  return a.priority - b.priority || a.created_at.localeCompare(b.created_at);
}

type Group = { key: string; title: string; accountId: string | null; items: Automation[] };

/** Rows grouped by account, in the accounts' order; automations without one come last. */
export function groupByAccount(items: Automation[], accounts: SocialAccount[], sort: ListSort): Group[] {
  const groups = new Map<string, Group>();
  const known = new Map(accounts.map((account) => [account.id, account]));
  for (const automation of items) {
    const accountId = automation.social_account_id ?? null;
    const key = accountId ?? "none";
    let group = groups.get(key);
    if (!group) {
      const account = accountId ? known.get(accountId) : undefined;
      group = {
        key,
        accountId,
        title: account ? accountLabel(account) : accountId ? "Disconnected account" : "No account yet",
        items: [],
      };
      groups.set(key, group);
    }
    group.items.push(automation);
  }
  const order = (group: Group) => {
    if (!group.accountId) return Number.MAX_SAFE_INTEGER;
    const index = accounts.findIndex((account) => account.id === group.accountId);
    return index === -1 ? Number.MAX_SAFE_INTEGER - 1 : index;
  };
  const list = [...groups.values()].sort((a, b) => order(a) - order(b));
  if (sort === "priority") for (const group of list) group.items.sort(byPriority);
  return list;
}

/**
 * UX-SCR-02: the automations list. Figures for the last 7 days, search and filters, rows grouped
 * by account with priority by drag or keyboard, bulk pause, and the template gallery (UX-SCR-11).
 */
export function AutomationsPage({ openGallery = false }: { openGallery?: boolean }) {
  const workspace = useCurrentWorkspace();
  const wid = workspace.id;
  const router = useRouter();
  const now = useNow();

  // ---- filters (FR-AUT-19)
  const [text, setText] = useState("");
  const [q, setQ] = useState("");
  const [accountId, setAccountId] = useState<string | null>(null);
  const [status, setStatus] = useState<AutomationStatus | null>(null);
  const [trigger, setTrigger] = useState<TriggerName | null>(null);
  const [sort, setSort] = useState<ListSort>("priority");
  useEffect(() => {
    if (text === q) return;
    const timer = window.setTimeout(() => setQ(text), SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [text, q]);

  const filters: AutomationFilters = { accountId, status, trigger, q, sort: sort === "priority" ? "created" : sort };
  const filtered = Boolean(accountId || status || trigger || q.trim());
  const list = useAutomations(wid, filters);
  const summary = useAutomationsSummary(wid);
  const templates = useAutomationTemplates(wid);
  const allAccounts = useSocialAccounts(wid);
  const accounts = useMemo(() => instagramAccounts(allAccounts.data ?? []), [allAccounts.data]);

  // ---- gallery (UX-SCR-11)
  const [gallery, setGallery] = useState<{ open: boolean; choice?: Choice }>({ open: openGallery });
  const { start, pending: starting } = useStartAutomation();
  const closeGallery = () => {
    setGallery({ open: false });
    if (openGallery) router.replace(`/w/${workspace.slug}/automations` as Route);
  };
  const quickStart = (choice: Choice) => {
    if (accounts.length > 1) setGallery({ open: true, choice });
    else start(choice, accounts[0]?.id ?? null);
  };

  // ---- row actions
  const activate = useActivateAutomation(wid);
  const pause = usePauseAutomation(wid);
  const duplicate = useDuplicateAutomation(wid);
  const remove = useDeleteAutomation(wid);
  const bulkPause = useBulkPause(wid);
  const priorities = useUpdatePriorities(wid);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const items = useMemo(() => list.data?.items ?? [], [list.data]);
  const selectedIds = items.filter((item) => selected.has(item.id)).map((item) => item.id);
  const pendingStatusId = activate.isPending ? activate.variables : pause.isPending ? pause.variables : null;

  const actions: GroupActions = {
    href: (automation) => editorHref(workspace.slug, automation.id),
    selected,
    onSelectedChange: (id, value) =>
      setSelected((current) => {
        const next = new Set(current);
        if (value) next.add(id);
        else next.delete(id);
        return next;
      }),
    pendingStatusId: pendingStatusId ?? null,
    onActiveChange: (automation, active) => {
      if (!active) {
        pause.mutate(automation.id, {
          onSuccess: () => toast.success(`Paused ${automation.name}`),
          onError: (error) => toast.error(errorMessage(error)),
        });
        return;
      }
      activate.mutate(automation.id, {
        onSuccess: (result) =>
          toast.success(result.display_status === "scheduled" ? `${result.name} is scheduled` : `${result.name} is active`),
        onError: (error) => {
          const fields = error instanceof ApiError && error.code === "validation_error" ? error.errors : [];
          if (fields.length > 0) {
            toast.error(`${automation.name} isn't ready: ${fields[0].message}`, {
              action: { label: "Finish setup", onClick: () => router.push(editorHref(workspace.slug, automation.id)) },
            });
          } else toast.error(errorMessage(error));
        },
      });
    },
    onDuplicate: (automation) =>
      duplicate.mutate(automation.id, {
        onSuccess: (copy) =>
          toast.success(`Duplicated as ${copy.name}`, {
            action: { label: "Open", onClick: () => router.push(editorHref(workspace.slug, copy.id)) },
          }),
        onError: (error) => toast.error(errorMessage(error)),
      }),
    onDelete: (automation) =>
      remove.mutate(automation.id, {
        onSuccess: () => {
          toast.success(`Deleted ${automation.name}`);
          setSelected((current) => {
            const next = new Set(current);
            next.delete(automation.id);
            return next;
          });
        },
        onError: (error) => toast.error(errorMessage(error)),
      }),
  };

  const pauseSelected = () =>
    bulkPause.mutate(selectedIds, {
      onSuccess: () => {
        toast.success(selectedIds.length === 1 ? "Paused 1 automation" : `Paused ${selectedIds.length} automations`);
        setSelected(new Set());
      },
      onError: (error) => toast.error(errorMessage(error)),
    });

  // Reordering needs every automation of the account on screen, in the order they run.
  const canReorder = sort === "priority" && !status && !trigger && !q.trim();
  const reorder = (groupAccountId: string) => (orderedIds: string[]) =>
    priorities.mutate(
      { accountId: groupAccountId, orderedIds },
      { onError: (error) => toast.error(`The order didn't save. ${errorMessage(error)}`) },
    );

  const groups = useMemo(() => groupByAccount(items, accounts, sort), [items, accounts, sort]);
  const clearFilters = () => {
    setText("");
    setQ("");
    setAccountId(null);
    setStatus(null);
    setTrigger(null);
  };

  let content;
  if (list.isPending) content = <RowSkeletons />;
  else if (list.isError) content = <ErrorState error={list.error} onRetry={() => void list.refetch()} />;
  else if (items.length === 0 && !filtered) {
    content = (
      <EmptyAutomations
        templates={templates.data ?? []}
        loading={templates.isPending}
        plan={workspace.plan}
        starting={starting}
        onUse={quickStart}
        onBrowse={() => setGallery({ open: true })}
      />
    );
  } else if (items.length === 0) {
    content = (
      <EmptyState
        {...emptyStates.automationsFiltered}
        action={
          <Button variant="secondary" onClick={clearFilters}>
            Clear filters
          </Button>
        }
      />
    );
  } else {
    content = (
      <div className="space-y-6">
        {groups.map((group) => (
          <AccountGroup
            key={group.key}
            title={group.title}
            automations={group.items}
            timeZone={workspace.timezone}
            now={now}
            actions={actions}
            onReorder={canReorder && group.accountId && group.items.length > 1 ? reorder(group.accountId) : undefined}
          />
        ))}
        {sort === "priority" && !canReorder ? (
          <p className="text-xs text-fg-secondary">Clear the search and filters to change the order.</p>
        ) : null}
      </div>
    );
  }

  return (
    <PageFrame
      title="Automations"
      actions={
        <Button className="bg-brand-gradient h-9 text-white" onClick={() => setGallery({ open: true })}>
          <Plus aria-hidden /> New automation
        </Button>
      }
    >
      <div className="space-y-5">
        <SummaryStrip summary={summary.data} loading={summary.isPending} />

        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-48 flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-fg-secondary" aria-hidden />
            <label htmlFor="automations-search" className="sr-only">
              Search automations
            </label>
            <input
              id="automations-search"
              type="search"
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder="Search by name or keyword"
              autoComplete="off"
              className="h-9 w-full rounded-lg border border-line bg-field pr-3 pl-10 text-sm outline-none focus:bg-raised focus-visible:ring-3 focus-visible:ring-ring/50"
            />
          </div>
          {accounts.length > 1 ? (
            <Select value={accountId ?? ALL} onValueChange={(value) => setAccountId(value === ALL ? null : value)}>
              <SelectTrigger aria-label="Account" className="h-9 max-w-48">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>All accounts</SelectItem>
                {accounts.map((account) => (
                  <SelectItem key={account.id} value={account.id}>
                    {accountLabel(account)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : null}
          <Select
            value={status ?? ALL}
            onValueChange={(value) => setStatus(value === ALL ? null : (value as AutomationStatus))}
          >
            <SelectTrigger aria-label="Status" className="h-9">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All statuses</SelectItem>
              {STATUSES.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={trigger ?? ALL} onValueChange={(value) => setTrigger(value === ALL ? null : (value as TriggerName))}>
            <SelectTrigger aria-label="Trigger" className="h-9">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All triggers</SelectItem>
              {TRIGGERS.map((value) => (
                <SelectItem key={value} value={value}>
                  {TRIGGER_LABEL[value]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={sort} onValueChange={(value) => setSort(value as ListSort)}>
            <SelectTrigger aria-label="Sort" className="h-9">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SORTS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  Sort: {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {selectedIds.length > 0 ? (
          <div
            role="region"
            aria-label="Selected automations"
            className="flex flex-wrap items-center gap-3 rounded-xl border border-brand-line bg-brand-soft px-4 py-2 text-sm"
          >
            <span className="font-medium tabular-nums">{selectedIds.length} selected</span>
            <Button size="sm" variant="secondary" onClick={pauseSelected} disabled={bulkPause.isPending}>
              <Pause aria-hidden /> Pause
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setSelected(new Set())} className="ml-auto">
              <X aria-hidden /> Clear selection
            </Button>
          </div>
        ) : null}

        {content}
      </div>

      {gallery.open ? (
        <TemplateGallery
          open
          onOpenChange={(open) => (open ? undefined : closeGallery())}
          templates={templates.data ?? []}
          templatesLoading={templates.isPending}
          accounts={accounts}
          initialChoice={gallery.choice}
          plan={workspace.plan}
        />
      ) : null}
    </PageFrame>
  );
}

function SummaryStrip({
  summary,
  loading,
}: {
  summary: { active: number; runs_7d: number; dms_sent_7d: number; waiting: number; longest_eta_minutes?: number | null } | undefined;
  loading: boolean;
}) {
  const eta = etaText(summary?.longest_eta_minutes);
  const figures = [
    { label: "Active automations", value: summary?.active, hint: "Running now" },
    { label: "Runs", value: summary?.runs_7d, hint: "Last 7 days" },
    { label: "DMs sent", value: summary?.dms_sent_7d, hint: "Last 7 days" },
    {
      label: "Waiting for a DM",
      value: summary?.waiting,
      hint: summary?.waiting ? (eta ? `All sent in ${eta}` : "In the private-reply queue") : "Nobody waiting",
    },
  ];
  return (
    <section aria-label="Last 7 days" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {figures.map((figure) => (
        <div key={figure.label} className="rounded-xl border border-line bg-panel p-4">
          <p className="text-xs text-fg-secondary">{figure.label}</p>
          {loading ? (
            <Skeleton className="mt-2 h-7 w-16 bg-raised" />
          ) : (
            <p className="mt-1 text-2xl font-semibold tabular-nums">
              {figure.value === undefined ? "—" : formatCount(figure.value)}
            </p>
          )}
          <p className="mt-1 text-xs text-fg-secondary">{figure.hint}</p>
        </div>
      ))}
    </section>
  );
}

function RowSkeletons() {
  return (
    <div aria-busy="true" aria-label="Loading automations" className="space-y-2">
      {Array.from({ length: 4 }, (_, i) => (
        <div key={i} className="flex items-center gap-3 rounded-xl border border-line bg-panel p-4">
          <Skeleton className="h-5 w-8 rounded-full bg-raised" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3 w-1/3 bg-raised" />
            <Skeleton className="h-3 w-1/2 bg-raised" />
          </div>
          <Skeleton className="h-5 w-24 bg-raised" />
        </div>
      ))}
    </div>
  );
}

function EmptyAutomations({
  templates,
  loading,
  plan,
  starting,
  onUse,
  onBrowse,
}: {
  templates: Parameters<typeof TemplateCard>[0]["template"][];
  loading: boolean;
  plan: "free" | "pro" | "max";
  starting: boolean;
  onUse: (choice: Choice) => void;
  onBrowse: () => void;
}) {
  return (
    <section className="rounded-xl border border-line bg-panel p-6">
      <EmptyState className="py-4" {...emptyStates.automations} />
      <ul aria-label="Templates" className="grid grid-cols-1 gap-3 md:grid-cols-3">
        {loading
          ? Array.from({ length: 3 }, (_, i) => (
              <li key={i} aria-hidden>
                <Skeleton className="h-44 rounded-xl bg-raised" />
              </li>
            ))
          : templates.slice(0, 3).map((template) => (
              <li key={template.key}>
                <TemplateCard
                  template={template}
                  showPro={template.requires_paid_plan && plan === "free"}
                  pending={false}
                  disabled={starting}
                  onUse={() => onUse(template)}
                />
              </li>
            ))}
      </ul>
      <div className="mt-4 flex justify-center">
        <Button variant="secondary" onClick={onBrowse}>
          Browse all templates
        </Button>
      </div>
    </section>
  );
}
