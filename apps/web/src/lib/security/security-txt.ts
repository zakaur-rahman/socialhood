import { SUPPORT_EMAIL } from "@/lib/copy";
import { absoluteUrl, siteUrl } from "@/lib/marketing/site";

/** The page security.txt's Policy field points at (app/(marketing)/security). */
export const SECURITY_POLICY_PATH = "/security";
export const SECURITY_TXT_PATH = "/.well-known/security.txt";

/**
 * How far ahead Expires is. RFC 9116 §2.5.5 recommends less than a year; the route is rebuilt
 * daily (its `revalidate`), so the file is always about this far from expiring.
 */
export const SECURITY_TXT_LIFETIME_DAYS = 360;

/**
 * /.well-known/security.txt (RFC 9116, C-143): where to report a vulnerability, in English, and
 * the policy page. Expires is counted from `now`, at midnight UTC so a day's builds agree.
 */
export function securityTxt(now: Date = new Date(), origin: string = siteUrl()): string {
  const expires = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
  expires.setUTCDate(expires.getUTCDate() + SECURITY_TXT_LIFETIME_DAYS);
  return [
    `Contact: mailto:${SUPPORT_EMAIL}`,
    `Expires: ${expires.toISOString().replace(".000Z", "Z")}`,
    "Preferred-Languages: en",
    `Canonical: ${absoluteUrl(SECURITY_TXT_PATH, origin)}`,
    `Policy: ${absoluteUrl(SECURITY_POLICY_PATH, origin)}`,
    "",
  ].join("\n");
}
