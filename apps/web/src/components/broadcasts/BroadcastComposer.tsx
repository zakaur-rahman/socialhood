"use client";

import { AlertTriangle, Info } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { PageFrame } from "@/components/shell/PageFrame";
import { ErrorState } from "@/components/states/ErrorState";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { ApiError } from "@/lib/api/errors";
import {
  useBroadcastAvailability,
  useBroadcastPreview,
  useContactFields,
  useContactSegments,
  useCreateBroadcast,
  useSocialAccounts,
  useStartBroadcast,
  useWhatsAppTemplates,
} from "@/lib/api/queries";
import type { BroadcastDraft, BroadcastPreview, VariableSpec } from "@/lib/api/types";
import { BUILT_IN_FIELDS, fillTemplate, formatCount, formatMoney } from "@/lib/broadcasts/format";
import { toastError } from "@/lib/toast-error";
import { useNow } from "@/lib/use-browser-state";
import { zonedToDate } from "@/lib/tz";
import { useCurrentWorkspace } from "@/lib/workspace";
import { BroadcastsUnavailable } from "./BroadcastsPage";
import { CARD_TITLE, ITEM_TITLE, META } from "@/styles/tokens";

/** One template variable as the form holds it. */
export type VariableState = { source: "field" | "fixed"; field: string; value: string; fallback: string };

const BLANK: VariableState = { source: "field", field: "first_name", value: "", fallback: "" };
const PREVIEW_DELAY_MS = 400;

/** The mapping the API stores: only what the chosen source uses. */
export function toSpecs(variables: VariableState[]): VariableSpec[] {
  return variables.map((v) =>
    v.source === "fixed"
      ? { source: "fixed", value: v.value }
      : { source: "field", field: v.field, fallback: v.fallback.trim() || null },
  );
}

/** Whether every variable says what it is. */
export function variablesReady(variables: VariableState[]): boolean {
  return variables.every((v) => (v.source === "fixed" ? v.value.trim() !== "" : v.field !== ""));
}

/** A value that follows `value` after it has stopped changing for `ms`. */
function useDebounced<T>(value: T, ms: number): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return settled;
}

/**
 * GR-23: a new broadcast. Pick the WhatsApp number, the segment and an approved template, say where
 * each variable comes from, see who is sent to and who is skipped, the message with a sample contact
 * and what Meta's rate card puts it at, then send now or at a time. Nothing is sent before the
 * confirmation. The preview is the server's: the same audience rules the send uses.
 */
