/**
 * The editor's model (UX-SCR-03, F-11): the definition the autosave PUTs, which steps show for a
 * trigger, when each step is complete (FR-AUT-02), and which step an API field error belongs to.
 */
import type { ProblemField } from "@/lib/api/errors";
import type { Automation, AutomationDefinition, LinkButton, TriggerName } from "@/lib/api/types";

import {
  BUTTON_TITLE_MAX,
  charCount,
  clampChars,
  FOLLOW_NUDGE_MAX,
  MESSAGE_LIMIT_BYTES,
  OPENING_BUTTON_MAX,
  worstCaseBytes,
} from "./render";

export type StepId = "when" | "posts" | "keywords" | "then" | "settings";

export const DEFAULT_NAME = "Untitled automation";

/** Tap first (FR-AUT-21): the API's defaults for new comment automations. */
export const DEFAULT_OPENING_TEXT =
  "Hi {first_name|there}! Tap the button below, or just reply here, and I'll send it right over 👇";
export const DEFAULT_OPENING_BUTTON = "Send me the link";
/** The follow nudge (FR-AUT-22): the spec's example. */
export const DEFAULT_FOLLOW_NUDGE = "Enjoying this? Follow us for more like it.";

export function isCommentTrigger(trigger: TriggerName | null | undefined): boolean {
  return trigger === "comment_keyword" || trigger === "comment_any";
}

type TapFirstFields = Pick<AutomationDefinition, "trigger" | "action" | "confirm_first">;

/** Tap first applies to comment triggers that send a message (FR-AUT-21). */
export function usesTapFirst(draft: TapFirstFields): boolean {
  return isCommentTrigger(draft.trigger) && draft.action === "send_message" && draft.confirm_first;
}

/** The follow nudge applies to automations that send a message, on either trigger (FR-AUT-22). */
export function usesFollowNudge(draft: Pick<AutomationDefinition, "action" | "follow_nudge">): boolean {
  return draft.action === "send_message" && draft.follow_nudge;
}

/** Switching tap first on: the default opening and button fill whatever is still empty. */
export function tapFirstOn(
  draft: Pick<AutomationDefinition, "opening_text" | "opening_button">,
): Pick<AutomationDefinition, "confirm_first" | "opening_text" | "opening_button"> {
  return {
    confirm_first: true,
    opening_text: draft.opening_text?.trim() ? draft.opening_text : DEFAULT_OPENING_TEXT,
    opening_button: draft.opening_button?.trim() ? draft.opening_button : DEFAULT_OPENING_BUTTON,
  };
}

/**
 * A trigger change. Any comment needs chosen posts or the next post (FR-AUT-02), so it starts on
 * chosen posts. An automation that becomes a comment automation for the first time (it has never
 * had an opening) starts with tap first on, as new comment automations do (FR-AUT-21).
 */
export function triggerPatch(draft: AutomationDefinition, trigger: TriggerName): Partial<AutomationDefinition> {
  const patch: Partial<AutomationDefinition> = { trigger };
  if (trigger === "comment_any" && draft.post_scope === "all") patch.post_scope = "selected";
  const firstComment = isCommentTrigger(trigger) && !isCommentTrigger(draft.trigger);
  const neverOpened = draft.opening_text == null && draft.opening_button == null;
  if (firstComment && neverOpened) Object.assign(patch, tapFirstOn(draft));
  return patch;
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
    confirm_first: automation.confirm_first,
    opening_text: automation.opening_text ?? null,
    opening_button: automation.opening_button ?? null,
    follow_nudge: automation.follow_nudge,
    follow_nudge_text: automation.follow_nudge_text ?? null,
  };
}

/**
 * What the autosave sends. The editor keeps everything the user typed, but the request carries
 * only what the trigger uses (no keywords for Any comment, no posts, public replies or tap first
 * for DMs), and leaves out blank reply variations and link buttons until they have a title and a
 * URL. Tap first and the follow nudge go with a message: Reply with AI turns them off, while an
 * automation with no action yet keeps the API's defaults.
 */
