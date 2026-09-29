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
 * The byte counter's worst case: each field as a 30-character value (the API's sample), or its
 * fallback when that is longer, plus the disclosure line, which counts toward the limit.
 */
export function worstCaseBytes(text: string, disclosure: string | null | undefined): number {
  const longest = text.replace(FIELD, (_, field: FieldName, fallback: string | undefined) => {
    const sample = "x".repeat(SAMPLE_LENGTH);
    const alternative = fallback ?? DEFAULT_FALLBACK[field];
    return utf8Bytes(alternative) > SAMPLE_LENGTH ? alternative : sample;
  });
  return utf8Bytes(withDisclosure(longest, disclosure));
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