"use client";

import { useId } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { FlowCondition, FlowFieldDefinition, FlowTag, LeadStage } from "@/lib/api/types";
import { LEAD_STAGES, STAGE_LABEL } from "@/lib/leads/stages";

import { NativeSelect } from "../NativeSelect";

/** The ways a branch can ask about a contact, as one list (the API's seven conditions, with yes/no). */
type Choice =
  | "tag"
  | "no_tag"
  | "field"
  | "email_known"
  | "email_unknown"
  | "phone_known"
  | "phone_unknown"
  | "follows"
  | "not_follows"
  | "instagram"
  | "whatsapp"
  | "lead_score"
  | "lead_stage";

const LABEL: Record<Choice, string> = {
  tag: "Has a tag",
  no_tag: "Doesn't have a tag",
  field: "A field",
  email_known: "We have their email",
  email_unknown: "We don't have their email",
  phone_known: "We have their phone",
  phone_unknown: "We don't have their phone",
  follows: "They follow you",
  not_follows: "They don't follow you",
  instagram: "They're on Instagram",
  whatsapp: "They're on WhatsApp",
  lead_score: "Lead score is at least",
  lead_stage: "Lead stage is",
};

const ORDER = Object.keys(LABEL) as Choice[];

export function choiceOf(when: FlowCondition): Choice {
  switch (when.kind) {
    case "tag":
      return when.has ? "tag" : "no_tag";
    case "field":
      return "field";
    case "contact":
      if (when.has === "email") return when.known ? "email_known" : "email_unknown";
      return when.known ? "phone_known" : "phone_unknown";
    case "follows_business":
      return when.follows ? "follows" : "not_follows";
    case "platform":
      return when.platform;
    case "lead_score":
      return "lead_score";
    case "lead_stage":
      return "lead_stage";
  }
}

/** A new condition of a kind, keeping what the old one chose where it still applies. */
export function conditionFor(choice: Choice, previous: FlowCondition, tags: FlowTag[], fields: FlowFieldDefinition[]): FlowCondition {
  switch (choice) {
    case "tag":
    case "no_tag":
      return {
        kind: "tag",
        tag_id: previous.kind === "tag" ? previous.tag_id : (tags[0]?.id ?? ""),
        has: choice === "tag",
      };
    case "field":
      return previous.kind === "field" ? previous : { kind: "field", key: fields[0]?.key ?? "", op: "set", value: null };
    case "email_known":
    case "email_unknown":
      return { kind: "contact", has: "email", known: choice === "email_known" };
    case "phone_known":
    case "phone_unknown":
      return { kind: "contact", has: "phone", known: choice === "phone_known" };
    case "follows":
    case "not_follows":
      return { kind: "follows_business", follows: choice === "follows" };
    case "instagram":
    case "whatsapp":
      return { kind: "platform", platform: choice };
    case "lead_score":
      return previous.kind === "lead_score" ? previous : { kind: "lead_score", at_least: 50 };
    case "lead_stage":
      return previous.kind === "lead_stage" ? previous : { kind: "lead_stage", stages: ["qualified"] };
  }
}

/**
 * One rule of a branch: what to check, and for a tag, a field or a score, the thing to check
 * it against. ``label`` names the rule for screen readers ("Rule 1 of step 3").
 */
export function ConditionEditor({
  when,
  onChange,
  tags,
  fields,
  label,
  problem,
}: {
  when: FlowCondition;
  onChange: (when: FlowCondition) => void;
  tags: FlowTag[];
  fields: FlowFieldDefinition[];
  label: string;
  problem?: string;
}) {
  const id = useId();
  const choice = choiceOf(when);
  return (
    <div className="space-y-2">
      <NativeSelect
        label={`${label}: check`}
        hideLabel
        value={choice}
        onChange={(value) => onChange(conditionFor(value as Choice, when, tags, fields))}
        invalid={Boolean(problem)}
      >
        {ORDER.map((item) => (
          <option key={item} value={item}>
            {LABEL[item]}
          </option>
        ))}
      </NativeSelect>

      {when.kind === "tag" ? (
        <NativeSelect
          label={`${label}: tag`}
          hideLabel
          value={when.tag_id}
          invalid={Boolean(problem)}
          onChange={(value) => onChange({ ...when, tag_id: value })}
        >
          <option value="">Choose a tag</option>
          {tags.map((tag) => (
            <option key={tag.id} value={tag.id}>
              {tag.name}
            </option>
          ))}
        </NativeSelect>
      ) : null}

      {when.kind === "field" ? (
        <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <NativeSelect
            label={`${label}: field`}
            hideLabel
            value={when.key}
            invalid={Boolean(problem)}
            onChange={(value) => onChange({ ...when, key: value })}
          >
            <option value="">Choose a field</option>
            {fields.map((field) => (
              <option key={field.key} value={field.key}>
                {field.label}
              </option>
            ))}
          </NativeSelect>
          <NativeSelect
            label={`${label}: test`}
            hideLabel
            value={when.op ?? "set"}
            onChange={(value) => onChange({ ...when, op: value as "set" | "unset" | "equals" })}
          >
            <option value="set">is filled in</option>
            <option value="unset">is empty</option>
            <option value="equals">is exactly</option>
          </NativeSelect>
          {when.op === "equals" ? (
            <div className="sm:col-span-2">
              <Label htmlFor={`${id}-value`} className="sr-only">
                {label}: value
              </Label>
              <Input
                id={`${id}-value`}
                value={when.value ?? ""}
                maxLength={200}
                placeholder="Value to compare with"
                aria-invalid={problem ? true : undefined}
                onChange={(event) => onChange({ ...when, value: event.target.value })}
                size="lg"
              />
            </div>
          ) : null}
        </div>
      ) : null}

      {when.kind === "lead_score" ? (
        <div>
          <Label htmlFor={`${id}-score`} className="sr-only">
            {label}: score
          </Label>
          <Input
            id={`${id}-score`}
            type="number"
            inputMode="numeric"
            min={0}
            max={100}
            value={when.at_least}
            onChange={(event) =>
              onChange({ ...when, at_least: Math.max(0, Math.min(100, Number(event.target.value) || 0)) })
            }
            size="lg"
            className="sm:max-w-32"
          />
        </div>
      ) : null}

      {when.kind === "lead_stage" ? (
        <NativeSelect
          label={`${label}: stage`}
          hideLabel
          value={when.stages[0] ?? "qualified"}
          onChange={(value) => onChange({ ...when, stages: [value as LeadStage] })}
        >
          {LEAD_STAGES.map((stage) => (
            <option key={stage.value} value={stage.value}>
              {STAGE_LABEL[stage.value]}
            </option>
          ))}
        </NativeSelect>
      ) : null}

      {problem ? <p className="text-xs text-danger-fg">{problem}</p> : null}
    </div>
  );
}
