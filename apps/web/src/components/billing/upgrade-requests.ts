import type { UpgradeRequest } from "@/lib/api/provider";

/**
 * What "Upgrade" asks the upgrade dialog (UI-063: one behaviour per word). Every Upgrade control
 * opens the dialog; these are the requests the ones without a 402 of their own send.
 */

/** A plain Upgrade with no limit hit: the dialog says what Pro adds. */
export const PLAN_UPGRADE: UpgradeRequest = { code: "entitlement_required", entitlement: "pro" };

/** The AI credits' Upgrade: once they are used up the dialog names the limit and the reset date. */
export function creditsUpgrade(used: number, limit: number): UpgradeRequest {
  return used >= limit ? { code: "quota_exceeded", entitlement: "ai_credits_monthly", limit } : PLAN_UPGRADE;
}

/** The AI credits ran out and the screen has no figures of its own: the dialog reads the limit from billing. */
export const CREDITS_EXHAUSTED: UpgradeRequest = { code: "quota_exceeded", entitlement: "ai_credits_monthly" };

/** The knowledge meter's Upgrade, shown once the characters are used up. */
export function knowledgeUpgrade(limit: number | null | undefined): UpgradeRequest {
  return { code: "quota_exceeded", entitlement: "knowledge_characters", limit };
}

/** The product catalogue's Upgrade (GR-31, PD-8: Pro and Max): adding, importing and syncing products. */
export const COMMERCE_UPGRADE: UpgradeRequest = { code: "entitlement_required", entitlement: "commerce" };
