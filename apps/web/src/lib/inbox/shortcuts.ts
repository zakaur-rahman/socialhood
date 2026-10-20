/**
 * The inbox's single-key shortcuts (FR-INB-12) and the per-device switch for them (D-14, WCAG 2.1.4
 * "Character Key Shortcuts"): on by default, and when it is off the letter keys do nothing, so
 * speech input or a stray key can't archive a conversation. Shortcuts with Ctrl or Cmd (Ask Social
 * Hood's Ctrl+K, the sidebar's Ctrl+[) and Esc are not character keys and stay on.
 */

/** Remembered per device (try/catch-guarded localStorage, lib/use-browser-state). */
export const SINGLE_KEY_SHORTCUTS_KEY = "socialhood:inbox-shortcuts";

export type InboxShortcut = { keys: string[]; label: string };

/** In the order the dialog lists them. */
export const INBOX_SHORTCUTS: InboxShortcut[] = [
  { keys: ["j"], label: "Open the next conversation" },
  { keys: ["k"], label: "Open the previous conversation" },
  { keys: ["/"], label: "Search conversations" },
  { keys: ["e"], label: "Archive the open conversation, or move it back to the inbox" },
  { keys: ["u"], label: "Mark the open conversation unread" },
  { keys: ["?"], label: "Show this list" },
  { keys: ["Esc"], label: "Close the details panel, or go back to the list on a phone" },
];
