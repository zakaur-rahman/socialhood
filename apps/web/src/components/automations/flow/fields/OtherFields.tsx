"use client";

import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useAssignment } from "@/lib/api/queries";
import type { FlowAction } from "@/lib/api/types";
import { MAX_DELAY_SECONDS, type ActionNode, type AiNode, type DelayNode } from "@/lib/automations/flow";
import { AI_INSTRUCTIONS_MAX } from "@/lib/automations/render";
import { useCurrentWorkspace } from "@/lib/workspace";

import { useFlowEnv } from "../FlowContext";
import { NativeSelect } from "../NativeSelect";

type ActionKind = FlowAction["kind"];

const ACTION_LABEL: Record<ActionKind, string> = {
  add_tag: "Add a tag",
  remove_tag: "Remove a tag",
  set_field: "Set a field",
  notify_team: "Notify the team",
  hand_off: "Hand off to a person",
  assign: "Assign the conversation",
};

function actionFor(kind: ActionKind, previous: FlowAction, tagId: string, fieldKey: string): FlowAction {
  switch (kind) {
    case "add_tag":
    case "remove_tag":
      return { kind, tag_id: "tag_id" in previous ? previous.tag_id : tagId };
    case "set_field":
      return previous.kind === "set_field" ? previous : { kind, key: fieldKey, value: "" };
    case "notify_team":
      return { kind, note: previous.kind === "notify_team" ? previous.note : "" };
    case "hand_off":
      return { kind };
    case "assign":
      return previous.kind === "assign" ? previous : { kind, mode: "round_robin" };
  }
}

/** An Action step: tag the contact, set a field, tell the team, or hand the conversation to a person. */
export function ActionFields({ node }: { node: ActionNode }) {
  const env = useFlowEnv();
  const problems = env.problemsOf(node.id);
  const action = node.action;
  const set = (next: FlowAction) =>
    env.patch(node.id, (current) => (current.kind === "action" ? { ...current, action: next } : current));
  const where = problems.action?.message;
  const valueProblem = problems["action.value"]?.message;
  const id = `flow-${node.id}`;

  return (
    <div className="space-y-3">
      <NativeSelect
        label="Do this"
        value={action.kind}
        onChange={(value) => set(actionFor(value as ActionKind, action, env.tags[0]?.id ?? "", env.fields[0]?.key ?? ""))}
      >
        {(Object.keys(ACTION_LABEL) as ActionKind[]).map((kind) => (
          <option key={kind} value={kind}>
            {ACTION_LABEL[kind]}
          </option>
        ))}
      </NativeSelect>

      {action.kind === "add_tag" || action.kind === "remove_tag" ? (
        <NativeSelect
          label="Tag"
          value={action.tag_id}
          onChange={(tag_id) => set({ ...action, tag_id })}
          invalid={Boolean(where)}
          describedBy={where ? `${id}-error` : undefined}
        >
          <option value="">Choose a tag</option>
          {env.tags.map((tag) => (
            <option key={tag.id} value={tag.id}>
              {tag.name}
            </option>
          ))}
        </NativeSelect>
      ) : null}

      {action.kind === "set_field" ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <NativeSelect
            label="Field"
            value={action.key}
            onChange={(key) => set({ ...action, key })}
            invalid={Boolean(where)}
            describedBy={where ? `${id}-error` : undefined}
          >
            <option value="">Choose a field</option>
            {env.fields.map((field) => (
              <option key={field.key} value={field.key}>
                {field.label}
              </option>
            ))}
          </NativeSelect>
          <Field id={`${id}-value`}>
            <FieldLabel>Value</FieldLabel>
            <Input
              id={`${id}-value`}
              value={action.value}
              maxLength={200}
              onChange={(event) => set({ ...action, value: event.target.value })}
              aria-invalid={valueProblem ? true : undefined}
              size="lg"
            />
            {valueProblem ? <p className="text-xs text-danger-fg">{valueProblem}</p> : null}
          </Field>
        </div>
      ) : null}

      {action.kind === "notify_team" ? (
        <Field id={`${id}-note`}>
          <FieldLabel>Note for the team</FieldLabel>
          <Input
            id={`${id}-note`}
            value={action.note ?? ""}
            maxLength={200}
            placeholder="Optional"
            onChange={(event) => set({ ...action, note: event.target.value })}
            size="lg"
          />
        </Field>
      ) : null}

      {action.kind === "hand_off" ? (
        <p className="text-xs text-fg-secondary">
          The conversation moves to Needs you, and the AI stops replying in it until you resume it.
        </p>
      ) : null}

      {action.kind === "assign" ? <AssignFields action={action} set={set} error={problems["action.user_id"]?.message} id={id} /> : null}

      {where ? (
        <p id={`${id}-error`} className="text-xs text-danger-fg">
          {where}
        </p>
      ) : null}
    </div>
  );
}

