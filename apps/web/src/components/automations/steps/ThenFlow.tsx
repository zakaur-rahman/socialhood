"use client";

import type { AutomationDefinition, Plan } from "@/lib/api/types";
import { errorsFor, isCommentTrigger, type FieldErrors } from "@/lib/automations/definition";
import type { StepErrors } from "@/lib/automations/flow";

import { FlowEditor } from "../flow/FlowEditor";
import type { FlowDraft } from "../flow/use-flow-draft";
import { StepCard, type StepState } from "../StepCard";
import { ReplyVariations, type Uploader } from "./ThenStep";

/**
 * GR-13 Then for an automation saved as a flow: the public reply variations for a comment (they
 * stay on the automation), then the steps. The message settings no longer apply.
 */
export function ThenFlow({
  wid,
  automationId,
  draft,
  change,
  errors,
  state,
  plan,
  disclosure,
  upload,
  flow,
  activationErrors,
  clearActivationErrors,
}: {
  wid: string;
  automationId: string;
  draft: AutomationDefinition;
  change: (patch: Partial<AutomationDefinition>) => void;
  errors: FieldErrors;
  state: StepState;
  plan: Plan;
  disclosure: string | null;
  upload?: Uploader;
  flow: FlowDraft;
  activationErrors: StepErrors;
  clearActivationErrors: (id: string) => void;
}) {
  const comment = isCommentTrigger(draft.trigger);
  return (
    <StepCard id="then" label="Then" state={state} errors={[...new Set(errorsFor(errors, "public_reply_texts"))]}>
      <div className="space-y-6">
        {comment ? (
          <ReplyVariations texts={draft.public_reply_texts ?? []} onChange={(texts) => change({ public_reply_texts: texts })} />
        ) : null}
        <FlowEditor
          wid={wid}
          automationId={automationId}
          plan={plan}
          draft={flow}
          comment={comment}
          disclosure={disclosure}
          upload={upload}
          activationErrors={activationErrors}
          clearActivationErrors={clearActivationErrors}
        />
      </div>
    </StepCard>
  );
}
