"use client";

import { useRef } from "react";

import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { AskNode } from "@/lib/automations/flow";
import { formatCount } from "@/lib/automations/format";
import { MESSAGE_LIMIT_BYTES, MESSAGE_MAX_CHARS, worstCaseBytes } from "@/lib/automations/render";
import { cn } from "@/lib/utils";

import { InsertFieldMenu } from "../../steps/ThenStep";
import { useFlowEnv } from "../FlowContext";
import { NativeSelect } from "../NativeSelect";

const EXPECT_LABEL: Record<AskNode["expect"], string> = {
  email: "An email address",
  phone: "A phone number",
  text: "Text",
};

/** Field types that can hold each kind of answer (the API's table). */
const HOLDS: Record<AskNode["expect"], string[]> = {
  text: ["text", "number", "date", "choice"],
  email: ["email"],
  phone: ["phone"],
};

const OWN_FIELD: Record<AskNode["expect"], string> = {
  text: "Choose a field",
  email: "The contact's email",
  phone: "The contact's phone",
};

/**
 * An Ask step: a question whose answer is checked and saved. An email or a phone goes to the
 * contact (or to a custom field of that type); text goes to a custom field. An answer that doesn't
 * fit gets the retry prompt, then the step's "doesn't fit" path (shown below the fields).
 */
export function AskFields({ node }: { node: AskNode }) {
  const env = useFlowEnv();
  const problems = env.problemsOf(node.id);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const textId = `flow-${node.id}-text`;
  const bytes = worstCaseBytes(node.text, env.disclosure);
  const textProblem = problems.text?.message;
  const fieldProblem = problems.field_key?.message;
  const set = (patch: Partial<AskNode>) =>
    env.patch(node.id, (current) => (current.kind === "ask" ? { ...current, ...patch } : current));
  const choices = env.fields.filter((field) => HOLDS[node.expect].includes(field.type));

  return (
    <div className="space-y-4">
      <Field id={textId}>
        <div className="flex items-center justify-between gap-2">
          <FieldLabel>Question</FieldLabel>
          <InsertFieldMenu
            target={textarea}
            text={node.text}
            onChange={(text) => set({ text })}
            label={`Insert field in step ${env.numberOf(node.id)}`}
          />
        </div>
        <Textarea
          ref={textarea}
          id={textId}
          value={node.text}
          maxLength={MESSAGE_MAX_CHARS}
          rows={2}
          onChange={(event) => set({ text: event.target.value })}
          placeholder="What's your email, so we can send it over?"
          aria-invalid={textProblem ? true : undefined}
          aria-describedby={textProblem ? `${textId}-error` : undefined}
        />
        <p className={cn("text-right text-xs tabular-nums", bytes > MESSAGE_LIMIT_BYTES ? "text-danger-fg" : "text-fg-secondary")}>
          {formatCount(bytes)} / {formatCount(MESSAGE_LIMIT_BYTES)} bytes
        </p>
        {textProblem ? (
          <p id={`${textId}-error`} className="text-xs text-danger-fg">
            {textProblem}
          </p>
        ) : null}
      </Field>

      <div className="grid gap-3 sm:grid-cols-2">
        <NativeSelect
          label="They answer with"
          value={node.expect}
          onChange={(value) => set({ expect: value as AskNode["expect"], field_key: null })}
        >
          {(Object.keys(EXPECT_LABEL) as AskNode["expect"][]).map((expect) => (
            <option key={expect} value={expect}>
              {EXPECT_LABEL[expect]}
            </option>
          ))}
        </NativeSelect>
        <div className="space-y-1.5">
          <NativeSelect
            label="Save the answer to"
            value={node.field_key ?? ""}
            onChange={(value) => set({ field_key: value || null })}
            invalid={Boolean(fieldProblem)}
            describedBy={fieldProblem ? `${textId}-field-error` : undefined}
          >
            <option value="">{OWN_FIELD[node.expect]}</option>
            {choices.map((field) => (
              <option key={field.key} value={field.key}>
                {field.label}
              </option>
            ))}
            {node.field_key && !choices.some((field) => field.key === node.field_key) ? (
              <option value={node.field_key}>{node.field_key}</option>
            ) : null}
          </NativeSelect>
          {fieldProblem ? (
            <p id={`${textId}-field-error`} className="text-xs text-danger-fg">
              {fieldProblem}
            </p>
          ) : null}
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_8rem]">
        <Field id={`${textId}-retry`}>
          <FieldLabel>If it doesn&apos;t fit, ask again with</FieldLabel>
          <Input
            id={`${textId}-retry`}
            value={node.retry_text}
            maxLength={300}
            onChange={(event) => set({ retry_text: event.target.value })}
            placeholder="That doesn't look right. Could you send it again?"
            size="lg"
          />
        </Field>
        <NativeSelect label="Tries" value={String(node.tries)} onChange={(value) => set({ tries: Number(value) })}>
          {[1, 2, 3].map((tries) => (
            <option key={tries} value={tries}>
              {tries}
            </option>
          ))}
        </NativeSelect>
      </div>
    </div>
  );
}
