"use client";

import { Plus, Trash2 } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { PageFrame } from "@/components/shell/PageFrame";
import { ErrorState } from "@/components/states/ErrorState";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/errors";
import { useAutomations, useIceBreakers, useSaveIceBreakers, useSocialAccounts, useSyncIceBreakers } from "@/lib/api/queries";
import type { IceBreaker, Platform } from "@/lib/api/types";
import { networkName } from "@/lib/automations/limits";
import { accountLabel, automationAccounts } from "@/lib/automations/accounts";
import { toastError } from "@/lib/toast-error";
import { useCurrentWorkspace } from "@/lib/workspace";

const AI = "ai";
const MAX_QUESTION = 80;

/** One row being edited: the question and where a tap goes ("ai", an automation id, or nothing yet). */
type Row = { key: string; question: string; target: string };

function rowsOf(items: IceBreaker[]): Row[] {
  return items.map((item) => ({
    key: item.id,
    question: item.question,
    target: item.answer_with_ai ? AI : (item.automation_id ?? ""),
  }));
}

/**
 * GR-11: an Instagram account's conversation starters, up to four questions shown at the top of a
 * new chat in the Instagram app (not on desktop). Each one starts an automation or is answered by
 * the AI. Saving pushes the list to Instagram; if Instagram refuses it, the list is kept and the
 * reason is shown with a way to try again.
 */
