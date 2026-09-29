/**
 * The editor's model (UX-SCR-03, F-11): the definition the autosave PUTs, which steps show for a
 * trigger, when each step is complete (FR-AUT-02), and which step an API field error belongs to.
 */
import type { ProblemField } from "@/lib/api/errors";
import type { Automation, AutomationDefinition, LinkButton, TriggerName } from "@/lib/api/types";

import { BUTTON_TITLE_MAX, MESSAGE_LIMIT_BYTES, worstCaseBytes } from "./render";

export type StepId = "when" | "posts" | "keywords" | "then" | "settings";

export const DEFAULT_NAME = "Untitled automation";

export function isCommentTrigger(trigger: TriggerName | null | undefined): boolean {
  return trigger === "comment_keyword" || trigger === "comment_any";
}

/** The editable definition of a stored automation. */
export function toDefinition(automation: Automation): AutomationDefinition {
  return {
    name: automation.name,
    social_account_id: automation.social_account_id ?? null,
    trigger: automation.trigger ?? null,
    keywords: [...automation.keywords],
    match_mode: automation.match_mode,
    action: automation.action ?? null,
    message_text: automation.message_text ?? null,
    message_buttons: automation.message_buttons.map((button) => ({ title: button.title, url: button.url })),
    message_media_asset_id: automation.message_media_asset_id ?? null,
    ai_instructions: automation.ai_instructions ?? null,
    public_reply_texts: [...automation.public_reply_texts],
    post_scope: automation.post_scope,
    media_item_ids: automation.posts.flatMap((post) => (post.media_item_id ? [post.media_item_id] : [])),
    scheduled_post_ids: automation.posts.flatMap((post) =>
      !post.media_item_id && post.scheduled_post_id ? [post.scheduled_post_id] : [],
    ),
    cooldown_hours: automation.cooldown_hours,
    starts_at: automation.starts_at ?? null,
    ends_at: automation.ends_at ?? null,
    surge_order: automation.surge_order,
  };
}

/**
 * What the autosave sends. The editor keeps everything the user typed, but the request carries
 * only what the trigger uses (no keywords for Any comment, no posts or public replies for DMs),
 * and leaves out blank reply variations and link buttons until they have a title and a URL.
 */
export function toRequestBody(draft: AutomationDefinition): AutomationDefinition {
  const comment = isCommentTrigger(draft.trigger);
  const buttons = (draft.message_buttons ?? [])
    .map((button) => ({ title: button.title.trim().slice(0, BUTTON_TITLE_MAX), url: button.url.trim() }))
    .filter((button) => button.title && button.url);
  return {
    ...draft,
    name: draft.name.trim() || DEFAULT_NAME,
    keywords: draft.trigger === "comment_any" ? [] : (draft.keywords ?? []),
    message_buttons: buttons,
    public_reply_texts: comment ? (draft.public_reply_texts ?? []).map((text) => text.trim()).filter(Boolean) : [],
    post_scope: comment ? draft.post_scope : "all",
    media_item_ids: comment && draft.post_scope === "selected" ? (draft.media_item_ids ?? []) : [],
    scheduled_post_ids: comment && draft.post_scope === "selected" ? (draft.scheduled_post_ids ?? []) : [],
  };
}

/** The steps a trigger uses, in order. Before a trigger is chosen the DM shape shows. */
export function visibleSteps(trigger: TriggerName | null | undefined): StepId[] {
  switch (trigger) {
    case "comment_keyword":
      return ["when", "posts", "keywords", "then", "settings"];
    case "comment_any":
      return ["when", "posts", "then", "settings"];
    default:
      return ["when", "keywords", "then", "settings"];
  }
}

// ---- validation as you type (FR-AUT-13)

export function isHttpsUrl(value: string): boolean {
  let url: URL;
  try {
    url = new URL(value.trim());
  } catch {
    return false;
  }
  return url.protocol === "https:" && url.hostname.includes(".") && !url.hostname.endsWith(".");
}

export type ButtonProblems = { title?: string; url?: string };