type AssignAction = Extract<FlowAction, { kind: "assign" }>;

const ASSIGN_MODE_HELP: Record<AssignAction["mode"], string> = {
  member: "Always the same person. They are told, as for any assignment.",
  round_robin: "The next available member in turn, whether or not round-robin is on for new conversations.",
  nobody: "Takes the assignee away.",
};

/** The assign action (GR-20): a chosen member, the next available member in turn, or nobody. */
function AssignFields({
  action,
  set,
  error,
  id,
}: {
  action: AssignAction;
  set: (next: FlowAction) => void;
  error?: string;
  id: string;
}) {
  const { id: wid } = useCurrentWorkspace();
  const overview = useAssignment(wid);
  const members = overview.data?.members ?? [];
  return (
    <div className="space-y-3">
      <NativeSelect
        label="Assign to"
        value={action.mode}
        onChange={(value) => {
          const mode = value as AssignAction["mode"];
          set(mode === "member" ? { kind: "assign", mode, user_id: action.user_id ?? null } : { kind: "assign", mode });
        }}
      >
        <option value="round_robin">The next available member</option>
        <option value="member">A chosen member</option>
        <option value="nobody">Nobody</option>
      </NativeSelect>
      {action.mode === "member" ? (
        <NativeSelect
          label="Member"
          value={action.user_id ?? ""}
          onChange={(user_id) => set({ ...action, user_id: user_id || null })}
          invalid={Boolean(error)}
          describedBy={error ? `${id}-error` : undefined}
        >
          <option value="">Choose a member</option>
          {members.map((member) => (
            <option key={member.user_id} value={member.user_id}>
              {member.name ?? "A team member"}
            </option>
          ))}
        </NativeSelect>
      ) : null}
      <p className="text-xs text-fg-secondary">{ASSIGN_MODE_HELP[action.mode]}</p>
    </div>
  );
}

const UNITS = { minutes: 60, hours: 3600 } as const;
type Unit = keyof typeof UNITS;

/** A Delay step: wait up to 23 hours, so what follows can still go inside Instagram's 24-hour window. */
export function DelayFields({ node }: { node: DelayNode }) {
  const env = useFlowEnv();
  const unit: Unit = node.seconds % 3600 === 0 ? "hours" : "minutes";
  const amount = node.seconds / UNITS[unit];
  const id = `flow-${node.id}-delay`;
  const set = (seconds: number) =>
    env.patch(node.id, (current) =>
      current.kind === "delay" ? { ...current, seconds: Math.max(1, Math.min(MAX_DELAY_SECONDS, Math.round(seconds))) } : current,
    );
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-3 sm:max-w-sm">
        <Field id={id}>
          <FieldLabel>Wait for</FieldLabel>
          <Input
            id={id}
            type="number"
            inputMode="numeric"
            min={1}
            value={Number.isFinite(amount) ? amount : 1}
            onChange={(event) => set((Number(event.target.value) || 1) * UNITS[unit])}
            size="lg"
          />
        </Field>
        <NativeSelect
          label="Unit"
          value={unit}
          onChange={(next) => set(amount * UNITS[next as Unit])}
        >
          <option value="minutes">minutes</option>
          <option value="hours">hours</option>
        </NativeSelect>
      </div>
      <p className="text-xs text-fg-secondary">
        Up to 23 hours. Instagram lets you message someone for 24 hours after they last wrote.
      </p>
    </div>
  );
}

/** An AI reply step: instructions for the AI, which answers from your knowledge and ends the flow. */
export function AiFields({ node }: { node: AiNode }) {
  const env = useFlowEnv();
  const problem = env.problemsOf(node.id).instructions?.message;
  const id = `flow-${node.id}-ai`;
  return (
    <Field id={id}>
      <FieldLabel>Instructions</FieldLabel>
      <Textarea
        id={id}
        value={node.instructions}
        maxLength={AI_INSTRUCTIONS_MAX}
        rows={4}
        onChange={(event) =>
          env.patch(node.id, (current) => (current.kind === "ai" ? { ...current, instructions: event.target.value } : current))
        }
        aria-invalid={problem ? true : undefined}
        placeholder="Answer price questions from the catalogue. Keep it to two sentences."
      />
      {problem ? <p className="text-xs text-danger-fg">{problem}</p> : null}
      <p className="text-xs text-fg-secondary">
        The AI answers from your knowledge. When the answer isn&apos;t there, it moves the conversation to Needs you.
      </p>
    </Field>
  );
}
