import type { SavedReply } from "@/lib/api/types";

/** The most saved replies the composer's picker lists at once. */
export const PICKER_LIMIT = 6;

export type SlashToken = {
  /** Where the "/" is in the draft. */
  start: number;
  /** What follows it, lower case ("pri" for "/Pri"). */
  query: string;
};

const TOKEN = /(?:^|\s)\/([a-z0-9_-]{0,30})$/i;

/**
 * GR-21: the "/word" being typed at the caret, when the slash starts the draft, a line or follows a
 * space (so "https://x" and "and/or" are plain text). The caret must be at its end.
 */
export function slashToken(draft: string, caret: number): SlashToken | null {
  const before = draft.slice(0, caret);
  const match = TOKEN.exec(before);
  if (!match) return null;
  const query = match[1];
  return { start: before.length - query.length - 1, query: query.toLowerCase() };
}

/**
 * The replies a query finds: an exact shortcut first, then shortcuts that start with it, then
 * shortcuts or titles that contain it. An empty query lists them in shortcut order.
 */
export function matchReplies(replies: readonly SavedReply[], query: string): SavedReply[] {
  const wanted = query.trim().toLowerCase();
  const rank = (reply: SavedReply): number => {
    const shortcut = reply.shortcut.toLowerCase();
    if (wanted === "") return 1;
    if (shortcut === wanted) return 0;
    if (shortcut.startsWith(wanted)) return 1;
    if (shortcut.includes(wanted) || reply.title.toLowerCase().includes(wanted)) return 2;
    return 3;
  };
  return replies
    .map((reply) => ({ reply, rank: rank(reply) }))
    .filter((entry) => entry.rank < 3)
    .sort((a, b) => a.rank - b.rank || a.reply.shortcut.localeCompare(b.reply.shortcut))
    .slice(0, PICKER_LIMIT)
    .map((entry) => entry.reply);
}

/** The draft with the "/word" token replaced by the filled reply. */
export function insertReply(draft: string, token: SlashToken, text: string): { draft: string; caret: number } {
  const end = token.start + 1 + token.query.length;
  return { draft: draft.slice(0, token.start) + text + draft.slice(end), caret: token.start + text.length };
}