export function StartersPage() {
  const workspace = useCurrentWorkspace();
  const wid = workspace.id;
  const allAccounts = useSocialAccounts(wid);
  const accounts = useMemo(() => automationAccounts(allAccounts.data ?? []), [allAccounts.data]);
  const [chosen, setChosen] = useState<string | null>(null);
  const accountId = chosen ?? accounts[0]?.id ?? null;

  return (
    <PageFrame
      title="Conversation starters"
      back={{ href: `/w/${workspace.slug}/automations` as Route, label: "Automations" }}
      actions={
        accounts.length > 1 ? (
          <Select value={accountId ?? ""} onValueChange={setChosen}>
            <SelectTrigger aria-label="Account" size="lg" className="max-w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {accounts.map((account) => (
                <SelectItem key={account.id} value={account.id}>
                  {accountLabel(account)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : null
      }
    >
      {accountId ? (
        <Starters
          key={accountId}
          wid={wid}
          slug={workspace.slug}
          accountId={accountId}
          platform={accounts.find((account) => account.id === accountId)?.platform}
        />
      ) : (
        <Card className="p-4 text-sm text-fg-secondary">
          Connect an Instagram account or a Facebook Page to set conversation starters.
        </Card>
      )}
    </PageFrame>
  );
}

function Starters({
  wid,
  slug,
  accountId,
  platform,
}: {
  wid: string;
  slug: string;
  accountId: string;
  platform?: Platform;
}) {
  const network = networkName(platform);
  const list = useIceBreakers(wid, accountId);
  const options = useAutomations(wid, { accountId, status: null, trigger: "ice_breaker", q: "", sort: "created" });
  const save = useSaveIceBreakers(wid, accountId);
  const sync = useSyncIceBreakers(wid, accountId);
  const [edited, setRows] = useState<Row[] | null>(null);
  const [problems, setProblems] = useState<Record<string, string>>({});
  const saved = list.data?.items;
  const fromSaved = useMemo(() => (saved ? rowsOf(saved) : null), [saved]);
  // Start from what is saved; after that the member's edits are the truth until they save.
  const rows = edited ?? fromSaved;

  if (list.isPending || rows === null) {
    return (
      <Card className="space-y-3 p-4" aria-busy="true" aria-label="Loading conversation starters">
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-full" />
      </Card>
    );
  }
  if (list.isError) return <ErrorState error={list.error} onRetry={() => void list.refetch()} />;

  const max = list.data?.max_items ?? 4;
  const automations = options.data?.items ?? [];
  const change = (key: string, patch: Partial<Row>) =>
    setRows(rows.map((row) => (row.key === key ? { ...row, ...patch } : row)));

  const onSave = () => {
    setProblems({});
    save.mutate(
      {
        items: rows.map((row) => ({
          question: row.question,
          automation_id: row.target && row.target !== AI ? row.target : null,
          answer_with_ai: row.target === AI,
        })),
      },
      {
        onSuccess: (result) => {
          setRows(rowsOf(result.items));
          if (result.sync_error) toast.error(`Saved here, but ${network} didn't take the list.`);
          else toast.success(`Saved. ${network} shows these in new chats.`);
        },
        onError: (caught) => {
          if (caught instanceof ApiError && caught.errors.length > 0) {
            const next: Record<string, string> = {};
            for (const problem of caught.errors) next[problem.field] = problem.message;
            setProblems(next);
          } else {
            toastError(caught);
          }
        },
      },
    );
  };

  return (
    <div className="space-y-4">
      <p className="text-sm text-fg-secondary">
        Up to {max} questions that show at the top of a new chat in the {network} app. They don&apos;t show on
        desktop. A tap starts the automation you choose, or the AI answers.
      </p>
      <Card className="space-y-3 p-4">
        {rows.length === 0 ? <p className="text-sm text-fg-secondary">No conversation starters yet.</p> : null}
        <ul className="space-y-3" aria-label="Conversation starters">
          {rows.map((row, index) => (
            <li key={row.key} className="grid gap-2 sm:grid-cols-[1fr_16rem_auto] sm:items-start">
              <div className="space-y-1">
                <Input
                  aria-label={`Question ${index + 1}`}
                  value={row.question}
                  maxLength={MAX_QUESTION}
                  placeholder="What are your opening hours?"
                  aria-invalid={problems[`items.${index}.question`] ? true : undefined}
                  onChange={(event) => change(row.key, { question: event.target.value })}
                />
                {problems[`items.${index}.question`] ? (
                  <p className="text-xs text-danger-fg">{problems[`items.${index}.question`]}</p>
                ) : null}
              </div>
              <div className="space-y-1">
                <Select value={row.target} onValueChange={(value) => change(row.key, { target: value })}>
                  <SelectTrigger aria-label={`Answer for question ${index + 1}`} className="w-full">
                    <SelectValue placeholder="Choose what happens" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={AI}>Answer with AI</SelectItem>
                    {automations.map((automation) => (
                      <SelectItem key={automation.id} value={automation.id}>
                        {automation.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {problems[`items.${index}.automation_id`] ? (
                  <p className="text-xs text-danger-fg">{problems[`items.${index}.automation_id`]}</p>
                ) : null}
              </div>
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Remove question ${index + 1}`}
                onClick={() => setRows(rows.filter((r) => r.key !== row.key))}
              >
                <Trash2 aria-hidden />
              </Button>
            </li>
          ))}
        </ul>
        {automations.length === 0 ? (
          <p className="text-xs text-fg-secondary">
            To start an automation from a tap, make one with the &ldquo;{network} conversation starter&rdquo;
            trigger in{" "}
            <Link href={`/w/${slug}/automations` as Route} className="text-brand-fg underline underline-offset-4">
              Automations
            </Link>
            .
          </p>
        ) : null}
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="secondary"
            disabled={rows.length >= max}
            onClick={() => setRows([...rows, { key: `new-${rows.length}-${Date.now()}`, question: "", target: "" }])}
          >
            <Plus aria-hidden /> Add a starter
          </Button>
          <Button onClick={onSave} disabled={save.isPending}>
            {save.isPending ? "Saving…" : "Save"}
          </Button>
        </div>
      </Card>
      <SyncStatus
        syncedAt={list.data?.synced_at ?? null}
        error={list.data?.sync_error ?? null}
        syncing={sync.isPending}
        onSync={() => sync.mutate(undefined, { onError: (caught) => toastError(caught) })}
        hasStarters={(saved?.length ?? 0) > 0}
        network={network}
      />
    </div>
  );
}

function SyncStatus({
  syncedAt,
  error,
  syncing,
  onSync,
  hasStarters,
  network,
}: {
  syncedAt: string | null;
  error: string | null;
  syncing: boolean;
  onSync: () => void;
  hasStarters: boolean;
  network: string;
}) {
  if (!hasStarters && !error) return null;
  return (
    <Card className="flex flex-wrap items-center justify-between gap-3 p-4" role="status">
      <p className={error ? "text-sm text-danger-fg" : "text-sm text-fg-secondary"}>
        {error
          ? `${network} didn't take the list: ${error}`
          : syncedAt
            ? `On ${network} since ${new Date(syncedAt).toLocaleString()}.`
            : `Not sent to ${network} yet.`}
      </p>
      <Button variant="secondary" onClick={onSync} disabled={syncing}>
        {syncing ? "Sending…" : `Send to ${network} again`}
      </Button>
    </Card>
  );
}
