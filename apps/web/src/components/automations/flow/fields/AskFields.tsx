"use client";

import { useRef } from "react";

import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type { AskNode } from "@/lib/automations/flow";
import { formatCount } from "@/lib/automations/format";
import { messageLimit, messageSize } from "@/lib/automations/limits";
import { MESSAGE_MAX_CHARS } from "@/lib/automations/render";
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

/** The default prompts the API uses when these are left blank (services/automations/capture.py). */
const RETRY_DEFAULT: Record<AskNode["expect"], string> = {
  email: "That doesn't look like an email address. Could you send it again?",
  phone: "That doesn't look like a phone number. Could you send it with the country code?",
  text: "Sorry, I didn't catch that. Could you send it again?",
};
const CONSENT_DEFAULT = "Can we message you with offers and updates here? You can say no, and you can stop any time.";
const CONFIRM_SUGGESTION = "Thanks, I've got it.";

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
  const size = messageSize(node.text, env.disclosure, env.platform);
  const { limit, unit } = messageLimit(env.platform);
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
        <p className={cn("text-right text-xs tabular-nums", size > limit ? "text-danger-fg" : "text-fg-secondary")}>
          {formatCount(size)} / {formatCount(limit)} {unit}
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
            placeholder={RETRY_DEFAULT[node.expect]}
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

      <Field id={`${textId}-confirm`}>
        <FieldLabel>Then confirm with (optional)</FieldLabel>
        <Input
          id={`${textId}-confirm`}
          value={node.confirm_text}
          maxLength={300}
          onChange={(event) => set({ confirm_text: event.target.value })}
          placeholder={CONFIRM_SUGGESTION}
          size="lg"
          aria-invalid={problems.confirm_text ? true : undefined}
        />
        {problems.confirm_text ? <p className="text-xs text-danger-fg">{problems.confirm_text.message}</p> : null}
      </Field>

      {env.platform === "facebook" ? null : (
        <div className="space-y-3 rounded-lg border border-line p-3">
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-0.5">
              <Label htmlFor={`${textId}-consent`}>Ask for marketing consent</Label>
              <p id={`${textId}-consent-hint`} className="text-xs text-fg-secondary">
                After the answer is saved, ask a Yes or No question. Their answer is recorded on the contact with the messages
                as proof. WhatsApp broadcasts need it.
              </p>
            </div>
            <Switch
              id={`${textId}-consent`}
              checked={node.consent}
              onCheckedChange={(consent) => set({ consent })}
              aria-describedby={`${textId}-consent-hint`}
              className="mt-0.5"
            />
          </div>
          {node.consent ? (
            <Field id={`${textId}-consent-text`}>
              <FieldLabel>Consent question</FieldLabel>
              <Textarea
                id={`${textId}-consent-text`}
                value={node.consent_text}
                maxLength={300}
                rows={2}
                onChange={(event) => set({ consent_text: event.target.value })}
                placeholder={CONSENT_DEFAULT}
                aria-invalid={problems.consent_text ? true : undefined}
              />
              {problems.consent_text ? <p className="text-xs text-danger-fg">{problems.consent_text.message}</p> : null}
            </Field>
          ) : null}
        </div>
      )}
    </div>
  );
}
