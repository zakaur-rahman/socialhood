/**
 * What a message may be on the account's platform (GR-29). Instagram counts the UTF-8 bytes of a
 * DM (1,000, TR-PL-10); a Facebook Page counts characters (Messenger's text limit, 2,000;
 * unverified until a real Page confirms it). The API checks the same on activation
 * (services/automations/validation.py), with the same words.
 */
import type { Platform } from "@/lib/api/types";

import { MESSAGE_LIMIT_BYTES, worstCaseBytes, worstCaseChars } from "./render";

export const FACEBOOK_MESSAGE_CHARS = 2000;

export type MessageLimit = { limit: number; unit: "bytes" | "characters" };

export function messageLimit(platform?: Platform | null): MessageLimit {
  return platform === "facebook"
    ? { limit: FACEBOOK_MESSAGE_CHARS, unit: "characters" }
    : { limit: MESSAGE_LIMIT_BYTES, unit: "bytes" };
}

/** The message in its worst case with the disclosure line, in the platform's unit. */
export function messageSize(text: string, disclosure: string | null | undefined, platform?: Platform | null): number {
  return platform === "facebook" ? worstCaseChars(text, disclosure) : worstCaseBytes(text, disclosure);
}

export function networkName(platform?: Platform | null): string {
  return platform === "facebook" ? "Facebook" : "Instagram";
}

/** "Instagram allows 1,000 bytes in a DM, counting the longest name. Shorten it." */
export function overLimitCopy(platform: Platform | null | undefined, shorten: string, counting = true): string {
  const { limit, unit } = messageLimit(platform);
  const where = platform === "facebook" ? "a message" : "a DM";
  return `${networkName(platform)} allows ${limit.toLocaleString("en-US")} ${unit} in ${where}${counting ? ", counting the longest name" : ""}. Shorten ${shorten}.`;
}
