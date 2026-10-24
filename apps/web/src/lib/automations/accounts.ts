import type { SocialAccount } from "@/lib/api/types";

/** Platforms whose accounts automations, comments and entry links work on. */
export const AUTOMATION_PLATFORMS = ["instagram", "facebook"] as const;

/**
 * Automations run on Instagram accounts and Facebook Pages that are still connected (FR-AUT-01,
 * GR-29).
 */
export function automationAccounts(accounts: SocialAccount[]): SocialAccount[] {
  return accounts.filter(
    (account) => (AUTOMATION_PLATFORMS as readonly string[]).includes(account.platform) && account.status !== "disconnected",
  );
}

/**
 * Instagram accounts that are still connected: what only Instagram has (story mentions) and
 * publishing, until Pages publish too (GR-30).
 */
export function instagramAccounts(accounts: SocialAccount[]): SocialAccount[] {
  return accounts.filter((account) => account.platform === "instagram" && account.status !== "disconnected");
}

/** "@handle", else the name, else what kind of account it is. */
export function accountLabel(
  account: Pick<SocialAccount, "username" | "display_name"> & { platform?: string },
): string {
  if (account.username) return `@${account.username}`;
  return account.display_name ?? (account.platform === "facebook" ? "Facebook Page" : "Instagram account");
}
