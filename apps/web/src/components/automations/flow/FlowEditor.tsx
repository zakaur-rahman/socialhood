"use client";

import { AlertCircle, ListTree, Undo2 } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { toast } from "sonner";

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
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useBillingPlans, useFlowFields, useFlowTags, useResetFlow, useSavedReplies } from "@/lib/api/queries";
import type { FlowDefinition, Plan, Platform } from "@/lib/api/types";
import { entitlementOf } from "@/lib/billing/plan";
import { stepTitle, type StepErrors } from "@/lib/automations/flow";
import { toastError } from "@/lib/toast-error";

import type { Uploader } from "../steps/ThenStep";
import { FlowProvider, useFlowEnv } from "./FlowContext";
import type { FlowDraft } from "./use-flow-draft";
import { focusFlowStep, StepList } from "./StepTree";

/** What the Free plan's cap on steps is until the owner decides (PD-5): the plan list says. */
export function useStepCap(plan: Plan): number | null {
  const plans = useBillingPlans();
  const value = entitlementOf(plans.data?.items.find((item) => item.plan === plan)?.entitlements, "flow_steps");
  return typeof value === "number" ? value : null;
}

/**
 * GR-13: the "Then" of an automation saved as a flow. Steps are a vertical list; a branch is an
 * indented group with its own steps; every step is a card with its own checks. Edits autosave
 * (use-flow-draft). The API's refusals (a save, an activation) land on the steps they name, and
 * the list at the top jumps to them.
 */