export function toRequestBody(draft: AutomationDefinition): AutomationDefinition {
  const comment = isCommentTrigger(draft.trigger);
  const ai = draft.action === "ai_reply";
  const buttons = (draft.message_buttons ?? [])
    .map((button) => ({ title: button.title.trim().slice(0, BUTTON_TITLE_MAX), url: button.url.trim() }))
    .filter((button) => button.title && button.url);
  const openingButton = clampChars(draft.opening_button?.trim() ?? "", OPENING_BUTTON_MAX);
  return {
    ...draft,
    name: draft.name.trim() || DEFAULT_NAME,
    keywords: draft.trigger === "comment_any" ? [] : (draft.keywords ?? []),
    message_buttons: buttons,
    public_reply_texts: comment ? (draft.public_reply_texts ?? []).map((text) => text.trim()).filter(Boolean) : [],
    post_scope: comment ? draft.post_scope : "all",
    media_item_ids: comment && draft.post_scope === "selected" ? (draft.media_item_ids ?? []) : [],
    scheduled_post_ids: comment && draft.post_scope === "selected" ? (draft.scheduled_post_ids ?? []) : [],
    confirm_first: comment && !ai ? draft.confirm_first : false,
    opening_text: comment ? draft.opening_text || null : null,
    opening_button: comment ? openingButton || null : null,
    follow_nudge: ai ? false : draft.follow_nudge,
    follow_nudge_text: draft.follow_nudge_text || null,
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

export type OpeningProblems = { text?: string; button?: string };

/** Tap first's opening (FR-AUT-21): required text within 1,000 bytes, and a 1–20 character button. */
export function openingProblems(
  draft: Pick<AutomationDefinition, "opening_text" | "opening_button">,
  disclosure: string | null = null,
): OpeningProblems {
  const problems: OpeningProblems = {};
  const text = draft.opening_text ?? "";
  if (!text.trim()) problems.text = "Write the opening message.";
  else if (worstCaseBytes(text, disclosure) > MESSAGE_LIMIT_BYTES) {
    const limit = MESSAGE_LIMIT_BYTES.toLocaleString("en-US");
    problems.text = `Instagram allows ${limit} bytes in a DM, counting the longest name. Shorten the opening.`;
  }
  const button = draft.opening_button ?? "";
  if (!button.trim()) problems.button = "Add a button title.";
  else if (charCount(button) > OPENING_BUTTON_MAX) problems.button = `Use ${OPENING_BUTTON_MAX} characters or fewer.`;
  return problems;
}

/** The follow nudge's text (FR-AUT-22): required, up to 300 characters. */
export function followNudgeProblem(text: string | null | undefined): string | null {
  if (!text?.trim()) return "Write the follow message.";
  if (charCount(text) > FOLLOW_NUDGE_MAX) return `Use ${FOLLOW_NUDGE_MAX} characters or fewer.`;
  return null;
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
      const messageOk = hasContent && buttonsOk && worstCaseBytes(text, disclosure) <= MESSAGE_LIMIT_BYTES;
      // A private reply carries no image (C-030): only tap first's message, a normal DM, can.
      const tapFirst = usesTapFirst(draft);
      const imageOk = !isCommentTrigger(draft.trigger) || tapFirst || !draft.message_media_asset_id;
      const openingOk = !tapFirst || Object.keys(openingProblems(draft, disclosure)).length === 0;
      const nudgeOk = !usesFollowNudge(draft) || followNudgeProblem(draft.follow_nudge_text) === null;
      return messageOk && imageOk && openingOk && nudgeOk;
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
  confirm_first: "then",
  opening_text: "then",
  opening_button: "then",
  follow_nudge: "then",
  follow_nudge_text: "then",
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

/**
 * Switches that settle other fields' problems: turning tap first off drops the opening's, and on
 * allows the image (C-030); turning the nudge off drops its text's.
 */
const SETTLES: Record<string, string[]> = {
  confirm_first: ["opening_text", "opening_button", "message_media_asset_id"],
  follow_nudge: ["follow_nudge_text"],
};

/** The errors left after the user edits some fields: editing a field clears its messages. */
export function clearFieldErrors(errors: FieldErrors, changed: string[]): FieldErrors {
  if (changed.length === 0) return errors;
  const cleared = new Set(changed.flatMap((field) => [field, ...(SETTLES[field] ?? [])]));
  const out: FieldErrors = {};
  for (const [field, message] of Object.entries(errors)) {
    const root = field.split(".")[0];
    if (!cleared.has(root)) out[field] = message;
  }
  return out;
}
