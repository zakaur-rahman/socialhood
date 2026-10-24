"use client";

import {
  ArrowDown,
  ArrowUp,
  ChevronDown,
  ChevronRight,
  GripVertical,
  Plus,
  Trash2,
  X,
} from "lucide-react";
import { useRef, useState, type KeyboardEvent, type PointerEvent, type ReactNode } from "react";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CardInset } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  describeCondition,
  dropIndex,
  endsFlow,
  MAX_PATHS,
  MAX_REPLIES,
  MAX_RULES,
  stepTitle,
  type AskNode,
  type BranchNode,
  type EditorStep,
  type ListRef,
  type SendNode,
  type SplitNode,
} from "@/lib/automations/flow";
import { cn } from "@/lib/utils";

import { useFlowEnv } from "./FlowContext";
import { KindMenu } from "./KindMenu";
import { ConditionEditor } from "./fields/ConditionEditor";
import { AskFields } from "./fields/AskFields";
import { ActionFields, AiFields, DelayFields } from "./fields/OtherFields";
import { SendFields } from "./fields/SendFields";
import { NativeSelect } from "./NativeSelect";

/** The id of a step's card in the page, for "go to step". */
export const stepDomId = (id: string) => `flow-step-${id}`;

/** Take the user to a step: scroll to its card and focus it (its first field when asked). */
export function focusFlowStep(id: string, { field = false }: { field?: boolean } = {}): void {
  const card = document.getElementById(stepDomId(id));
  if (!card) return;
  const target = field
    ? card.querySelector<HTMLElement>("textarea:not([disabled]), input:not([disabled]):not([type=file]), select:not([disabled])")
    : null;
  (target ?? card).focus();
  card.scrollIntoView?.({ block: "center", behavior: "smooth" });
}

// ---------------------------------------------------------------- the add menu

export function AddStepMenu({ listRef, label, ariaLabel }: { listRef: ListRef; label?: string; ariaLabel?: string }) {
  const env = useFlowEnv();
  const full = env.cap !== null && env.count >= env.cap;
  return (
    <KindMenu
      label={label}
      ariaLabel={ariaLabel}
      disabledReason={full ? `Your plan includes ${env.cap} steps in a flow.` : null}
      onPick={(kind) => env.add(listRef, kind)}
    />
  );
}

// ---------------------------------------------------------------- a list of steps

/**
 * A vertical list of step cards with drag to reorder (a handle on each card: pointer drag, or the
 * arrow keys on the focused handle) and an "Add step" menu at the end. ``outerFollower`` says
 * whether something comes after the list's owner, which is where an arm that runs out carries on.
 */
