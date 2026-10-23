"use client";

import type { ReactNode } from "react";

import type { FlowPreviewStep } from "@/lib/api/types";
import { cn } from "@/lib/utils";

import { NativeSelect } from "./NativeSelect";

/**
 * One walk through a flow as a chat: what the business sends, the taps and answers between, and at
 * each fork a picker for the way to follow (the Preview and the Test tab show one branch at a time).
 * The steps come from the editor's own walk (lib/automations/flow.walk) or the API's dry run
 * (``flow_path``); both have the same shape. ``onChoose(fork, exit)`` is the nth fork of this walk.
 */
export function PathView({
  steps,
  onChoose,
  imageNote,
}: {
  steps: FlowPreviewStep[];
  onChoose: (fork: number, exit: number) => void;
  /** Step ids whose message carries an image (the walk doesn't know what it looks like). */
  imageNote?: ReadonlySet<string>;
}) {
  let fork = 0;
  return (
    <ol className="space-y-3" aria-label="The flow, one way through">
      {steps.map((step) => {
        const exits = step.exits ?? [];
        const forkNumber = exits.length > 0 ? ++fork : 0;
        return (
          <li key={step.step_id} data-testid="path-step" data-kind={step.kind} className="space-y-2">
            <StepBubbles step={step} image={imageNote?.has(step.step_id) ?? false} />
            {forkNumber > 0 ? (
              <NativeSelect
                label={`Branch ${forkNumber}`}
                value={String(step.picked ?? 0)}
                onChange={(value) => onChoose(forkNumber - 1, Number(value))}
              >
                {exits.map((exit, index) => (
                  <option key={index} value={index}>
                    {exit}
                  </option>
                ))}
              </NativeSelect>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}

function StepBubbles({ step, image }: { step: FlowPreviewStep; image: boolean }) {
  if (step.kind === "send" || step.kind === "ask") {
    const quickReplies = step.quick_replies ?? [];
    const buttons = step.buttons ?? [];
    const tapped = step.picked !== null && step.picked !== undefined ? quickReplies[step.picked] : undefined;
    return (
      <div className="space-y-1.5">
        <Mine>
          {image ? <span className="block rounded-lg bg-on-brand/15 py-6 text-center text-xs">Image</span> : null}
          {step.text ? <p className="leading-relaxed break-words whitespace-pre-wrap">{step.text}</p> : null}
          {!step.text && buttons.length === 0 && !image ? <p className="opacity-80">Nothing written yet</p> : null}
          {buttons.map((button, index) => (
            <span key={index} className="block rounded-lg bg-on-brand/15 py-1.5 text-center text-xs font-medium">
              {button}
            </span>
          ))}
        </Mine>
        {quickReplies.length > 0 ? (
          <div className="flex flex-wrap justify-end gap-1.5">
            {quickReplies.map((reply, index) => (
              <span
                key={index}
                className={cn(
                  "rounded-full border px-3 py-1 text-xs font-medium",
                  index === step.picked ? "border-brand bg-brand-soft text-brand-fg" : "border-brand-line text-brand-fg",
                )}
              >
                {reply}
              </span>
            ))}
          </div>
        ) : null}
        {step.kind === "ask" ? <Theirs muted>Their answer</Theirs> : null}
        {tapped ? <Theirs>{tapped}</Theirs> : null}
        {step.kind === "send" && quickReplies.length > 0 && step.picked === quickReplies.length ? (
          <Theirs muted>They type an answer</Theirs>
        ) : null}
      </div>
    );
  }
  return <p className="text-center text-xs text-fg-secondary">{step.title}</p>;
}

function Mine({ children }: { children: ReactNode }) {
  return (
    <div className="flex justify-end">
      <div className="bg-brand-gradient max-w-[88%] space-y-2 rounded-2xl rounded-br-md px-3 py-2 text-sm text-on-brand">
        {children}
      </div>
    </div>
  );
}

function Theirs({ children, muted }: { children: ReactNode; muted?: boolean }) {
  return (
    <div className="flex justify-start">
      <p className={cn("max-w-[85%] rounded-2xl rounded-bl-md bg-field px-3 py-2 text-sm", muted && "text-fg-secondary italic")}>
        {children}
      </p>
    </div>
  );
}
