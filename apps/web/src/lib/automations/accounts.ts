import type { SocialAccount } from "@/lib/api/types";

/** Automations run on Instagram accounts that are still connected (FR-AUT-01). */
export function instagramAccounts(accounts: SocialAccount[]): SocialAccount[] {
  return accounts.filter((account) => account.platform === "instagram" && account.status !== "disconnected");
}

export function accountLabel(account: Pick<SocialAccount, "username" | "display_name">): string {
  return account.username ? `@${account.username}` : (account.display_name ?? "Instagram account");
}