export function StepList({
  steps,
  listRef,
  outerFollower,
  addAria,
}: {
  steps: EditorStep[];
  listRef: ListRef;
  outerFollower: boolean;
  /** The accessible name of the list's Add step button, when the page has several. */
  addAria?: string;
}) {
  const env = useFlowEnv();
  const [drag, setDrag] = useState<{ id: string; index: number; over: number } | null>(null);
  const items = useRef(new Map<string, HTMLElement>());

  const overFor = (clientY: number, id: string) => {
    const middles = steps
      .filter((node) => node.id !== id)
      .map((node) => {
        const rect = items.current.get(node.id)?.getBoundingClientRect();
        return rect ? rect.top + rect.height / 2 : 0;
      });
    return dropIndex(middles, clientY);
  };

  const handleFor = (node: EditorStep, index: number): HandleProps => ({
    onPointerDown: (event: PointerEvent<HTMLButtonElement>) => {
      if (event.button !== 0 || steps.length < 2) return;
      event.currentTarget.setPointerCapture?.(event.pointerId);
      setDrag({ id: node.id, index, over: index });
    },
    onPointerMove: (event: PointerEvent<HTMLButtonElement>) => {
      if (!drag || drag.id !== node.id) return;
      const over = overFor(event.clientY, node.id);
      if (over !== drag.over) setDrag({ ...drag, over });
    },
    onPointerUp: () => {
      if (drag && drag.id === node.id && drag.over !== drag.index) {
        env.reorder(listRef, drag.index, drag.over);
        env.announce(`Moved step ${env.numberOf(node.id)} to position ${drag.over + 1} of ${steps.length}`);
      }
      setDrag(null);
    },
    onPointerCancel: () => setDrag(null),
    onKeyDown: (event: KeyboardEvent<HTMLButtonElement>) => {
      if (event.key === "ArrowUp" || event.key === "ArrowDown") {
        event.preventDefault();
        env.moveBy(node.id, event.key === "ArrowUp" ? -1 : 1);
      }
    },
  });

  const others = steps.filter((node) => node.id !== drag?.id);
  const marker = (key: string) => <li key={key} aria-hidden data-testid="drop-marker" className="h-0.5 rounded-full bg-brand" />;

  const rendered: ReactNode[] = [];
  const entries = drag ? [...steps] : steps;
  let othersSeen = 0;
  entries.forEach((node, index) => {
    if (drag && node.id !== drag.id) {
      if (othersSeen === drag.over) rendered.push(marker(`marker-${othersSeen}`));
      othersSeen += 1;
    }
    rendered.push(
      <li
        key={node.id}
        ref={(element) => {
          if (element) items.current.set(node.id, element);
          else items.current.delete(node.id);
        }}
      >
        <FlowStepCard
          node={node}
          listRef={listRef}
          index={index}
          length={steps.length}
          follower={index < steps.length - 1 || outerFollower}
          handle={handleFor(node, index)}
          dragging={drag?.id === node.id}
        />
      </li>,
    );
  });
  if (drag && drag.over >= others.length) rendered.push(marker("marker-end"));

  const last = steps[steps.length - 1];
  return (
    <div className="space-y-3">
      {steps.length > 0 ? <ol className="space-y-3">{rendered}</ol> : null}
      {steps.length === 0 ? (
        <p className="text-sm text-fg-secondary">
          {outerFollower ? "Nothing here. It carries on with the step below." : "Nothing here. The flow ends."}
        </p>
      ) : null}
      {endsFlow(last) ? (
        <p className="text-xs text-fg-secondary">The flow stops at {last?.kind === "ai" ? "the AI reply" : "End"}. Remove it to add more.</p>
      ) : (
        <AddStepMenu listRef={listRef} ariaLabel={addAria} />
      )}
    </div>
  );
}

type HandleProps = {
  onPointerDown: (event: PointerEvent<HTMLButtonElement>) => void;
  onPointerMove: (event: PointerEvent<HTMLButtonElement>) => void;
  onPointerUp: () => void;
  onPointerCancel: () => void;
  onKeyDown: (event: KeyboardEvent<HTMLButtonElement>) => void;
};

// ---------------------------------------------------------------- a step card

const STATE_BADGE = {
  complete: null,
  incomplete: { tone: "neutral", label: "Not finished" },
  error: { tone: "danger", label: "Needs attention" },
} as const;

/** The fields the card shows itself; a problem on any other field is listed at the top of the card. */
const SHOWN: Record<EditorStep["kind"], RegExp> = {
  send: /^(text|saved_reply_id|image_asset_id|buttons\..*|quick_replies(\..*)?)$/,
  ask: /^(text|field_key|retry_text|consent_text|confirm_text)$/,
  branch: /^rules\.\d+\.when$/,
  action: /^action(\.value)?$/,
  delay: /^$/,
  split: /^$/,
  ai: /^instructions$/,
  end: /^$/,
};