/** Problems with one link button; an untouched empty field is reported too (activation needs it). */
export function buttonProblems(button: LinkButton): ButtonProblems {
  const problems: ButtonProblems = {};
  if (!button.title.trim()) problems.title = "Add a button title.";
  else if (button.title.length > BUTTON_TITLE_MAX) problems.title = `Use ${BUTTON_TITLE_MAX} characters or fewer.`;
  if (!button.url.trim()) problems.url = "Add a link.";
  else if (!isHttpsUrl(button.url)) problems.url = "Use a full link that starts with https://";
  return problems;
}

/** The run window's end must come after its start (FR-AUT-17). */
export function runWindowProblem(draft: Pick<AutomationDefinition, "starts_at" | "ends_at">): string | null {
  if (!draft.starts_at || !draft.ends_at) return null;
  return new Date(draft.ends_at) <= new Date(draft.starts_at) ? "The end must be after the start." : null;
}

/** FR-AUT-02, per step, as the editor can tell before asking the API. */
export function stepComplete(step: StepId, draft: AutomationDefinition, disclosure: string | null = null): boolean {
  switch (step) {
    case "when":
      return Boolean(draft.social_account_id && draft.trigger);
    case "posts":
      if (draft.post_scope === "selected") {
        return (draft.media_item_ids?.length ?? 0) + (draft.scheduled_post_ids?.length ?? 0) > 0;
      }
      if (draft.post_scope === "all") return draft.trigger !== "comment_any";
      return true;
    case "keywords":
      return (draft.keywords?.length ?? 0) > 0;
    case "then": {
      if (draft.action === "ai_reply") return Boolean(draft.ai_instructions?.trim());
      if (draft.action !== "send_message") return false;
      const text = draft.message_text ?? "";
      const hasContent = Boolean(text.trim() || draft.message_media_asset_id);
      const buttonsOk = (draft.message_buttons ?? []).every((button) => Object.keys(buttonProblems(button)).length === 0);
      return hasContent && buttonsOk && worstCaseBytes(text, disclosure) <= MESSAGE_LIMIT_BYTES;
    }
    case "settings":
      return runWindowProblem(draft) === null;
  }
}

export function firstIncompleteStep(draft: AutomationDefinition, disclosure: string | null = null): StepId | null {
  return visibleSteps(draft.trigger).find((step) => !stepComplete(step, draft, disclosure)) ?? null;
}

// ---- API field errors (422 validation_error) → steps

const FIELD_STEP: Record<string, StepId | "name"> = {
  name: "name",
  social_account_id: "when",
  trigger: "when",
  post_scope: "posts",
  posts: "posts",
  media_item_ids: "posts",
  scheduled_post_ids: "posts",
  keywords: "keywords",
  match_mode: "keywords",
  action: "then",
  message_text: "then",
  message_buttons: "then",
  message_media_asset_id: "then",
  ai_instructions: "then",
  public_reply_texts: "then",
  cooldown_hours: "settings",
  starts_at: "settings",
  ends_at: "settings",
  surge_order: "settings",
};

/** "message_buttons.0.url" belongs to Then; unknown fields to none. */
export function stepOfField(field: string): StepId | "name" | null {
  return FIELD_STEP[field.split(".")[0]] ?? null;
}

export type FieldErrors = Record<string, string>;

/** 422 errors keyed by field name, first message per field. */
export function fieldErrors(errors: ProblemField[]): FieldErrors {
  const out: FieldErrors = {};
  for (const error of errors) if (!(error.field in out)) out[error.field] = error.message;
  return out;
}

export function stepsWithErrors(errors: FieldErrors): Set<StepId | "name"> {
  const steps = new Set<StepId | "name">();
  for (const field of Object.keys(errors)) {
    const step = stepOfField(field);
    if (step) steps.add(step);
  }
  return steps;
}

/** Messages for one step's fields, e.g. everything under message_buttons for Then. */
export function errorsFor(errors: FieldErrors, prefix: string): string[] {
  return Object.entries(errors)
    .filter(([field]) => field === prefix || field.startsWith(`${prefix}.`))
    .map(([, message]) => message);
}

/** The errors left after the user edits some fields: editing a field clears its messages. */
export function clearFieldErrors(errors: FieldErrors, changed: string[]): FieldErrors {
  if (changed.length === 0) return errors;
  const out: FieldErrors = {};
  for (const [field, message] of Object.entries(errors)) {
    const root = field.split(".")[0];
    if (!changed.includes(root)) out[field] = message;
  }
  return out;
}
