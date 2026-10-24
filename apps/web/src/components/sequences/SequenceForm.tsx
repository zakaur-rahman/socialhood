"use client";

import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react";
import type { Route } from "next";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { toast } from "sonner";

import { VariableRow } from "@/components/broadcasts/BroadcastComposer";
import { PageFrame } from "@/components/shell/PageFrame";
import { ErrorState } from "@/components/states/ErrorState";
import { Alert, AlertDescription } from "@/components/ui/alert";
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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api/errors";
import {
  useBroadcasts,
  useContactFields,
  useCreateSequence,
  useDeleteSequence,
  useSequenceAction,
  useSequencePreview,
  useSocialAccounts,
  useTags,
  useUpdateSequence,
  useWhatsAppTemplates,
} from "@/lib/api/queries";
import type { Sequence, SocialAccount, WhatsAppTemplate } from "@/lib/api/types";
import {
  CAPTURE_KINDS,
  ENTRY_STAGES,
  ENTRY_TYPES,
  SEQUENCE_STATUS,
  STOP_STAGES,
  UNIT_SECONDS,
  blankState,
  blankStep,
  dayOf,
  fromSequence,
  missingFor,
  templateKeyOf,
  toBody,
  type EditorState,
  type StepState,
  type Unit,
} from "@/lib/sequences/format";
import { toastError } from "@/lib/toast-error";
import { useCurrentWorkspace } from "@/lib/workspace";
import { CARD_TITLE, ITEM_TITLE, META } from "@/styles/tokens";

const PREVIEW_DELAY_MS = 400;
const PLATFORM_NAME = { instagram: "Instagram", whatsapp: "WhatsApp", facebook: "Messenger" } as const;
const NO_TEMPLATE = "none";
const ANY_BROADCAST = "any";
const MAX_STEPS = 20;

/** A value that follows `value` after it has stopped changing for `ms`. */
function useDebounced<T>(value: T, ms: number): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return settled;
}

function accountName(account: SocialAccount): string {
  const name = account.display_name ?? (account.username ? `@${account.username}` : account.phone_number);
  const platform = PLATFORM_NAME[account.platform as keyof typeof PLATFORM_NAME] ?? account.platform;
  return name ? `${name} (${platform})` : platform;
}

/**
 * GR-24: a sequence, as a form. Name and account, what starts it, the steps (each: how long to wait,
 * the message, on WhatsApp the template that goes after 24 hours, and whether it waits for business
 * hours), when it stops, and a preview from the server of when each step goes and what it sends. A
 * sequence that is on is read-only: pause it to change it (the API refuses otherwise). `children` is
 * shown below (the people in it).
 */