function FlowStepCard({
  node,
  listRef,
  index,
  length,
  follower,
  handle,
  dragging,
}: {
  node: EditorStep;
  listRef: ListRef;
  index: number;
  length: number;
  follower: boolean;
  handle: HandleProps;
  dragging: boolean;
}) {
  const env = useFlowEnv();
  const number = env.numberOf(node.id);
  const state = env.stateOf(node.id);
  const problems = env.problemsOf(node.id);
  const collapsed = env.collapsed.has(node.id);
  const headId = `${stepDomId(node.id)}-title`;
  const tagName = (id: string) => env.tags.find((tag) => tag.id === id)?.name;
  const title = stepTitle(node, tagName);
  const badge = STATE_BADGE[state];
  const rootAlone = listRef.parent === null && length === 1;
  const leftover = Object.entries(problems).filter(([field]) => !SHOWN[node.kind].test(field));

  return (
    <CardInset asChild padding="compact">
      <section
        id={stepDomId(node.id)}
        data-flow-step={node.id}
        data-kind={node.kind}
        data-state={state}
        aria-labelledby={headId}
        tabIndex={-1}
        ref={(element) => {
          if (element && env.claimFocus(node.id)) {
            queueMicrotask(() => focusFlowStep(node.id, { field: true }));
          }
        }}
        className={cn(
          "scroll-mt-24 bg-canvas/40 sm:[--card-padding:--spacing(4)]",
          state === "error" && "border-danger",
          dragging && "opacity-60 ring-2 ring-ring",
        )}
      >
        <div className="flex flex-wrap items-center gap-x-1 gap-y-1">
          <button
            type="button"
            {...handle}
            disabled={length < 2}
            aria-label={`Reorder step ${number}`}
            aria-describedby={length < 2 ? undefined : "flow-reorder-help"}
            className="inline-flex size-8 shrink-0 cursor-grab touch-none items-center justify-center rounded-md text-fg-secondary hover:bg-hover active:cursor-grabbing disabled:cursor-default disabled:opacity-30 pointer-coarse:size-10"
          >
            <GripVertical className="size-4" aria-hidden />
          </button>
          <h3 id={headId} className="flex min-w-24 flex-1 items-center gap-2 text-sm font-semibold">
            <span className="tabular-nums text-fg-secondary">{number}</span>
            <span className="truncate">{title}</span>
            {badge ? (
              <Badge tone={badge.tone} size="sm">
                {badge.label}
              </Badge>
            ) : null}
          </h3>
          <div className="ml-auto flex items-center">
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={collapsed ? `Expand step ${number}` : `Collapse step ${number}`}
              aria-expanded={!collapsed}
              onClick={() => env.toggleCollapsed(node.id)}
            >
              {collapsed ? <ChevronRight aria-hidden /> : <ChevronDown aria-hidden />}
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={`Move step ${number} up`}
              disabled={index === 0}
              onClick={() => env.moveBy(node.id, -1)}
            >
              <ArrowUp aria-hidden />
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={`Move step ${number} down`}
              disabled={index === length - 1}
              onClick={() => env.moveBy(node.id, 1)}
            >
              <ArrowDown aria-hidden />
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={`Delete step ${number}`}
              disabled={rootAlone}
              title={rootAlone ? "A flow needs at least one step" : undefined}
              onClick={() => env.remove(node.id)}
            >
              <Trash2 aria-hidden />
            </Button>
          </div>
        </div>

        {collapsed ? (
          <p className="mt-2 truncate pl-1 text-xs text-fg-secondary">{summary(node)}</p>
        ) : (
          <div className="mt-3 space-y-4">
            {leftover.length > 0 ? (
              <Alert tone="danger">
                <ul className="space-y-1">
                  {leftover.map(([field, problem]) => (
                    <li key={field}>{problem.message}</li>
                  ))}
                </ul>
              </Alert>
            ) : null}
            <Body node={node} />
            <Arms node={node} follower={follower} />
          </div>
        )}
      </section>
    </CardInset>
  );
}

function summary(node: EditorStep): string {
  if (node.kind === "send" && node.saved) return "A saved reply";
  if (node.kind === "send" || node.kind === "ask") return node.text.trim() || "Nothing written yet";
  if (node.kind === "ai") return node.instructions.trim() || "No instructions yet";
  if (node.kind === "branch") return node.rules.map((rule) => describeCondition(rule.when)).join(", ");
  return "";
}

