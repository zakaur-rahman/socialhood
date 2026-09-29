"use client";

import { AlertCircle, Check, Clock, Copy, EllipsisVertical, Loader2, Pause, Play, RotateCw, Trash2 } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

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
import { Button } from "@/components/ui/button";
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
import { ApiError, toApiError } from "@/lib/api/errors";
import {
  useActivateAutomation,
  useAutomation,
  useDeleteAutomation,
  useDuplicateAutomation,
  usePauseAutomation,
  useSocialAccounts,
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
import { queueBanner, shortDateTime, STATUS_LABEL, SURGE_LABEL } from "@/lib/automations/format";
import { errorMessage } from "@/lib/copy";
import { cn } from "@/lib/utils";
import { useCurrentWorkspace } from "@/lib/workspace";

import { SidePanel } from "./SidePanel";
import { focusStep, type StepState } from "./StepCard";
import { KeywordsStep } from "./steps/KeywordsStep";
import { PostsStep } from "./steps/PostsStep";
import { SettingsStep } from "./steps/SettingsStep";
import { ThenStep, type Uploader } from "./steps/ThenStep";
import { WhenStep } from "./steps/WhenStep";
import { editorHref } from "./TemplateGallery";
import { useAutosave, type SaveStatus } from "./use-autosave";

const STATUS_TONE: Record<DisplayStatus, string> = {
  draft: "bg-raised text-fg-secondary",
  scheduled: "bg-brand-soft text-brand-fg",
  active: "bg-success/15 text-success",
  paused: "bg-warning/15 text-warning",
  ended: "bg-raised text-fg-secondary",
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
          className="min-h-[60vh]"
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
  const router = useRouter();
  const searchParams = useSearchParams();

  // The server's view (status, overlaps, queue) follows every save; the draft is what the user typed.
  const server = useAutomation(wid, initial.id).data ?? initial;
  const details = useWorkspace(wid);
  const disclosure = details.data?.automation_disclosure ?? null;
  const allAccounts = useSocialAccounts(wid);
  const accounts = useMemo(() => instagramAccounts(allAccounts.data ?? []), [allAccounts.data]);

  const { draft, update, flush, discard, status, error } = useAutosave(wid, initial);
  const [activationErrors, setActivationErrors] = useState<FieldErrors>({});
  const [mediaUrl, setMediaUrl] = useState<string | null>(initial.message_media_url ?? null);
  const [confirmDelete, setConfirmDelete] = useState(false);

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
  const stateOf = (step: StepId): StepState =>
    errorSteps.has(step) ? "error" : stepComplete(step, draft, disclosure) ? "complete" : "incomplete";
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
        toast.success(
          result.display_status === "scheduled" && result.starts_at
            ? `Scheduled. It starts ${shortDateTime(result.starts_at, timeZone)}.`
            : "Active. It answers new messages from now on.",
        );
      },
      onError: (caught) => {
        const apiError = toApiError(caught);
        if (apiError.code !== "validation_error" || apiError.errors.length === 0) {
          toast.error(errorMessage(apiError));
          return;
        }
        const next = fieldErrors(apiError.errors);
        setActivationErrors(next);
        const withErrors = stepsWithErrors(next);
        const first = steps.find((step) => withErrors.has(step));
        if (first) requestAnimationFrame(() => focusStep(first, { field: false }));
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
      onError: (caught) => toast.error(errorMessage(caught)),
    });

  const onDuplicate = async () => {
    await flush();
    duplicate.mutate(server.id, {
      onSuccess: (copy) => {
        toast.success(`Duplicated. You're editing ${copy.name}.`);
        router.push(editorHref(slug, copy.id));
      },
      onError: (caught) => toast.error(errorMessage(caught)),
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
      onError: (caught) => toast.error(errorMessage(caught)),
    });
  };

  const active = server.status === "active";
  const statusBusy = activate.isPending || pause.isPending;
  const account = accounts.find((item) => item.id === draft.social_account_id);
  const nameError = errors.name;

  return (
    <div className="mx-auto w-full max-w-[1200px] p-4 md:p-6">
      <header className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-line pb-4">
        <div className="min-w-0 flex-1 basis-64">
          <nav aria-label="Breadcrumb" className="text-xs text-fg-secondary">
            <Link href={`/w/${slug}/automations` as Route} className="hover:text-fg hover:underline">
              Automations
            </Link>{" "}
            <span aria-hidden>/</span>
          </nav>
          <input
            aria-label="Automation name"
            value={draft.name}
            maxLength={80}
            onChange={(event) => change({ name: event.target.value })}
            onBlur={() => {
              if (!draft.name.trim()) change({ name: DEFAULT_NAME });
            }}
            aria-invalid={nameError ? true : undefined}
            className="-mx-1 w-full rounded-md bg-transparent px-1 text-xl font-semibold outline-none hover:bg-white/5 focus:bg-field focus-visible:ring-3 focus-visible:ring-ring/50"
          />
          {nameError ? <p className="text-xs text-danger-fg">{nameError}</p> : null}
        </div>
        <span
          data-testid="status-pill"
          className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium", STATUS_TONE[server.display_status])}
        >
          {STATUS_LABEL[server.display_status]}
        </span>
        <SaveIndicator status={status} onRetry={() => void flush()} />
        {active ? (
          <Button variant="secondary" className="h-9" onClick={onPause} disabled={statusBusy}>
            {pause.isPending ? <Loader2 className="animate-spin" aria-hidden /> : <Pause aria-hidden />} Pause
          </Button>
        ) : (
          <Button className="bg-brand-gradient h-9 text-white" onClick={() => void onActivate()} disabled={statusBusy}>
            {activate.isPending ? <Loader2 className="animate-spin" aria-hidden /> : <Play aria-hidden />} Activate
          </Button>
        )}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon-lg" className="size-10 md:size-9" aria-label="More actions">
              <EllipsisVertical aria-hidden />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-44 border-line bg-panel shadow-xl">
            <DropdownMenuItem onSelect={() => void onDuplicate()} disabled={duplicate.isPending}>
              <Copy aria-hidden /> Duplicate
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={() => setConfirmDelete(true)} className="text-danger-fg focus:text-danger-fg">
              <Trash2 aria-hidden /> Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </header>
      {status === "error" && error ? (
        <p role="alert" className="mt-3 flex items-start gap-2 text-sm text-danger-fg">
          <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
          {error.code === "validation_error" ? "Some changes weren't saved. Fix the fields marked below." : errorMessage(error)}
        </p>
      ) : null}

      <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <aside
          aria-label="Preview and results"
          className="rounded-xl border border-line bg-panel p-4 xl:sticky xl:top-6 xl:col-start-2 xl:row-start-1 xl:self-start"
        >
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
          />
        </aside>

        <div className="min-w-0 space-y-4 xl:col-start-1 xl:row-start-1 xl:max-w-[720px]">
          {server.queue.waiting > 0 ? (
            <QueueBanner queue={server.queue} order={draft.surge_order} onOrderChange={(order) => change({ surge_order: order })} />
          ) : null}
          {unplaced.length > 0 ? (
            <ul role="alert" className="space-y-1 rounded-xl border border-danger bg-danger/10 px-4 py-3 text-sm text-danger-fg">
              {unplaced.map(([field, message]) => (
                <li key={field}>{message}</li>
              ))}
            </ul>
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
                    return (
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
      </div>

      <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <AlertDialogContent className="border-line bg-panel">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {draft.name}?</AlertDialogTitle>
            <AlertDialogDescription className="text-fg-secondary">
              It stops answering at once and can&apos;t be restored. Messages it already sent stay in the inbox.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => void onDelete()} className="bg-danger-fill text-white hover:bg-danger-fill/90">
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
            <Loader2 className="size-3.5 animate-spin" aria-hidden /> Saving…
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
    <div role="status" className="flex flex-wrap items-center gap-3 rounded-xl border border-brand-line bg-brand-soft px-4 py-3 text-sm">
      <Clock className="size-4 shrink-0 text-brand-fg" aria-hidden />
      <p className="min-w-0 flex-1">
        <span className="font-medium tabular-nums">{queueBanner(queue)}</span>
        <span className="text-fg-secondary"> · {SURGE_LABEL[order]}</span>
      </p>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="secondary" size="sm">
            Change order
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56 border-line bg-panel shadow-xl">
          <DropdownMenuLabel className="text-xs text-fg-secondary">When busy</DropdownMenuLabel>
          <DropdownMenuRadioGroup value={order} onValueChange={(value) => onOrderChange(value as SurgeOrder)}>
            {(Object.keys(SURGE_LABEL) as SurgeOrder[]).map((value) => (
              <DropdownMenuRadioItem key={value} value={value}>
                {SURGE_LABEL[value]}
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

function EditorSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading automation" className="mx-auto w-full max-w-[1200px] space-y-6 p-4 md:p-6">
      <div className="space-y-2 border-b border-line pb-4">
        <Skeleton className="h-3 w-24 bg-raised" />
        <Skeleton className="h-7 w-64 bg-raised" />
      </div>
      <div className="max-w-[720px] space-y-4 pl-8">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="space-y-3 rounded-xl border border-line bg-panel p-5">
            <Skeleton className="h-3 w-20 bg-raised" />
            <Skeleton className="h-9 w-full bg-raised" />
          </div>
        ))}
      </div>
    </div>
  );
}