export function FlowEditor({
  wid,
  automationId,
  plan,
  draft,
  comment,
  platform,
  disclosure,
  upload,
  activationErrors,
  clearActivationErrors,
}: {
  wid: string;
  automationId: string;
  plan: Plan;
  draft: FlowDraft;
  comment: boolean;
  /** GR-29: the account's platform (Instagram when unknown). */
  platform?: Platform;
  disclosure: string | null;
  upload?: Uploader;
  /** The API's problems from the last activation, by step. */
  activationErrors: StepErrors;
  clearActivationErrors: (id: string) => void;
}) {
  const tags = useFlowTags(wid);
  const fields = useFlowFields(wid);
  const savedReplies = useSavedReplies(wid);
  const cap = useStepCap(plan);
  const [announcement, setAnnouncement] = useState("");

  const serverErrors = useMemo<StepErrors>(() => {
    const merged: StepErrors = {};
    for (const source of [draft.saveErrors, activationErrors]) {
      for (const [id, found] of Object.entries(source)) merged[id] = { ...merged[id], ...found };
    }
    return merged;
  }, [draft.saveErrors, activationErrors]);

  const clearServerErrors = clearActivationErrors;
  const tagName = useCallback((id: string) => tags.data?.find((tag) => tag.id === id)?.name, [tags.data]);
  const title = useCallback((node: Parameters<typeof stepTitle>[0]) => stepTitle(node, tagName), [tagName]);

  if (draft.phase === "loading") {
    return (
      <div role="status" aria-busy="true" aria-label="Loading steps" className="space-y-3">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }
  if (draft.phase === "error") {
    return <ErrorState size="compact" error={draft.loadError} onRetry={draft.retryLoad} />;
  }
  if (draft.phase === "opaque" && draft.stored) {
    return <OpaqueFlow wid={wid} automationId={automationId} definition={draft.stored} />;
  }

  return (
    <FlowProvider
      wid={wid}
      tree={draft.tree}
      update={draft.update}
      disclosure={disclosure}
      comment={comment}
      platform={platform}
      upload={upload}
      tags={tags.data ?? []}
      fields={fields.data ?? []}
      savedReplies={savedReplies.data?.items}
      serverErrors={serverErrors}
      clearServerErrors={clearServerErrors}
      cap={cap}
      onAnnounce={setAnnouncement}
      title={title}
    >
      <FlowBody wid={wid} automationId={automationId} draft={draft} announcement={announcement} />
    </FlowProvider>
  );
}

function FlowBody({
  wid,
  automationId,
  draft,
  announcement,
}: {
  wid: string;
  automationId: string;
  draft: FlowDraft;
  announcement: string;
}) {
  const env = useFlowEnv();
  const reset = useResetFlow(wid, automationId);
  const [confirm, setConfirm] = useState(false);
  const atCap = env.cap !== null && env.count >= env.cap;

  const onReset = () =>
    reset.mutate(undefined, {
      onSuccess: () => {
        setConfirm(false);
        toast.success("Back to one message. Its text is the one from before you added steps.");
      },
      onError: (caught) => toastError(caught),
    });

  return (
    <div className="space-y-4" data-testid="flow-editor">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-medium">
          Steps{" "}
          <span className="font-normal text-fg-secondary tabular-nums" data-testid="flow-count">
            · {env.cap !== null ? `${env.count} of ${env.cap}` : env.count}
          </span>
        </p>
        <Button variant="ghost" size="sm" onClick={() => setConfirm(true)}>
          <Undo2 aria-hidden /> Back to one message
        </Button>
      </div>
      <p id="flow-reorder-help" className="sr-only">
        Drag this handle to move the step, or press the up and down arrow keys.
      </p>
      <p role="status" aria-live="polite" className="sr-only">
        {announcement}
      </p>
      {env.comment ? (
        <p className="text-xs text-fg-secondary">
          The first message answers the comment. Instagram allows one reply to a comment until the person answers, so
          follow it with quick replies or a question before any more messages.
        </p>
      ) : null}

      {draft.capMessage ? (
        <Alert tone="warning" icon={<AlertCircle />}>
          {draft.capMessage}
        </Alert>
      ) : atCap ? (
        <Alert tone="brand">
          Your plan includes {env.cap} steps in a flow. Upgrade to add more.
        </Alert>
      ) : null}

      {draft.saveGeneral.length > 0 ? (
        <Alert tone="danger" icon={<AlertCircle />}>
          <ul className="space-y-1">
            {draft.saveGeneral.map((message) => (
              <li key={message}>{message}</li>
            ))}
          </ul>
        </Alert>
      ) : null}

      {env.attention.length > 0 ? (
        <Alert tone="danger" icon={<AlertCircle />} data-testid="flow-attention">
          <p className="mb-1 font-medium">
            {env.attention.length === 1 ? "One step needs attention" : `${env.attention.length} steps need attention`}
          </p>
          <ul className="space-y-1">
            {env.attention.map((item) => (
              <li key={item.id} className="flex flex-wrap items-baseline gap-x-2">
                <Button
                  variant="link"
                  size="xs"
                  className="h-auto px-0"
                  onClick={() => focusFlowStep(item.id, { field: true })}
                  aria-label={`Go to step ${item.number}: ${item.title}`}
                >
                  Step {item.number}
                </Button>
                <span>
                  {item.title}: {item.message}
                </span>
              </li>
            ))}
          </ul>
        </Alert>
      ) : null}

      <StepList steps={env.tree} listRef={{ parent: null, slot: "root" }} outerFollower={false} />

      <AlertDialog open={confirm} onOpenChange={setConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Go back to one message?</AlertDialogTitle>
            <AlertDialogDescription>
              The steps you built stop being used. The automation sends the single message from its message
              settings again. People already partway through a flow finish it.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep the steps</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={onReset} disabled={reset.isPending}>
              Go back to one message
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

/**
 * A stored flow whose shape the editor can't show yet (made through the API, with steps that paths
 * share without ever meeting). It still runs exactly as saved; here it is read-only, with a way to
 * start again from a single message.
 */
function OpaqueFlow({ wid, automationId, definition }: { wid: string; automationId: string; definition: FlowDefinition }) {
  const reset = useResetFlow(wid, automationId);
  return (
    <div className="space-y-3" data-testid="flow-opaque">
      <Alert tone="brand" icon={<ListTree />}>
        This flow was built outside the editor and has a shape the editor can&apos;t show yet. It runs as saved. To
        edit it here, start again from one message.
      </Alert>
      <ol className="space-y-2">
        {definition.steps.map((step, index) => (
          <li key={step.id} className="rounded-lg border border-line px-3 py-2 text-sm">
            <span className="tabular-nums text-fg-secondary">{index + 1}</span>{" "}
            <span className="font-medium">{step.type === "randomize" ? "split" : step.type.replace("_", " ")}</span>
            {"text" in step && step.text ? <span className="text-fg-secondary"> · {step.text}</span> : null}
          </li>
        ))}
      </ol>
      <Button variant="secondary" size="sm" loading={reset.isPending} onClick={() => reset.mutate(undefined, { onError: (caught) => toastError(caught) })}>
        <Undo2 aria-hidden /> Start again from one message
      </Button>
    </div>
  );
}