function Body({ node }: { node: EditorStep }) {
  switch (node.kind) {
    case "send":
      return <SendFields node={node} />;
    case "ask":
      return <AskFields node={node} />;
    case "action":
      return <ActionFields node={node} />;
    case "delay":
      return <DelayFields node={node} />;
    case "ai":
      return <AiFields node={node} />;
    case "end":
      return <p className="text-sm text-fg-secondary">The flow stops here.</p>;
    case "branch":
      return <p className="text-xs text-fg-secondary">The first rule that holds picks the way. If none does, Otherwise.</p>;
    case "split":
      return (
        <p className="text-xs text-fg-secondary">
          Each person goes down one path, picked at random by its weight. Use it to compare two messages.
        </p>
      );
  }
}

// ---------------------------------------------------------------- arms: the lists inside a step

function ArmSection({
  parent,
  slot,
  label,
  header,
  steps,
  follower,
}: {
  parent: string;
  slot: string;
  label: string;
  header?: ReactNode;
  steps: EditorStep[];
  follower: boolean;
}) {
  return (
    <div role="group" aria-label={label} className="space-y-3 border-l-2 border-line-strong pl-2 sm:pl-4">
      {header ?? <p className="text-sm font-medium">{label}</p>}
      <StepList steps={steps} listRef={{ parent, slot }} outerFollower={follower} addAria={`Add step to ${label}`} />
    </div>
  );
}

function Arms({ node, follower }: { node: EditorStep; follower: boolean }) {
  switch (node.kind) {
    case "send":
      return <SendArms node={node} follower={follower} />;
    case "ask":
      return <AskArm node={node} follower={follower} />;
    case "branch":
      return <BranchArms node={node} follower={follower} />;
    case "split":
      return <SplitArms node={node} follower={follower} />;
    default:
      return null;
  }
}

function SendArms({ node, follower }: { node: SendNode; follower: boolean }) {
  if (node.saved) return null; // a saved reply goes alone: no quick replies
  return <SendReplies node={node} follower={follower} />;
}