export function SequenceForm({ sequence, children }: { sequence?: Sequence; children?: ReactNode }) {
  const workspace = useCurrentWorkspace();
  const wid = workspace.id;
  const router = useRouter();
  const accounts = useSocialAccounts(wid);
  const tags = useTags(wid);
  const fields = useContactFields(wid);
  const create = useCreateSequence(wid);
  const update = useUpdateSequence(wid);
  const action = useSequenceAction(wid);
  const remove = useDeleteSequence(wid);

  const [state, setState] = useState<EditorState>(() => (sequence ? fromSequence(sequence) : blankState()));
  const [problems, setProblems] = useState<Record<string, string>>({});
  const [deleting, setDeleting] = useState(false);

  const locked = sequence?.status === "active";
  const usable = useMemo(
    () =>
      (accounts.data ?? []).filter(
        (a) => ["instagram", "whatsapp", "facebook"].includes(a.platform) && a.status !== "disconnected",
      ),
    [accounts.data],
  );
  const accountId = state.accountId ?? (!sequence && usable.length === 1 ? usable[0].id : null);
  const account = usable.find((a) => a.id === accountId) ?? null;
  const isWhatsApp = account?.platform === "whatsapp";
  const effective: EditorState = useMemo(() => ({ ...state, accountId }), [state, accountId]);
  const templates = useWhatsAppTemplates(wid, accountId ?? "", isWhatsApp);
  const sendable = useMemo<WhatsAppTemplate[]>(
    () => (templates.data ?? []).filter((t) => t.category !== "authentication"),
    [templates.data],
  );
  const broadcasts = useBroadcasts(wid, state.entryType === "broadcast_replied" && isWhatsApp);

  const body = useMemo(() => toBody(effective), [effective]);
  const bodyKey = body ? JSON.stringify(body) : null;
  const settledKey = useDebounced(bodyKey, PREVIEW_DELAY_MS);
  const settledBody = useMemo(() => (settledKey ? (JSON.parse(settledKey) as NonNullable<typeof body>) : null), [settledKey]);
  const preview = useSequencePreview(wid, locked ? null : settledBody);
  const missing = missingFor(effective);

  function change(patch: Partial<EditorState>) {
    setState((current) => ({ ...current, ...patch }));
    setProblems({});
  }
  function changeStep(index: number, patch: Partial<StepState>) {
    setState((current) => ({
      ...current,
      steps: current.steps.map((step, i) => (i === index ? { ...step, ...patch } : step)),
    }));
    setProblems({});
  }
  function moveStep(index: number, by: -1 | 1) {
    setState((current) => {
      const steps = [...current.steps];
      const target = index + by;
      if (target < 0 || target >= steps.length) return current;
      [steps[index], steps[target]] = [steps[target], steps[index]];
      return { ...current, steps };
    });
  }
  function chooseTemplate(index: number, key: string) {
    const template = sendable.find((t) => templateKeyOf(t) === key);
    if (key === NO_TEMPLATE || !template) return changeStep(index, { templateKey: null, variables: [] });
    const current = state.steps[index].variables;
    changeStep(index, {
      templateKey: key,
      variables: Array.from(
        { length: template.param_count },
        (_, i) => current[i] ?? { source: "field", field: "first_name", value: "", fallback: "" },
      ),
    });
  }
  function toggle(list: string[], value: string, on: boolean): string[] {
    return on ? [...list.filter((v) => v !== value), value] : list.filter((v) => v !== value);
  }

  async function save(thenActivate: boolean) {
    if (!body) return;
    setProblems({});
    let saved: Sequence;
    try {
      saved = sequence ? await update.mutateAsync({ id: sequence.id, body }) : await create.mutateAsync(body);
    } catch (error) {
      if (error instanceof ApiError && error.errors.length > 0) {
        setProblems(Object.fromEntries(error.errors.map((e) => [e.field, e.message])));
      } else {
        toastError(error);
      }
      return;
    }
    if (thenActivate) {
      try {
        await action.mutateAsync({ id: saved.id, action: "activate" });
        toast.success("Sequence is on");
      } catch (error) {
        // It is saved as a draft; the page says what stopped it from starting.
        toastError(error);
      }
    } else {
      toast.success(sequence ? "Changes saved" : "Draft saved");
    }
    if (!sequence) router.push(`/w/${workspace.slug}/sequences/${saved.id}` as Route);
  }

  async function run(which: "activate" | "pause") {
    if (!sequence) return;
    try {
      await action.mutateAsync({ id: sequence.id, action: which });
      toast.success(which === "activate" ? "Sequence is on" : "Sequence paused");
    } catch (error) {
      toastError(error);
    }
  }

  const back = { href: `/w/${workspace.slug}/sequences` as Route, label: "Sequences" };
  const title = sequence ? sequence.name : "New sequence";
  if (accounts.isPending || tags.isPending) {
    return (
      <PageFrame title={title} back={back}>
        <Skeleton className="h-64 w-full" />
      </PageFrame>
    );
  }
  if (accounts.isError) {
    return (
      <PageFrame title={title} back={back}>
        <ErrorState error={accounts.error} onRetry={() => void accounts.refetch()} />
      </PageFrame>
    );
  }

  const status = sequence ? SEQUENCE_STATUS[sequence.status] : null;
  const busy = create.isPending || update.isPending || action.isPending;
  const customFields = (fields.data?.items ?? []).map((f) => ({ value: f.key, label: f.label }));

  return (
    <PageFrame
      title={title}
      back={back}
      actions={
        <>
          {status ? <Badge tone={status.tone}>{status.label}</Badge> : null}
          {sequence?.status === "active" ? (
            <Button variant="secondary" size="lg" loading={action.isPending} onClick={() => void run("pause")}>
              Pause
            </Button>
          ) : null}
          {sequence && sequence.status !== "active" ? (
            <Button
              variant="secondary"
              size="lg"
              disabled={busy || (sequence.problems?.length ?? 0) > 0}
              onClick={() => void run("activate")}
            >
              Turn on
            </Button>
          ) : null}
          {sequence && sequence.status !== "active" ? (
            <Button variant="destructive-ghost" size="lg" onClick={() => setDeleting(true)}>
              <Trash2 aria-hidden /> Delete
            </Button>
          ) : null}
        </>
      }
    >
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,24rem)]">
        <fieldset disabled={locked} className="min-w-0 space-y-5">
          {locked ? (
            <Alert tone="brand" variant="outline">
              <AlertDescription>
                This sequence is on. Pause it to change it. People already in it carry on afterwards.
              </AlertDescription>
            </Alert>
          ) : null}
          {sequence && (sequence.problems?.length ?? 0) > 0 ? (
            <Alert tone="warning" variant="outline">
              <AlertDescription>{sequence.problems?.[0]}</AlertDescription>
            </Alert>
          ) : null}

          <Card className="space-y-4">
            <h2 className={CARD_TITLE}>Name and account</h2>
            <div className="space-y-1.5">
              <label htmlFor="sequence-name" className={ITEM_TITLE}>
                Name
              </label>
              <Input
                id="sequence-name"
                value={state.name}
                maxLength={80}
                onChange={(event) => change({ name: event.target.value })}
                placeholder="Welcome follow-up"
              />
              <p className={META}>Only your team sees it.</p>
              {problems.name ? <p className="text-sm text-danger-fg">{problems.name}</p> : null}
            </div>
            <div className="space-y-1.5">
              <p className={ITEM_TITLE}>Sends from</p>
              <Select
                value={accountId ?? ""}
                onValueChange={(value) =>
                  change({
                    accountId: value,
                    entryType: state.entryType === "broadcast_replied" ? "tagged" : state.entryType,
                    steps: state.steps.map((step) => ({ ...step, templateKey: null, variables: [] })),
                  })
                }
                disabled={Boolean(sequence?.enrolments && sequence.enrolments.active + sequence.enrolments.completed + sequence.enrolments.stopped > 0)}
              >
                <SelectTrigger aria-label="Account" size="lg" className="w-full">
                  <SelectValue placeholder="Choose an account" />
                </SelectTrigger>
                <SelectContent>
                  {usable.map((a) => (
                    <SelectItem key={a.id} value={a.id}>
                      {accountName(a)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {usable.length === 0 ? (
                <p className={META}>Connect an Instagram, WhatsApp or Messenger account first.</p>
              ) : null}
              {problems.social_account_id ? <p className="text-sm text-danger-fg">{problems.social_account_id}</p> : null}
            </div>
          </Card>

          <Card className="space-y-4">
            <h2 className={CARD_TITLE}>Starts when</h2>
            <Select value={state.entryType} onValueChange={(value) => change({ entryType: value as EditorState["entryType"] })}>
              <SelectTrigger aria-label="Starts when" size="lg" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ENTRY_TYPES.filter((t) => t.value !== "broadcast_replied" || isWhatsApp).map((t) => (
                  <SelectItem key={t.value} value={t.value}>
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {state.entryType === "tagged" ? (
              <div className="space-y-1.5">
                <Select value={state.tagId ?? ""} onValueChange={(value) => change({ tagId: value })}>
                  <SelectTrigger aria-label="Tag" size="lg" className="w-full">
                    <SelectValue placeholder="Choose a tag" />
                  </SelectTrigger>
                  <SelectContent>
                    {(tags.data ?? []).map((tag) => (
                      <SelectItem key={tag.id} value={tag.id}>
                        {tag.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {problems["entry.tag_id"] ? <p className="text-sm text-danger-fg">{problems["entry.tag_id"]}</p> : null}
              </div>
            ) : null}
            {state.entryType === "lead_stage" ? (
              <Select value={state.entryStage ?? ""} onValueChange={(value) => change({ entryStage: value })}>
                <SelectTrigger aria-label="Lead stage" size="lg" className="w-full">
                  <SelectValue placeholder="Choose a stage" />
                </SelectTrigger>
                <SelectContent>
                  {ENTRY_STAGES.map((stage) => (
                    <SelectItem key={stage.value} value={stage.value}>
                      {stage.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : null}
            {state.entryType === "captured" ? (
              <Select value={state.captureKind} onValueChange={(value) => change({ captureKind: value as EditorState["captureKind"] })}>
                <SelectTrigger aria-label="What they gave" size="lg" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CAPTURE_KINDS.map((kind) => (
                    <SelectItem key={kind.value} value={kind.value}>
                      {kind.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : null}
            {state.entryType === "broadcast_replied" ? (
              <Select
                value={state.broadcastId ?? ANY_BROADCAST}
                onValueChange={(value) => change({ broadcastId: value === ANY_BROADCAST ? null : value })}
              >
                <SelectTrigger aria-label="Broadcast" size="lg" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ANY_BROADCAST}>Any broadcast</SelectItem>
                  {(broadcasts.data?.items ?? []).map((b) => (
                    <SelectItem key={b.id} value={b.id}>
                      {b.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : null}
            <p className={META}>A person is in a sequence once at a time. The sequence only takes in people while it is on.</p>
          </Card>

          <section aria-labelledby="sequence-steps" className="space-y-3">
            <h2 id="sequence-steps" className={CARD_TITLE}>
              Steps
            </h2>
            <ol className="space-y-3">
              {state.steps.map((step, index) => (
                <li key={step.key}>
                  <StepCard
                    index={index}
                    count={state.steps.length}
                    step={step}
                    whatsapp={isWhatsApp}
                    templates={sendable}
                    templatesLoading={isWhatsApp && templates.isPending}
                    customFields={customFields}
                    problems={problems}
                    onChange={(patch) => changeStep(index, patch)}
                    onTemplate={(key) => chooseTemplate(index, key)}
                    onMove={(by) => moveStep(index, by)}
                    onRemove={() => change({ steps: state.steps.filter((_, i) => i !== index) })}
                  />
                </li>
              ))}
            </ol>
            <Button
              variant="secondary"
              onClick={() => change({ steps: [...state.steps, blankStep()] })}
              disabled={state.steps.length >= MAX_STEPS}
            >
              <Plus aria-hidden /> Add step
            </Button>
            {problems.steps ? <p className="text-sm text-danger-fg">{problems.steps}</p> : null}
          </section>

          <Card className="space-y-4">
            <h2 className={CARD_TITLE}>Stops when</h2>
            <label className="flex items-center justify-between gap-3">
              <span className="text-sm">They reply</span>
              <Switch
                checked={state.stopOnReply}
                onCheckedChange={(on) => change({ stopOnReply: on })}
                aria-label="Stop when they reply"
              />
            </label>
            {(tags.data ?? []).length > 0 ? (
              <fieldset className="space-y-2">
                <legend className={ITEM_TITLE}>One of these tags is added</legend>
                {(tags.data ?? []).map((tag) => (
                  <label key={tag.id} className="flex items-center gap-2 text-sm">
                    <Checkbox
                      checked={state.stopTagIds.includes(tag.id)}
                      onCheckedChange={(on) => change({ stopTagIds: toggle(state.stopTagIds, tag.id, on === true) })}
                    />
                    {tag.name}
                  </label>
                ))}
              </fieldset>
            ) : null}
            {(tags.data ?? []).length > 0 ? (
              <fieldset className="space-y-2">
                <legend className={ITEM_TITLE}>One of these tags is taken off</legend>
                {(tags.data ?? []).map((tag) => (
                  <label key={tag.id} className="flex items-center gap-2 text-sm">
                    <Checkbox
                      checked={state.stopRemovedTagIds.includes(tag.id)}
                      onCheckedChange={(on) =>
                        change({ stopRemovedTagIds: toggle(state.stopRemovedTagIds, tag.id, on === true) })
                      }
                    />
                    {tag.name}
                  </label>
                ))}
              </fieldset>
            ) : null}
            <fieldset className="space-y-2">
              <legend className={ITEM_TITLE}>Their lead stage becomes</legend>
              {STOP_STAGES.map((stage) => (
                <label key={stage.value} className="flex items-center gap-2 text-sm">
                  <Checkbox
                    checked={state.stopStages.includes(stage.value)}
                    onCheckedChange={(on) => change({ stopStages: toggle(state.stopStages, stage.value, on === true) })}
                  />
                  {stage.label}
                </label>
              ))}
            </fieldset>
            <label className="flex items-center justify-between gap-3">
              <span className="text-sm">Let people join again after they finish or are stopped</span>
              <Switch
                checked={state.allowReentry}
                onCheckedChange={(on) => change({ allowReentry: on })}
                aria-label="Let people join again"
              />
            </label>
          </Card>
        </fieldset>

        <div className="min-w-0 space-y-5">
          <Card className="space-y-3" aria-live="polite" data-testid="sequence-preview">
            <h2 className={CARD_TITLE}>Preview</h2>
            {locked ? (
              <p className="text-sm text-fg-secondary">Pause the sequence to change it and see a preview.</p>
            ) : body === null ? (
              <ul className="list-disc space-y-1 ps-5 text-sm text-fg-secondary">
                {missing.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            ) : preview.data === undefined ? (
              preview.isError ? (
                <ErrorState error={preview.error} onRetry={() => void preview.refetch()} size="compact" />
              ) : (
                <Skeleton className="h-32 w-full" />
              )
            ) : (
              <ol className="space-y-3">
                {preview.data.steps.map((step) => (
                  <li key={step.position} className="space-y-1" data-testid="preview-step">
                    <p className={ITEM_TITLE}>
                      {dayOf(step.after_seconds)}
                      <span className="ms-2 font-normal text-fg-secondary">
                        {step.sends === "template" ? "Template" : step.sends === "text" ? "Message" : "Nothing goes"}
                      </span>
                    </p>
                    {step.text ? <p className="whitespace-pre-wrap rounded-lg bg-field p-3 text-sm">{step.text}</p> : null}
                    {step.note ? <p className={META}>{step.note}</p> : null}
                  </li>
                ))}
              </ol>
            )}
            <p className={META}>Shown for a sample contact called Priya, as if each step ran on time.</p>
          </Card>

          {locked ? null : (
            <div className="flex flex-wrap gap-2">
              <Button size="lg" disabled={body === null || busy} loading={busy} onClick={() => void save(false)}>
                {sequence ? "Save changes" : "Save as draft"}
              </Button>
              {sequence ? null : (
                <Button size="lg" variant="secondary" disabled={body === null || busy} onClick={() => void save(true)}>
                  Save and turn on
                </Button>
              )}
            </div>
          )}
        </div>
      </div>

      {children}

      <AlertDialog open={deleting} onOpenChange={setDeleting}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this sequence?</AlertDialogTitle>
            <AlertDialogDescription>
              Its steps, the people in it and what it sent are removed from this page. Messages already sent stay in the
              conversations.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep it</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (!sequence) return;
                remove.mutate(sequence.id, {
                  onSuccess: () => {
                    toast.success("Sequence deleted");
                    router.push(back.href);
                  },
                  onError: (error) => toastError(error),
                });
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </PageFrame>
  );
}

const UNIT_OPTIONS = Object.keys(UNIT_SECONDS) as Unit[];

function StepCard({
  index,
  count,
  step,
  whatsapp,
  templates,
  templatesLoading,
  customFields,
  problems,
  onChange,
  onTemplate,
  onMove,
  onRemove,
}: {
  index: number;
  count: number;
  step: StepState;
  whatsapp: boolean;
  templates: WhatsAppTemplate[];
  templatesLoading: boolean;
  customFields: { value: string; label: string }[];
  problems: Record<string, string>;
  onChange: (patch: Partial<StepState>) => void;
  onTemplate: (key: string) => void;
  onMove: (by: -1 | 1) => void;
  onRemove: () => void;
}) {
  const where = `steps.${index}`;
  const template = templates.find((t) => templateKeyOf(t) === step.templateKey) ?? null;
  const first = index === 0;
  return (
    <Card className="space-y-3" data-testid="step-card">
      <div className="flex items-center justify-between gap-2">
        <h3 className={ITEM_TITLE}>Step {index + 1}</h3>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon-sm" aria-label={`Move step ${index + 1} up`} disabled={first} onClick={() => onMove(-1)}>
            <ArrowUp aria-hidden />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`Move step ${index + 1} down`}
            disabled={index === count - 1}
            onClick={() => onMove(1)}
          >
            <ArrowDown aria-hidden />
          </Button>
          <Button variant="ghost" size="icon-sm" aria-label={`Remove step ${index + 1}`} disabled={count === 1} onClick={onRemove}>
            <Trash2 aria-hidden />
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1.5">
          <label htmlFor={`step-${step.key}-amount`} className={ITEM_TITLE}>
            Wait
          </label>
          <div className="flex gap-2">
            <Input
              id={`step-${step.key}-amount`}
              type="number"
              inputMode="numeric"
              min={0}
              className="w-24"
              value={Number.isFinite(step.amount) ? step.amount : 0}
              onChange={(event) => onChange({ amount: Math.max(0, Number(event.target.value) || 0) })}
            />
            <Select value={step.unit} onValueChange={(value) => onChange({ unit: value as Unit })}>
              <SelectTrigger aria-label={`Step ${index + 1} unit`} size="lg" className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {UNIT_OPTIONS.map((unit) => (
                  <SelectItem key={unit} value={unit}>
                    {unit}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        {first ? (
          <p className={META}>after they enter</p>
        ) : (
          <Select value={step.from} onValueChange={(value) => onChange({ from: value as StepState["from"] })}>
            <SelectTrigger aria-label={`Step ${index + 1} counts from`} size="lg" className="min-w-52">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="previous">after the step before</SelectItem>
              <SelectItem value="entry">after they entered</SelectItem>
            </SelectContent>
          </Select>
        )}
      </div>

      <div className="space-y-1.5">
        <label htmlFor={`step-${step.key}-text`} className={ITEM_TITLE}>
          Message
        </label>
        <Textarea
          id={`step-${step.key}-text`}
          value={step.text}
          maxLength={1000}
          rows={3}
          onChange={(event) => onChange({ text: event.target.value })}
          placeholder="Hi {first_name}, did you get a chance to look at the catalogue?"
        />
        <p className={META}>
          {whatsapp
            ? "Sent while the 24-hour window is open. After that, WhatsApp only allows the template below."
            : "Sent only while the messaging window is open (24 hours after they last wrote). Otherwise the step is skipped."}
        </p>
        {problems[`${where}.text`] ? <p className="text-sm text-danger-fg">{problems[`${where}.text`]}</p> : null}
      </div>

      {whatsapp ? (
        <div className="space-y-2">
          <p className={ITEM_TITLE}>Template after 24 hours</p>
          {templatesLoading ? (
            <Skeleton className="h-10 w-full" />
          ) : templates.length === 0 ? (
            <p className="text-sm text-fg-secondary">
              This number has no approved templates yet, so this step is skipped once the window has closed.
            </p>
          ) : (
            <Select value={step.templateKey ?? NO_TEMPLATE} onValueChange={onTemplate}>
              <SelectTrigger aria-label={`Step ${index + 1} template`} size="lg" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NO_TEMPLATE}>No template</SelectItem>
                {templates.map((t) => (
                  <SelectItem key={templateKeyOf(t)} value={templateKeyOf(t)}>
                    {t.name} ({t.language}), {t.category}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          {problems[`${where}.template_name`] ? (
            <p className="text-sm text-danger-fg">{problems[`${where}.template_name`]}</p>
          ) : null}
          {template ? (
            <>
              <p className="whitespace-pre-wrap rounded-lg bg-field p-3 text-sm">{template.body}</p>
              <p className={META}>Templates go only to people who agreed to WhatsApp marketing messages.</p>
              {step.variables.map((variable, v) => (
                <VariableRow
                  key={v}
                  number={v + 1}
                  variable={variable}
                  customFields={customFields}
                  onChange={(patch) =>
                    onChange({ variables: step.variables.map((current, i) => (i === v ? { ...current, ...patch } : current)) })
                  }
                />
              ))}
              {problems[`${where}.variables`] ? (
                <p className="text-sm text-danger-fg">{problems[`${where}.variables`]}</p>
              ) : null}
            </>
          ) : null}
        </div>
      ) : null}

      <label className="flex items-center justify-between gap-3">
        <span className="text-sm">Only send during business hours</span>
        <Switch
          checked={step.respectHours}
          onCheckedChange={(on) => onChange({ respectHours: on })}
          aria-label={`Step ${index + 1} only in business hours`}
        />
      </label>
    </Card>
  );
}