export function BroadcastComposer() {
  const workspace = useCurrentWorkspace();
  const wid = workspace.id;
  const router = useRouter();
  const availability = useBroadcastAvailability(wid);
  const accounts = useSocialAccounts(wid);
  const segments = useContactSegments(wid);
  const fields = useContactFields(wid);
  const create = useCreateBroadcast(wid);
  const start = useStartBroadcast(wid);

  const [name, setName] = useState("");
  const [pickedAccount, setPickedAccount] = useState<string | null>(null);
  const [segmentId, setSegmentId] = useState<string | null>(null);
  const [templateKey, setTemplateKey] = useState<string | null>(null);
  const [variables, setVariables] = useState<VariableState[]>([]);
  const [when, setWhen] = useState<"now" | "later">("now");
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [problems, setProblems] = useState<Record<string, string>>({});

  const numbers = useMemo(
    () => (accounts.data ?? []).filter((a) => a.platform === "whatsapp" && a.status !== "disconnected"),
    [accounts.data],
  );
  const accountId = pickedAccount ?? (numbers.length === 1 ? numbers[0].id : null);
  const templates = useWhatsAppTemplates(wid, accountId ?? "", accountId !== null);
  const sendable = useMemo(() => (templates.data ?? []).filter((t) => t.category !== "authentication"), [templates.data]);
  const template = sendable.find((t) => `${t.name}|${t.language}` === templateKey) ?? null;
  const segment = segments.data?.find((s) => s.id === segmentId) ?? null;

  const draft = useMemo<BroadcastDraft | null>(() => {
    if (!accountId || !segmentId || !template || !variablesReady(variables)) return null;
    if (variables.length !== template.param_count) return null;
    return {
      social_account_id: accountId,
      segment_id: segmentId,
      template_name: template.name,
      template_language: template.language,
      variables: toSpecs(variables),
    };
  }, [accountId, segmentId, template, variables]);
  const draftKey = draft ? JSON.stringify(draft) : null;
  const settledKey = useDebounced(draftKey, PREVIEW_DELAY_MS);
  const settledDraft = useMemo<BroadcastDraft | null>(() => (settledKey ? (JSON.parse(settledKey) as BroadcastDraft) : null), [settledKey]);
  const preview = useBroadcastPreview(wid, settledDraft);
  const result = preview.data;

  const customFields = fields.data?.items ?? [];
  const scheduledAt = useMemo(() => {
    if (when !== "later") return null;
    return zonedToDate(date, time, workspace.timezone);
  }, [when, date, time, workspace.timezone]);
  const now = useNow();
  const scheduleOk = when === "now" || (scheduledAt !== null && scheduledAt.getTime() > now.getTime() + 60_000);
  const waiting = draftKey !== settledKey || preview.isPending;
  const canSend =
    draft !== null &&
    name.trim() !== "" &&
    scheduleOk &&
    !waiting &&
    result !== undefined &&
    result.audience.eligible > 0 &&
    (result.problems ?? []).length === 0;

  function chooseTemplate(key: string) {
    const next = sendable.find((t) => `${t.name}|${t.language}` === key);
    setTemplateKey(key);
    // One row per variable; a row already filled in keeps what was typed.
    setVariables((current) => Array.from({ length: next?.param_count ?? 0 }, (_, i) => current[i] ?? BLANK));
    setProblems({});
  }

  function setVariable(index: number, change: Partial<VariableState>) {
    setVariables((current) => current.map((v, i) => (i === index ? { ...v, ...change } : v)));
  }

  async function submit(mode: "draft" | "send") {
    if (!draft) return;
    setProblems({});
    let id: string;
    try {
      const created = await create.mutateAsync({ ...draft, name: name.trim() });
      id = created.id;
    } catch (error) {
      if (error instanceof ApiError && error.errors.length > 0) {
        setProblems(Object.fromEntries(error.errors.map((e) => [e.field, e.message])));
      } else {
        toastError(error);
      }
      setConfirming(false);
      return;
    }
    const detail = `/w/${workspace.slug}/broadcasts/${id}` as Route;
    if (mode === "draft") {
      toast.success("Draft saved");
      router.push(detail);
      return;
    }
    try {
      await start.mutateAsync({ id, scheduledAt: scheduledAt?.toISOString() });
      toast.success(scheduledAt ? "Broadcast scheduled" : "Broadcast started");
    } catch (error) {
      // The draft is kept: the broadcast page says what stopped it and can send it again.
      toastError(error);
    }
    router.push(detail);
  }

  if (availability.isPending || accounts.isPending || segments.isPending) {
    return (
      <PageFrame title="New broadcast">
        <Skeleton className="h-64 w-full" />
      </PageFrame>
    );
  }
  if (availability.data?.enabled !== true) return <BroadcastsUnavailable />;
  const back = { href: `/w/${workspace.slug}/broadcasts` as Route, label: "Broadcasts" };
  if (!availability.data.plan_allowed) {
    return (
      <PageFrame title="New broadcast" back={back}>
        <Alert tone="brand" variant="outline">
          <AlertDescription>
            Broadcasts are part of Pro.{" "}
            <Link href={`/w/${workspace.slug}/settings/billing` as Route} className="text-brand-fg underline-offset-4 hover:underline">
              See plans
            </Link>
          </AlertDescription>
        </Alert>
      </PageFrame>
    );
  }
  if (accounts.isError) {
    return (
      <PageFrame title="New broadcast" back={back}>
        <ErrorState error={accounts.error} onRetry={() => void accounts.refetch()} />
      </PageFrame>
    );
  }

  const sampleText = result?.sample.text ?? (template ? fillTemplate(template.body, []) : "");

  return (
    <PageFrame title="New broadcast" back={back}>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,24rem)]">
        <div className="space-y-5">
          <Card className="space-y-4">
            <h2 className={CARD_TITLE}>What and who</h2>
            <div className="space-y-1.5">
              <label htmlFor="broadcast-name" className={ITEM_TITLE}>
                Name
              </label>
              <Input
                id="broadcast-name"
                value={name}
                maxLength={80}
                onChange={(event) => setName(event.target.value)}
                placeholder="Diwali sale"
              />
              <p className={META}>Only your team sees it.</p>
              {problems.name ? <p className="text-sm text-danger-fg">{problems.name}</p> : null}
            </div>

            <div className="space-y-1.5">
              <p className={ITEM_TITLE}>WhatsApp number</p>
              {numbers.length === 0 ? (
                <p className="text-sm text-fg-secondary">
                  Connect a WhatsApp number first.{" "}
                  <Link href={`/w/${workspace.slug}/settings/connections` as Route} className="text-brand-fg underline-offset-4 hover:underline">
                    Open connections
                  </Link>
                </p>
              ) : (
                <Select
                  value={accountId ?? ""}
                  onValueChange={(value) => {
                    setPickedAccount(value);
                    setTemplateKey(null);
                    setVariables([]);
                  }}
                >
                  <SelectTrigger aria-label="WhatsApp number" size="lg" className="w-full">
                    <SelectValue placeholder="Choose a number" />
                  </SelectTrigger>
                  <SelectContent>
                    {numbers.map((account) => (
                      <SelectItem key={account.id} value={account.id}>
                        {account.display_name ?? account.username ?? "WhatsApp number"}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
              {problems.social_account_id ? <p className="text-sm text-danger-fg">{problems.social_account_id}</p> : null}
            </div>

            <div className="space-y-1.5">
              <p className={ITEM_TITLE}>Who gets it</p>
              {(segments.data ?? []).length === 0 ? (
                <p className="text-sm text-fg-secondary">
                  Save a segment on the Contacts page first, then pick it here.{" "}
                  <Link href={`/w/${workspace.slug}/contacts` as Route} className="text-brand-fg underline-offset-4 hover:underline">
                    Open contacts
                  </Link>
                </p>
              ) : (
                <Select value={segmentId ?? ""} onValueChange={setSegmentId}>
                  <SelectTrigger aria-label="Segment" size="lg" className="w-full">
                    <SelectValue placeholder="Choose a segment" />
                  </SelectTrigger>
                  <SelectContent>
                    {(segments.data ?? []).map((s) => (
                      <SelectItem key={s.id} value={s.id}>
                        {s.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
              <p className={META}>Only people on this WhatsApp number who agreed to marketing messages are sent to.</p>
              {problems.segment_id ? <p className="text-sm text-danger-fg">{problems.segment_id}</p> : null}
            </div>
          </Card>

          <Card className="space-y-4">
            <h2 className={CARD_TITLE}>Message</h2>
            <div className="space-y-1.5">
              <p className={ITEM_TITLE}>Approved template</p>
              {accountId === null ? (
                <p className="text-sm text-fg-secondary">Choose a number to see its templates.</p>
              ) : templates.isPending ? (
                <Skeleton className="h-10 w-full" />
              ) : templates.isError ? (
                <ErrorState error={templates.error} onRetry={() => void templates.refetch()} size="compact" />
              ) : sendable.length === 0 ? (
                <p className="text-sm text-fg-secondary">
                  This number has no approved templates yet. Create one in Meta&apos;s WhatsApp Manager and it appears here once it is approved.
                </p>
              ) : (
                <Select value={templateKey ?? ""} onValueChange={chooseTemplate}>
                  <SelectTrigger aria-label="Template" size="lg" className="w-full">
                    <SelectValue placeholder="Choose a template" />
                  </SelectTrigger>
                  <SelectContent>
                    {sendable.map((t) => (
                      <SelectItem key={`${t.name}|${t.language}`} value={`${t.name}|${t.language}`}>
                        {t.name} ({t.language}), {t.category}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
              {problems.template_name ? <p className="text-sm text-danger-fg">{problems.template_name}</p> : null}
            </div>

            {template ? (
              <>
                <p className="whitespace-pre-wrap rounded-lg bg-field p-3 text-sm" data-testid="template-body">
                  {template.body}
                </p>
                {variables.map((variable, index) => (
                  <VariableRow
                    key={index}
                    number={index + 1}
                    variable={variable}
                    customFields={customFields.map((f) => ({ value: f.key, label: f.label }))}
                    onChange={(change) => setVariable(index, change)}
                  />
                ))}
                {problems.variables ? <p className="text-sm text-danger-fg">{problems.variables}</p> : null}
              </>
            ) : null}
          </Card>

          <Card className="space-y-3">
            <h2 className={CARD_TITLE}>When</h2>
            <ToggleGroup aria-label="When" value={when} onValueChange={(value) => value && setWhen(value as "now" | "later")}>
              <ToggleGroupItem value="now">Send now</ToggleGroupItem>
              <ToggleGroupItem value="later">Schedule</ToggleGroupItem>
            </ToggleGroup>
            {when === "later" ? (
              <div className="flex flex-wrap items-end gap-3">
                <div className="space-y-1.5">
                  <label htmlFor="broadcast-date" className={ITEM_TITLE}>
                    Date
                  </label>
                  <Input id="broadcast-date" type="date" value={date} onChange={(event) => setDate(event.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="broadcast-time" className={ITEM_TITLE}>
                    Time
                  </label>
                  <Input id="broadcast-time" type="time" value={time} onChange={(event) => setTime(event.target.value)} />
                </div>
                <p className={META}>In {workspace.timezone}. The audience is fixed when it starts.</p>
              </div>
            ) : null}
          </Card>
        </div>

        <div className="space-y-5">
          <Card className="space-y-3" aria-live="polite" data-testid="broadcast-preview">
            <h2 className={CARD_TITLE}>Preview</h2>
            {draft === null ? (
              <p className="text-sm text-fg-secondary">Choose a number, a segment and a template to see who it reaches and what it costs.</p>
            ) : result === undefined ? (
              preview.isError ? (
                <ErrorState error={preview.error} onRetry={() => void preview.refetch()} size="compact" />
              ) : (
                <Skeleton className="h-40 w-full" />
              )
            ) : (
              <PreviewBody result={result} sampleText={sampleText} fetching={preview.isFetching || waiting} />
            )}
          </Card>

          <div className="flex flex-wrap gap-2">
            <Button size="lg" disabled={!canSend} onClick={() => setConfirming(true)} loading={create.isPending || start.isPending}>
              {when === "later" ? "Schedule broadcast" : "Send broadcast"}
            </Button>
            <Button
              size="lg"
              variant="secondary"
              disabled={draft === null || name.trim() === "" || create.isPending}
              onClick={() => void submit("draft")}
            >
              Save as draft
            </Button>
          </div>
        </div>
      </div>

      <AlertDialog open={confirming} onOpenChange={setConfirming}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{when === "later" ? "Schedule this broadcast?" : "Send this broadcast?"}</AlertDialogTitle>
            <AlertDialogDescription>
              {result
                ? `${formatCount(result.audience.eligible)} ${result.audience.eligible === 1 ? "person" : "people"} in ${segment?.name ?? "the segment"} will get it. `
                : ""}
              {result
                ? `Meta charges your WhatsApp Business Account about ${formatMoney(result.cost.total, result.cost.currency)}. `
                : ""}
              Anyone who replies STOP is removed from future broadcasts. Messages already sent can&apos;t be taken back.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Not yet</AlertDialogCancel>
            <AlertDialogAction onClick={() => void submit("send")}>{when === "later" ? "Schedule" : "Send"}</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </PageFrame>
  );
}

/** One template variable's source (also used by the sequence editor's template steps, GR-24). */
export function VariableRow({
  number,
  variable,
  customFields,
  onChange,
}: {
  number: number;
  variable: VariableState;
  customFields: { value: string; label: string }[];
  onChange: (change: Partial<VariableState>) => void;
}) {
  const options = [...BUILT_IN_FIELDS, ...customFields];
  return (
    <fieldset className="space-y-2 rounded-lg border border-line p-3">
      <legend className={`${ITEM_TITLE} px-1`}>Variable {number}</legend>
      <ToggleGroup
        aria-label={`Variable ${number} comes from`}
        value={variable.source}
        onValueChange={(value) => value && onChange({ source: value as "field" | "fixed" })}
      >
        <ToggleGroupItem value="field">A contact field</ToggleGroupItem>
        <ToggleGroupItem value="fixed">The same text</ToggleGroupItem>
      </ToggleGroup>
      {variable.source === "field" ? (
        <div className="flex flex-wrap gap-3">
          <Select value={variable.field} onValueChange={(value) => onChange({ field: value })}>
            <SelectTrigger aria-label={`Variable ${number} field`} size="lg" className="min-w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {options.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            aria-label={`Variable ${number} when empty`}
            className="min-w-44 flex-1"
            maxLength={200}
            value={variable.fallback}
            onChange={(event) => onChange({ fallback: event.target.value })}
            placeholder={variable.field === "first_name" ? "there" : "Write this when it is empty"}
          />
        </div>
      ) : (
        <Input
          aria-label={`Variable ${number} text`}
          maxLength={1024}
          value={variable.value}
          onChange={(event) => onChange({ value: event.target.value })}
          placeholder="31 October"
        />
      )}
    </fieldset>
  );
}

function PreviewBody({
  result,
  sampleText,
  fetching,
}: {
  result: BroadcastPreview;
  sampleText: string;
  fetching: boolean;
}) {
  const { audience, cost, quota, number } = result;
  const skipped = audience.opted_out + audience.no_consent + audience.missing_value;
  return (
    <div className="space-y-4" data-fetching={fetching}>
      <div>
        <p className="text-2xl font-semibold tabular-nums" data-testid="eligible">
          {formatCount(audience.eligible)} {audience.eligible === 1 ? "person" : "people"}
        </p>
        <p className={META}>of {formatCount(audience.matching)} in this segment on this number</p>
      </div>
      {skipped > 0 ? (
        <ul className="space-y-0.5 text-sm text-fg-secondary" data-testid="skipped">
          {audience.opted_out > 0 ? <li>{formatCount(audience.opted_out)} skipped: asked not to get marketing messages</li> : null}
          {audience.no_consent > 0 ? <li>{formatCount(audience.no_consent)} skipped: haven&apos;t agreed to marketing messages</li> : null}
          {audience.missing_value > 0 ? <li>{formatCount(audience.missing_value)} skipped: a variable has no value for them</li> : null}
        </ul>
      ) : null}

      <div className="rounded-lg bg-field p-3">
        <p className={META}>
          {result.sample.contact_name ? `Sample message for ${result.sample.contact_name}` : "Sample message"}
        </p>
        <p className="mt-1 whitespace-pre-wrap text-sm" data-testid="sample">
          {sampleText}
        </p>
      </div>

      <div className="space-y-1">
        <p className="text-sm">
          About <span className="font-semibold tabular-nums">{formatMoney(cost.total, cost.currency)}</span> from Meta
          <Badge tone="neutral" className="ml-2">
            {cost.category}
          </Badge>
        </p>
        <p className={META}>
          {`${formatMoney(cost.per_message, cost.currency)} a message, from Meta's rate card for India as of ${cost.as_of}`}
          {cost.verified ? "." : " (typed in by hand, not yet checked against Meta)."} Meta bills your WhatsApp Business
          Account directly. We add nothing.
        </p>
      </div>

      <p className={META}>
        {formatCount(quota.remaining)} of your {formatCount(quota.limit)} monthly broadcast recipients are left.
      </p>
      <p className={META}>
        {number.limit_known && number.daily_limit
          ? `This number can message ${formatCount(number.daily_limit)} people a day`
          : number.limit_known
            ? "This number has no daily limit"
            : `We don't know this number's daily limit, so we assume ${formatCount(number.daily_limit ?? 250)} people a day`}
        {number.days_to_send > 1 ? `, so this takes about ${number.days_to_send} days.` : "."}
      </p>

      {(result.problems ?? []).length > 0 ? (
        <Alert tone="warning" variant="soft" icon={<AlertTriangle />} data-testid="problems">
          <AlertDescription>
            <ul className="space-y-1">
              {(result.problems ?? []).map((problem) => (
                <li key={problem}>{problem}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      ) : null}
      {number.quality_rating === "yellow" ? (
        <Alert tone="warning" variant="soft" icon={<Info />}>
          <AlertDescription>WhatsApp rates this number&apos;s quality Medium. A broadcast pauses by itself if it drops.</AlertDescription>
        </Alert>
      ) : null}
    </div>
  );
}