function SendReplies({ node, follower }: { node: SendNode; follower: boolean }) {
  const env = useFlowEnv();
  const problems = env.problemsOf(node.id);
  const set = (change: (current: SendNode) => SendNode) =>
    env.patch(node.id, (current) => (current.kind === "send" ? change(current) : current));
  const canAdd = node.buttons.length === 0 && node.replies.length < MAX_REPLIES;

  const removeReply = (index: number) =>
    set((current) => {
      const typed = current.typed;
      return {
        ...current,
        replies: current.replies.filter((_, i) => i !== index),
        typed:
          typed.mode === "same"
            ? typed.index === index
              ? { mode: "none" }
              : { mode: "same", index: typed.index > index ? typed.index - 1 : typed.index }
            : typed,
      };
    });

  return (
    <div className="space-y-3">
      {node.replies.length > 0 ? (
        <div className="space-y-3">
          <p className="text-sm font-medium">
            Quick replies <span className="font-normal text-fg-secondary tabular-nums">· {node.replies.length} of {MAX_REPLIES}</span>
          </p>
          {node.replies.map((reply, index) => {
            const problem = problems[`quick_replies.${index}.title`]?.message;
            const id = `${stepDomId(node.id)}-reply-${index}`;
            return (
              <ArmSection
                key={index}
                parent={node.id}
                slot={`reply:${index}`}
                label={`Quick reply ${index + 1} of step ${env.numberOf(node.id)}`}
                steps={reply.steps}
                follower={follower}
                header={
                  <div className="space-y-1">
                    <div className="flex items-end gap-2">
                      <div className="min-w-0 flex-1 space-y-1.5">
                        <Label htmlFor={id}>Quick reply {index + 1}</Label>
                        <Input
                          id={id}
                          value={reply.title}
                          maxLength={20}
                          placeholder="Catalogue"
                          aria-invalid={problem ? true : undefined}
                          onChange={(event) =>
                            set((current) => ({
                              ...current,
                              replies: current.replies.map((r, i) => (i === index ? { ...r, title: event.target.value } : r)),
                            }))
                          }
                          size="lg"
                        />
                      </div>
                      <Button variant="ghost" size="icon-lg" aria-label={`Remove quick reply ${index + 1}`} onClick={() => removeReply(index)}>
                        <X aria-hidden />
                      </Button>
                    </div>
                    {problem ? <p className="text-xs text-danger-fg">{problem}</p> : <p className="text-xs text-fg-secondary">Then, for people who tap it:</p>}
                  </div>
                }
              />
            );
          })}
        </div>
      ) : null}

      {problems.quick_replies ? <p className="text-xs text-danger-fg">{problems.quick_replies.message}</p> : null}

      <Button
        variant="ghost"
        size="sm"
        disabled={!canAdd}
        title={node.buttons.length > 0 ? "A message has link buttons or quick replies, not both" : undefined}
        onClick={() =>
          set((current) => ({ ...current, replies: [...current.replies, { title: "", steps: [] }] }))
        }
      >
        <Plus aria-hidden /> Add a quick reply
      </Button>

      {node.replies.length > 0 ? (
        <div className="space-y-3">
          <NativeSelect
            label="If they type an answer instead"
            value={node.typed.mode === "same" ? `same:${node.typed.index}` : node.typed.mode}
            onChange={(value) =>
              set((current) => ({
                ...current,
                typed: value === "none" ? { mode: "none" } : value === "own" ? { mode: "own", steps: [] } : { mode: "same", index: Number(value.split(":")[1]) },
              }))
            }
          >
            <option value="none">Do nothing</option>
            {node.replies.map((reply, index) => (
              <option key={index} value={`same:${index}`}>
                Same as {reply.title.trim() ? `"${reply.title.trim()}"` : `quick reply ${index + 1}`}
              </option>
            ))}
            <option value="own">Their own steps</option>
          </NativeSelect>
          <p className="text-xs text-fg-secondary">Quick replies don&apos;t show on desktop, so people there type their answer.</p>
          {node.typed.mode === "own" ? (
            <ArmSection
              parent={node.id}
              slot="typed"
              label={`Typed answer of step ${env.numberOf(node.id)}`}
              steps={node.typed.steps}
              follower={follower}
              header={<p className="text-sm font-medium">If they type an answer</p>}
            />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function AskArm({ node, follower }: { node: AskNode; follower: boolean }) {
  const env = useFlowEnv();
  const skipping = node.skip !== null;
  return (
    <div className="space-y-3">
      <NativeSelect
        label="If the answer never fits"
        value={skipping ? "continue" : "end"}
        onChange={(value) =>
          env.patch(node.id, (current) => (current.kind === "ask" ? { ...current, skip: value === "end" ? null : [] } : current))
        }
      >
        <option value="continue">Carry on</option>
        <option value="end" disabled={Boolean(node.skip && node.skip.length > 0)}>
          End the flow
        </option>
      </NativeSelect>
      {node.skip ? (
        <ArmSection
          parent={node.id}
          slot="skip"
          label={`If the answer of step ${env.numberOf(node.id)} doesn't fit`}
          steps={node.skip}
          follower={follower}
          header={<p className="text-sm font-medium">If the answer doesn&apos;t fit</p>}
        />
      ) : null}
    </div>
  );
}

function BranchArms({ node, follower }: { node: BranchNode; follower: boolean }) {
  const env = useFlowEnv();
  const problems = env.problemsOf(node.id);
  const set = (change: (current: BranchNode) => BranchNode) =>
    env.patch(node.id, (current) => (current.kind === "branch" ? change(current) : current));
  return (
    <div className="space-y-3">
      {node.rules.map((rule, index) => (
        <ArmSection
          key={index}
          parent={node.id}
          slot={`rule:${index}`}
          label={`Rule ${index + 1} of step ${env.numberOf(node.id)}`}
          steps={rule.steps}
          follower={follower}
          header={
            <div className="flex items-start gap-2">
              <div className="min-w-0 flex-1 space-y-1">
                <p className="text-sm font-medium">If</p>
                <ConditionEditor
                  when={rule.when}
                  tags={env.tags}
                  fields={env.fields}
                  label={`Rule ${index + 1} of step ${env.numberOf(node.id)}`}
                  platform={env.platform}
                  problem={problems[`rules.${index}.when`]?.message}
                  onChange={(when) =>
                    set((current) => ({ ...current, rules: current.rules.map((r, i) => (i === index ? { ...r, when } : r)) }))
                  }
                />
              </div>
              <Button
                variant="ghost"
                size="icon-lg"
                className="mt-6"
                aria-label={`Remove rule ${index + 1}`}
                disabled={node.rules.length === 1}
                onClick={() => set((current) => ({ ...current, rules: current.rules.filter((_, i) => i !== index) }))}
              >
                <X aria-hidden />
              </Button>
            </div>
          }
        />
      ))}
      <Button
        variant="ghost"
        size="sm"
        disabled={node.rules.length >= MAX_RULES}
        onClick={() =>
          set((current) => ({
            ...current,
            rules: [...current.rules, { when: { kind: "contact", has: "email", known: true }, steps: [] }],
          }))
        }
      >
        <Plus aria-hidden /> Add a rule
      </Button>
      <ArmSection
        parent={node.id}
        slot="otherwise"
        label={`Otherwise of step ${env.numberOf(node.id)}`}
        steps={node.otherwise}
        follower={follower}
        header={<p className="text-sm font-medium">Otherwise</p>}
      />
    </div>
  );
}

function SplitArms({ node, follower }: { node: SplitNode; follower: boolean }) {
  const env = useFlowEnv();
  const total = node.paths.reduce((sum, path) => sum + path.weight, 0);
  const set = (change: (current: SplitNode) => SplitNode) =>
    env.patch(node.id, (current) => (current.kind === "split" ? change(current) : current));
  return (
    <div className="space-y-3">
      {node.paths.map((path, index) => {
        const name = String.fromCharCode(65 + index);
        const id = `${stepDomId(node.id)}-weight-${index}`;
        return (
          <ArmSection
            key={index}
            parent={node.id}
            slot={`path:${index}`}
            label={`Path ${name} of step ${env.numberOf(node.id)}`}
            steps={path.steps}
            follower={follower}
            header={
              <div className="flex items-end gap-2">
                <div className="min-w-0 flex-1 space-y-1.5">
                  <Label htmlFor={id}>
                    Path {name} weight{" "}
                    <span className="font-normal text-fg-secondary tabular-nums">· {Math.round((path.weight / total) * 100)}%</span>
                  </Label>
                  <Input
                    id={id}
                    type="number"
                    inputMode="numeric"
                    min={1}
                    max={100}
                    value={path.weight}
                    onChange={(event) =>
                      set((current) => ({
                        ...current,
                        paths: current.paths.map((p, i) =>
                          i === index ? { ...p, weight: Math.max(1, Math.min(100, Number(event.target.value) || 1)) } : p,
                        ),
                      }))
                    }
                    size="lg"
                    className="sm:max-w-32"
                  />
                </div>
                <Button
                  variant="ghost"
                  size="icon-lg"
                  aria-label={`Remove path ${name}`}
                  disabled={node.paths.length <= 2}
                  onClick={() => set((current) => ({ ...current, paths: current.paths.filter((_, i) => i !== index) }))}
                >
                  <X aria-hidden />
                </Button>
              </div>
            }
          />
        );
      })}
      <Button
        variant="ghost"
        size="sm"
        disabled={node.paths.length >= MAX_PATHS}
        onClick={() => set((current) => ({ ...current, paths: [...current.paths, { weight: 1, steps: [] }] }))}
      >
        <Plus aria-hidden /> Add a path
      </Button>
    </div>
  );
}
