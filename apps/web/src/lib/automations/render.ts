/**
 * Personal fields in automation messages (FR-AUT-13, FR-AUT-14), as the API renders them
 * (services/automations/render.py): {first_name} and {username}, each with an optional fallback
 * written {first_name|there}. Without one, {first_name} becomes "there" and {username} "".
 */

export type FieldName = "first_name" | "username";
export type FieldValues = { first_name?: string | null; username?: string | null };

const FIELD = /\{(first_name|username)(?:\|([^{}]{0,40}))?\}/g;
const DEFAULT_FALLBACK: Record<FieldName, string> = { first_name: "there", username: "" };

/** Instagram allows 1,000 bytes of UTF-8 in a DM (TR-PL-10). */
export const MESSAGE_LIMIT_BYTES = 1000;
export const MESSAGE_MAX_CHARS = 4000;
export const AI_INSTRUCTIONS_MAX = 2000;
export const PUBLIC_REPLY_MAX = 300;
export const MAX_PUBLIC_REPLIES = 5;
export const MAX_BUTTONS = 3;
export const BUTTON_TITLE_MAX = 20;
/** With link buttons the message is Instagram's button template: 640 characters of text. */
export const BUTTON_TEXT_MAX_CHARS = 640;
/** Tap first (FR-AUT-21): the opening is stored up to 2,000 characters; sent up to 1,000 bytes. */
export const OPENING_MAX_CHARS = 2000;
/** Instagram's quick-reply title limit. */
export const OPENING_BUTTON_MAX = 20;
/** The follow nudge (FR-AUT-22). */
export const FOLLOW_NUDGE_MAX = 300;
/** The API's long sample for the worst case: Instagram usernames are at most 30 characters. */
const SAMPLE_LENGTH = 30;

export function renderFields(text: string, values: FieldValues): string {
  return text.replace(FIELD, (_, field: FieldName, fallback: string | undefined) => {
    const value = values[field];
    if (value) return value;
    return fallback ?? DEFAULT_FALLBACK[field];
  });
}

export function withDisclosure(text: string, disclosure: string | null | undefined): string {
  return disclosure ? `${text}\n\n${disclosure}` : text;
}

export function utf8Bytes(text: string): number {
  return new TextEncoder().encode(text).length;
}

/**
 * The worst case the counters use: each field as a 30-character value (the API's sample), or its
 * fallback when that is longer, plus the disclosure line, which counts toward the limit.
 */
function longestRender(text: string, disclosure: string | null | undefined): string {
  const longest = text.replace(FIELD, (_, field: FieldName, fallback: string | undefined) => {
    const sample = "x".repeat(SAMPLE_LENGTH);
    const alternative = fallback ?? DEFAULT_FALLBACK[field];
    return utf8Bytes(alternative) > SAMPLE_LENGTH ? alternative : sample;
  });
  return withDisclosure(longest, disclosure);
}

export function worstCaseBytes(text: string, disclosure: string | null | undefined): number {
  return utf8Bytes(longestRender(text, disclosure));
}

/** Characters as the API counts them (code points), for the button template's limit. */
export function worstCaseChars(text: string, disclosure: string | null | undefined): number {
  return [...longestRender(text, disclosure)].length;
}

/** Characters as the API counts them (code points), e.g. "💛" is one. */
export function charCount(text: string): number {
  return [...text].length;
}

/** The text cut to a number of characters as the API counts them. */
export function clampChars(text: string, max: number): string {
  const chars = [...text];
  return chars.length > max ? chars.slice(0, max).join("") : text;
}

/** What "Insert field" puts at the cursor. */
export const INSERTABLE_FIELDS: { label: string; token: string }[] = [
  { label: "First name", token: "{first_name|there}" },
  { label: "Username", token: "{username}" },
];

/** Insert a token into text at a selection, returning the new text and the caret after it. */
export function insertAt(text: string, token: string, start: number, end = start): { text: string; caret: number } {
  const before = text.slice(0, start);
  const after = text.slice(end);
  return { text: `${before}${token}${after}`, caret: before.length + token.length };
}