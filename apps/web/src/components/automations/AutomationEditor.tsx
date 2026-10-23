"use client";

import { AlertCircle, Check, Clock, Copy, EllipsisVertical, Pause, Play, RotateCw, Trash2 } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { BackLink } from "@/components/shell/PageFrame";
import { EmptyState } from "@/components/states/EmptyState";
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
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { ApiError, toApiError } from "@/lib/api/errors";
import {
  useActivateAutomation,
  useAutomation,
  useDeleteAutomation,
  useDuplicateAutomation,
  useFlowFields,
  useFlowTags,
  usePauseAutomation,
  useSocialAccounts,
  useStartFlow,
  useWorkspace,
} from "@/lib/api/queries";
import type { Automation, AutomationDefinition, DisplayStatus, QueueInfo, SurgeOrder } from "@/lib/api/types";
import {
  clearFieldErrors,
  DEFAULT_NAME,
  fieldErrors,
  firstIncompleteStep,
  stepComplete,
  stepOfField,
  stepsWithErrors,
  toDefinition,
  visibleSteps,
  type FieldErrors,
  type StepId,
} from "@/lib/automations/definition";
import { instagramAccounts } from "@/lib/automations/accounts";
import { flowComplete, placeErrors, type StepErrors } from "@/lib/automations/flow";
import { queueBanner, shortDateTime, STATUS_LABEL, SURGE_LABEL } from "@/lib/automations/format";
import { errorMessage } from "@/lib/copy";
import { toastError } from "@/lib/toast-error";
import type { Tone } from "@/lib/ui/tone";
import { useNow } from "@/lib/use-browser-state";
import { cn } from "@/lib/utils";
import { useCurrentWorkspace } from "@/lib/workspace";

import { focusFlowStep } from "./flow/StepTree";
import { useFlowDraft } from "./flow/use-flow-draft";
import { SidePanel } from "./SidePanel";
import { focusStep, type StepState } from "./StepCard";
import { KeywordsStep } from "./steps/KeywordsStep";
import { PostsStep } from "./steps/PostsStep";
import { SettingsStep } from "./steps/SettingsStep";
import { AdsStep } from "./steps/AdsStep";
import { StoriesStep } from "./steps/StoriesStep";
import { ThenFlow } from "./steps/ThenFlow";
import { ThenStep, type Uploader } from "./steps/ThenStep";
import { WhenStep } from "./steps/WhenStep";
import { editorHref } from "./TemplateGallery";
import { useAutosave, type SaveStatus } from "./use-autosave";

const STATUS_TONE: Record<DisplayStatus, Tone> = {
  draft: "neutral",
  scheduled: "brand",
  active: "success",
  paused: "warning",
  ended: "neutral",
};

/** UX-SCR-03: loads the automation, then the editor keyed by it. */
export function AutomationEditor({ id, upload }: { id: string; upload?: Uploader }) {
  const workspace = useCurrentWorkspace();
  const automation = useAutomation(workspace.id, id);
  if (automation.isPending) return <EditorSkeleton />;
  if (automation.isError) {
    if (automation.error instanceof ApiError && automation.error.status === 404) {
      return (
        <EmptyState
          className="flex-1"
          title="Automation not found"
          body="It may have been deleted."
          action={
            <Link
              href={`/w/${workspace.slug}/automations` as Route}
              className="text-sm text-brand-fg underline-offset-4 hover:underline"
            >
              Back to automations
            </Link>
          }
        />
      );
    }
    return <ErrorState error={automation.error} onRetry={() => void automation.refetch()} />;
  }
  return <Editor initial={automation.data} upload={upload} />;
}

