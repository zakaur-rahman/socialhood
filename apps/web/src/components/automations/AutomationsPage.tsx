"use client";

import { Pause, Plus, X } from "lucide-react";
import type { Route } from "next";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { PageFrame } from "@/components/shell/PageFrame";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { SearchInput } from "@/components/ui/search-input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { TOAST_ACTION_DURATION } from "@/components/ui/sonner";
import { useAgentHandoff, type AutomationDraftHandoff } from "@/lib/agent/handoff";
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
import { toastError } from "@/lib/toast-error";
import { useNow } from "@/lib/use-browser-state";
import { useCurrentWorkspace } from "@/lib/workspace";

import { AccountGroup, type GroupActions } from "./AccountGroup";
import { AgentDraftDialog } from "./AgentDraftDialog";
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
  // The gallery stays mounted, so closing it plays its exit. Its state is its own; a new key on
  // each opening starts it fresh (and at the account question when a template card opened it).
  const [gallery, setGallery] = useState<{ open: boolean; choice?: Choice; key: number }>({ open: openGallery, key: 0 });
  const showGallery = (choice?: Choice) => setGallery((current) => ({ open: true, choice, key: current.key + 1 }));
  // /automations and /automations/new share this one list (the route group's layout), so arriving
  // at /new while the list is on screen opens the gallery, and leaving it doesn't remount the page.
  const [atNew, setAtNew] = useState(openGallery);
  if (openGallery !== atNew) {
    setAtNew(openGallery);
    if (openGallery) showGallery();
  }
  const { start, pending: starting } = useStartAutomation();
  const closeGallery = () => {
    setGallery((current) => ({ ...current, open: false }));
    if (openGallery) router.replace(`/w/${workspace.slug}/automations` as Route);
  };
  // A dialog opened by a link from another page (Home's checklist, Ask's hand-off) has no opener
  // here to give focus back to: New automation takes it (UX-A11Y-02).
  const newAutomation = useRef<HTMLButtonElement>(null);
  const focusNewAutomation = () => newAutomation.current;
  // FR-AGT-03: an automation draft handed over by Ask Social Hood shows first (instead of the
  // gallery on /automations/new); it is taken once from the hand-off store.
  const draftHandoff = useAgentHandoff((state) => state.automationDraft);
  const takeAutomationDraft = useAgentHandoff((state) => state.takeAutomationDraft);
  const [agentDraft, setAgentDraft] = useState<AutomationDraftHandoff | null>(null);
  const [draftOpen, setDraftOpen] = useState(false);
  const [draftTaken, setDraftTaken] = useState<string | null>(null);
  if (draftHandoff && draftHandoff.nonce !== draftTaken) {
    setDraftTaken(draftHandoff.nonce);
    setAgentDraft(draftHandoff);
    setDraftOpen(true);
  }
  useEffect(() => {
    if (draftHandoff) takeAutomationDraft(draftHandoff.nonce);
  }, [draftHandoff, takeAutomationDraft]);

  const quickStart = (choice: Choice) => {
    if (accounts.length > 1) showGallery(choice);
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
  // A delete's confirmation hands focus back to the row's ⋯ button, which goes with the row once
  // the delete lands: New automation takes it then, rather than the page losing it to <body>.
  const deleted = useRef<string | null>(null);

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
          onError: (error) => toastError(error),
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
              duration: TOAST_ACTION_DURATION,
            });
          } else toastError(error); // a plan limit (402) is the upgrade dialog's to say
        },
      });
    },
    onDuplicate: (automation) =>
      duplicate.mutate(automation.id, {
        onSuccess: (copy) =>
          toast.success(`Duplicated as ${copy.name}`, {
            action: { label: "Open", onClick: () => router.push(editorHref(workspace.slug, copy.id)) },
            duration: TOAST_ACTION_DURATION,
          }),
        onError: (error) => toastError(error),
      }),
    onDelete: (automation) => {
      deleted.current = automation.id;
      remove.mutate(automation.id, {
        onSuccess: () => {
          toast.success(`Deleted ${automation.name}`);
          setSelected((current) => {
            const next = new Set(current);
            next.delete(automation.id);
            return next;
          });
        },
        onError: (error) => {
          deleted.current = null;
          toastError(error);
        },
      });
    },
  };

  useEffect(() => {
    const id = deleted.current;
    if (!id || items.some((item) => item.id === id)) return;
    deleted.current = null;
    if (!document.activeElement || document.activeElement === document.body) newAutomation.current?.focus();
  }, [items]);

  const pauseSelected = () =>
    bulkPause.mutate(selectedIds, {
      onSuccess: () => {
        toast.success(selectedIds.length === 1 ? "Paused 1 automation" : `Paused ${selectedIds.length} automations`);
        setSelected(new Set());
      },
      onError: (error) => toastError(error),
    });

  // Reordering needs every automation of the account on screen, in the order they run.
  const canReorder = sort === "priority" && !status && !trigger && !q.trim();
  const reorder = (groupAccountId: string) => (orderedIds: string[]) =>
    priorities.mutate(
      { accountId: groupAccountId, orderedIds },
      { onError: (error) => toastError(error, `The order didn't save. ${errorMessage(error)}`) },
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
        onBrowse={() => showGallery()}
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
        <Button ref={newAutomation} size="lg" onClick={() => showGallery()}>
          <Plus aria-hidden /> New <span className="max-[359px]:sr-only">automation</span>
        </Button>
      }
    >
      <div className="space-y-5">
        <SummaryStrip summary={summary.data} loading={summary.isPending} />

        <div className="flex flex-wrap items-center gap-2">
          <SearchInput
            label="Search automations"
            id="automations-search"
            size="lg"
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="Search by name or keyword"
            className="min-w-48 flex-1"
          />
          {accounts.length > 1 ? (
            <Select value={accountId ?? ALL} onValueChange={(value) => setAccountId(value === ALL ? null : value)}>
              <SelectTrigger aria-label="Account" size="lg" className="max-w-48">
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
            <SelectTrigger aria-label="Status" size="lg">
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
            <SelectTrigger aria-label="Trigger" size="lg">
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
            <SelectTrigger aria-label="Sort" size="lg">
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

      <TemplateGallery
        key={gallery.key}
        open={gallery.open && !draftOpen}
        onOpenChange={(open) => (open ? undefined : closeGallery())}
        templates={templates.data ?? []}
        templatesLoading={templates.isPending}
        accounts={accounts}
        initialChoice={gallery.choice}
        plan={workspace.plan}
        returnFocusFallback={focusNewAutomation}
      />
      <AgentDraftDialog
        open={draftOpen}
        draft={agentDraft}
        accounts={accounts}
        returnFocusFallback={focusNewAutomation}
        onClose={() => {
          setDraftOpen(false);
          closeGallery();
        }}
      />
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
        <Card key={figure.label}>
          <p className="text-xs text-fg-secondary">{figure.label}</p>
          {loading ? (
            <Skeleton className="mt-2 h-7 w-16" />
          ) : (
            <p className="mt-1 text-2xl font-semibold tabular-nums">
              {figure.value === undefined ? "—" : formatCount(figure.value)}
            </p>
          )}
          <p className="mt-1 text-xs text-fg-secondary">{figure.hint}</p>
        </Card>
      ))}
    </section>
  );
}

function RowSkeletons() {
  return (
    <div aria-busy="true" aria-label="Loading automations" className="space-y-2">
      {Array.from({ length: 4 }, (_, i) => (
        <Card key={i} className="flex items-center gap-3">
          <Skeleton className="h-5 w-8 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3 w-1/3" />
            <Skeleton className="h-3 w-1/2" />
          </div>
          <Skeleton className="h-5 w-24" />
        </Card>
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
    <Card asChild padding="roomy">
    <section>
      <EmptyState className="py-4" {...emptyStates.automations} />
      <ul aria-label="Templates" className="grid grid-cols-1 gap-3 md:grid-cols-3">
        {loading
          ? Array.from({ length: 3 }, (_, i) => (
              <li key={i} aria-hidden>
                <Skeleton className="h-44 rounded-xl" />
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
    </Card>
  );
}