function Editor({ initial, upload }: { initial: Automation; upload?: Uploader }) {
  const workspace = useCurrentWorkspace();
  const wid = workspace.id;
  const slug = workspace.slug;
  const timeZone = workspace.timezone;
  const now = useNow();
  const router = useRouter();
  const searchParams = useSearchParams();

  // The server's view (status, overlaps, queue) follows every save; the draft is what the user typed.
  const server = useAutomation(wid, initial.id).data ?? initial;
  const details = useWorkspace(wid);
  const disclosure = details.data?.automation_disclosure ?? null;
  const allAccounts = useSocialAccounts(wid);
  const accounts = useMemo(() => instagramAccounts(allAccounts.data ?? []), [allAccounts.data]);

  const { draft, update, flush: flushSettings, discard, status: settingsStatus, error } = useAutosave(wid, initial);
  // GR-13: an automation saved as a flow edits its steps; one on its message settings shows its
  // message as the first step, and the first step added turns it into a flow.
  const flow = useFlowDraft(wid, server);
  const flowMode = flow.phase !== "off";
  const startFlow = useStartFlow(wid, server.id);
  const flowTags = useFlowTags(wid, flowMode);
  const flowFields = useFlowFields(wid, flowMode);
  const flowFlush = flow.flush;
  const flush = useCallback(async () => (await flushSettings()) && (await flowFlush()), [flushSettings, flowFlush]);
  const status: SaveStatus =
    settingsStatus === "error" || flow.status === "error"
      ? "error"
      : settingsStatus === "saving" || flow.status === "saving"
        ? "saving"
        : "saved";
  const [activationErrors, setActivationErrors] = useState<FieldErrors>({});
  const [flowActivationErrors, setFlowActivationErrors] = useState<StepErrors>({});
  const clearFlowActivationErrors = useCallback(
    (id: string) =>
      setFlowActivationErrors((current) => {
        if (!(id in current)) return current;
        const rest = { ...current };
        delete rest[id];
        return rest;
      }),
    [],
  );
  const [mediaUrl, setMediaUrl] = useState<string | null>(initial.message_media_url ?? null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  // The confirmation opens from a menu item, which is gone when it closes: focus goes back to ⋯.
  const menuTrigger = useRef<HTMLButtonElement>(null);

  const activate = useActivateAutomation(wid);
  const pause = usePauseAutomation(wid);
  const duplicate = useDuplicateAutomation(wid);
  const remove = useDeleteAutomation(wid);

  const change = useCallback(
    (patch: Partial<AutomationDefinition>) => {
      update(patch);
      setActivationErrors((current) => clearFieldErrors(current, Object.keys(patch)));
    },
    [update],
  );

  // ---- errors per step: activation (FR-AUT-02) and a rejected save
  const saveErrors = error?.code === "validation_error" ? fieldErrors(error.errors) : {};
  const errors: FieldErrors = { ...saveErrors, ...activationErrors };
  const errorSteps = stepsWithErrors(errors);
  const steps = visibleSteps(draft.trigger);
  const flowReady =
    flow.phase === "ready" &&
    flowComplete(flow.tree, {
      disclosure,
      fields: (flowFields.data ?? []).map((field) => ({ key: field.key, type: field.type })),
      tagIds: new Set((flowTags.data ?? []).map((tag) => tag.id)),
    });
  const flowErrored = Object.keys(flow.saveErrors).length > 0 || Object.keys(flowActivationErrors).length > 0;
  const stateOf = (step: StepId): StepState => {
    if (errorSteps.has(step) || (step === "then" && flowErrored)) return "error";
    if (step === "then" && flowMode) return flowReady ? "complete" : "incomplete";
    return stepComplete(step, draft, disclosure) ? "complete" : "incomplete";
  };
  const unplaced = Object.entries(errors).filter(([field]) => {
    const step = stepOfField(field);
    return !step || (step !== "name" && !steps.includes(step));
  });

  // ---- opened from the gallery: go to the first step that still needs something (UX-SCR-11)
  const [initialFocus] = useState<StepId | null>(() =>
    searchParams.get("focus") === "first" ? firstIncompleteStep(toDefinition(initial)) : null,
  );
  useEffect(() => {
    if (!initialFocus) return;
    focusStep(initialFocus);
    router.replace(editorHref(slug, initial.id));
  }, [initialFocus, initial.id, router, slug]);

  const onActivate = async () => {
    if (!(await flush())) {
      toast.error("Your latest changes aren't saved yet. Fix what's shown, then activate.");
      return;
    }
    activate.mutate(server.id, {
      onSuccess: (result) => {
        setActivationErrors({});
        setFlowActivationErrors({});
        toast.success(
          result.display_status === "scheduled" && result.starts_at
            ? `Scheduled. It starts ${shortDateTime(result.starts_at, timeZone)}.`
            : "Active. It answers new messages from now on.",
        );
      },
      onError: (caught) => {
        const apiError = toApiError(caught);
        if (apiError.code !== "validation_error" || apiError.errors.length === 0) {
          toastError(apiError); // a plan limit (402) is the upgrade dialog's to say
          return;
        }
        const next = fieldErrors(apiError.errors);
        setActivationErrors(next);
        const placed = placeErrors(
          apiError.errors.filter((item) => item.field.startsWith("flow.")),
          flow.ids,
        );
        setFlowActivationErrors(placed.byStep);
        const withErrors = stepsWithErrors(next);
        const first = steps.find((step) => withErrors.has(step));
        const firstFlowStep = flow.ids.find((id) => id in placed.byStep);
        if (first === "then" && firstFlowStep) requestAnimationFrame(() => focusFlowStep(firstFlowStep, { field: true }));
        else if (first) requestAnimationFrame(() => focusStep(first, { field: false }));
        toast.error(
          apiError.errors.length === 1
            ? "One thing to finish before this can go live."
            : `${apiError.errors.length} things to finish before this can go live.`,
        );
      },
    });
  };

  const onPause = () =>
    pause.mutate(server.id, {
      onSuccess: () => toast.success("Paused. It won't answer until you activate it again."),
      onError: (caught) => toastError(caught),
    });

  const onDuplicate = async () => {
    await flush();
    duplicate.mutate(server.id, {
      onSuccess: (copy) => {
        toast.success(`Duplicated. You're editing ${copy.name}.`);
        router.push(editorHref(slug, copy.id));
      },
      onError: (caught) => toastError(caught),
    });
  };

  const onDelete = async () => {
    await flush();
    remove.mutate(server.id, {
      onSuccess: () => {
        discard();
        toast.success(`Deleted ${draft.name}`);
        router.push(`/w/${slug}/automations` as Route);
      },
      onError: (caught) => toastError(caught),
    });
  };

  const active = server.status === "active";
  const statusBusy = activate.isPending || pause.isPending;
  const account = accounts.find((item) => item.id === draft.social_account_id);
  const nameError = errors.name;

  return (
    <div className="w-full p-4 md:p-6">
      <header className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-line pb-4">
        <h1 className="sr-only">{draft.name.trim() || DEFAULT_NAME}</h1>
        <div className="min-w-0 flex-1 basis-64">
          <BackLink href={`/w/${slug}/automations` as Route} label="Automations" />
          <input
            aria-label="Automation name"
            value={draft.name}
            maxLength={80}
            onChange={(event) => change({ name: event.target.value })}
            onBlur={() => {
              if (!draft.name.trim()) change({ name: DEFAULT_NAME });
            }}
            aria-invalid={nameError ? true : undefined}
            // The page title, edited in place: no field look until hovered or focused, then the
            // global focus outline; 40 px on touch like every control (DESIGN_SYSTEM §8.4).
            className="-mx-1 w-full rounded-md bg-transparent px-1 text-2xl font-semibold tracking-tight hover:bg-hover focus:bg-field pointer-coarse:min-h-10"
          />
          {nameError ? <p className="text-xs text-danger-fg">{nameError}</p> : null}
        </div>
        <Badge data-testid="status-pill" tone={STATUS_TONE[server.display_status]} size="md">
          {STATUS_LABEL[server.display_status]}
        </Badge>
        <SaveIndicator status={status} onRetry={() => void flush()} />
        {active ? (
          <Button variant="secondary" size="lg" onClick={onPause} disabled={statusBusy} loading={pause.isPending}>
            <Pause aria-hidden /> Pause
          </Button>
        ) : (
          <Button size="lg" onClick={() => void onActivate()} disabled={statusBusy} loading={activate.isPending}>
            <Play aria-hidden /> Activate
          </Button>
        )}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button ref={menuTrigger} variant="ghost" size="icon-lg" aria-label="More actions">
              <EllipsisVertical aria-hidden />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onSelect={() => void onDuplicate()} disabled={duplicate.isPending}>
              <Copy aria-hidden /> Duplicate
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="destructive" onSelect={() => setConfirmDelete(true)}>
              <Trash2 aria-hidden /> Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </header>
      {status === "error" && (error ?? flow.error) ? (
        <Alert tone="danger" icon={<AlertCircle />} className="mt-3">
          {(error ?? flow.error)?.code === "validation_error"
            ? "Some changes weren't saved. Fix the fields marked below."
            : errorMessage(error ?? flow.error)}
        </Alert>
      ) : null}

      <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-4 xl:col-start-1 xl:row-start-1 xl:max-w-[720px]">
          {server.queue.waiting > 0 ? (
            <QueueBanner queue={server.queue} order={draft.surge_order} onOrderChange={(order) => change({ surge_order: order })} />
          ) : null}
          {unplaced.length > 0 ? (
            <Alert tone="danger">
              <ul className="space-y-1">
                {unplaced.map(([field, message]) => (
                  <li key={field}>{message}</li>
                ))}
              </ul>
            </Alert>
          ) : null}
          <div className="relative pl-8">
            <span
              aria-hidden
              data-testid="step-line"
              data-active={server.display_status === "active"}
              className={cn(
                "absolute top-6 bottom-6 left-[11px] w-0.5 rounded-full",
                server.display_status === "active" ? "automation-line-active" : "bg-line-strong",
              )}
            />
            <div className="space-y-4">
              {steps.map((step) => {
                const state = stateOf(step);
                switch (step) {
                  case "when":
                    return (
                      <WhenStep key={step} draft={draft} change={change} errors={errors} state={state} accounts={accounts} slug={slug} />
                    );
                  case "posts":
                    if (draft.trigger === "story_reply") {
                      return (
                        <StoriesStep key={step} wid={wid} draft={draft} change={change} errors={errors} state={state} now={now} />
                      );
                    }
                    if (draft.trigger === "ad_click") {
                      return <AdsStep key={step} draft={draft} change={change} errors={errors} state={state} />;
                    }
                    return (
                      <PostsStep
                        key={step}
                        wid={wid}
                        draft={draft}
                        change={change}
                        errors={errors}
                        state={state}
                        knownPosts={server.posts}
                        timeZone={timeZone}
                      />
                    );
                  case "keywords":
                    return (
                      <KeywordsStep key={step} draft={draft} change={change} errors={errors} state={state} overlaps={server.overlaps} />
                    );
                  case "then":
                    return flowMode ? (
                      <ThenFlow
                        key={step}
                        wid={wid}
                        automationId={server.id}
                        draft={draft}
                        change={change}
                        errors={errors}
                        state={state}
                        plan={workspace.plan}
                        disclosure={disclosure}
                        upload={upload}
                        flow={flow}
                        activationErrors={flowActivationErrors}
                        clearActivationErrors={clearFlowActivationErrors}
                      />
                    ) : (
                      <ThenStep
                        key={step}
                        wid={wid}
                        draft={draft}
                        change={change}
                        errors={errors}
                        state={state}
                        plan={workspace.plan}
                        disclosure={disclosure}
                        mediaUrl={mediaUrl}
                        onMediaChange={setMediaUrl}
                        upload={upload}
                        startFlow={{
                          pending: startFlow.isPending,
                          reason: active ? "Pause this automation to add steps." : null,
                          onPick: (kind) => {
                            void (async () => {
                              if (!(await flushSettings())) {
                                toast.error("Your latest changes aren't saved yet. Fix what's shown, then add a step.");
                                return;
                              }
                              startFlow.mutate(kind, {
                                onSuccess: ({ tree }) => flow.begin(tree),
                                onError: (caught) => toastError(caught),
                              });
                            })();
                          },
                        }}
                      />
                    );
                  case "settings":
                    return (
                      <SettingsStep
                        key={step}
                        draft={draft}
                        change={change}
                        errors={errors}
                        state={state}
                        timeZone={timeZone}
                        disclosure={disclosure}
                        slug={slug}
                      />
                    );
                }
              })}
            </div>
          </div>
        </div>
        <Card
          asChild
          className="xl:sticky xl:top-6 xl:col-start-2 xl:row-start-1 xl:self-start"
        >
        <aside aria-label="Preview and results">
          <SidePanel
            wid={wid}
            slug={slug}
            automationId={server.id}
            draft={draft}
            accountUsername={account?.username ?? null}
            disclosure={disclosure}
            mediaUrl={mediaUrl}
            timeZone={timeZone}
            beforeTest={flush}
            flow={flowMode ? flow.definition : null}
            tags={flowTags.data ?? []}
          />
        </aside>
        </Card>

      </div>

      <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <AlertDialogContent
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            menuTrigger.current?.focus();
          }}
        >
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {draft.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              It stops answering at once and can&apos;t be restored. Messages it already sent stay in the inbox.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={() => void onDelete()}>
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

/** "Saved" only once the API has the latest edit; "Saving…" until then; "Not saved" with Retry. */
export function SaveIndicator({ status, onRetry }: { status: SaveStatus; onRetry: () => void }) {
  return (
    <div className="flex items-center gap-2 text-xs text-fg-secondary">
      <p role="status" aria-live="polite" data-testid="save-status" className="flex items-center gap-1">
        {status === "saved" ? (
          <>
            <Check className="size-3.5" aria-hidden /> Saved
          </>
        ) : status === "saving" ? (
          <>
            <Spinner size="sm" /> Saving…
          </>
        ) : (
          <span className="flex items-center gap-1 text-danger-fg">
            <AlertCircle className="size-3.5" aria-hidden /> Not saved
          </span>
        )}
      </p>
      {status === "error" ? (
        <Button variant="ghost" size="xs" onClick={onRetry}>
          <RotateCw aria-hidden /> Retry
        </Button>
      ) : null}
    </div>
  );
}

/** FR-AUT-10 / UX-SCR-12: DMs waiting in the account's private-reply queue, and the order in use. */
function QueueBanner({
  queue,
  order,
  onOrderChange,
}: {
  queue: QueueInfo;
  order: SurgeOrder;
  onOrderChange: (order: SurgeOrder) => void;
}) {
  return (
    <Alert
      tone="brand"
      icon={<Clock />}
      action={
        <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="secondary" size="sm">
            Change order
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuLabel>When busy</DropdownMenuLabel>
          <DropdownMenuRadioGroup value={order} onValueChange={(value) => onOrderChange(value as SurgeOrder)}>
            {(Object.keys(SURGE_LABEL) as SurgeOrder[]).map((value) => (
              <DropdownMenuRadioItem key={value} value={value}>
                {SURGE_LABEL[value]}
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>
      }
    >
      <p>
        <span className="font-medium tabular-nums">{queueBanner(queue)}</span>
        <span> · {SURGE_LABEL[order]}</span>
      </p>
    </Alert>
  );
}

function EditorSkeleton() {
  return (
    <div role="status" aria-busy="true" aria-label="Loading automation" className="w-full space-y-6 p-4 md:p-6">
      <div className="space-y-2 border-b border-line pb-4">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-7 w-64" />
      </div>
      <div className="max-w-[720px] space-y-4 pl-8">
        {Array.from({ length: 4 }, (_, i) => (
          <Card key={i} padding="roomy" className="space-y-3">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-9 w-full" />
          </Card>
        ))}
      </div>
    </div>
  );
}
