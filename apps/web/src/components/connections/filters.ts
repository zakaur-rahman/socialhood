import type { SocialAccount } from "@/lib/api/types";

/** Settings → Connections' segmented filter (C-066). Sandboxes overlap the other two. */
export type AccountFilter = "all" | "connected" | "disconnected" | "sandbox";

export const ACCOUNT_FILTERS: readonly { value: AccountFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "connected", label: "Connected" },
  { value: "disconnected", label: "Disconnected" },
  { value: "sandbox", label: "Sandboxes" },
];

const PLATFORM_WORDS = { instagram: "instagram", whatsapp: "whatsapp" } as const;

/** Name, handle, number or platform contains the text (any case). */
export function matchesSearch(account: SocialAccount, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return [account.display_name, account.username, account.username ? `@${account.username}` : null, account.phone_number, PLATFORM_WORDS[account.platform]]
    .filter((value): value is string => Boolean(value))
    .some((value) => value.toLowerCase().includes(q));
}

/** Connected means not disconnected: an account that needs reconnecting is still connected. */
export function inFilter(account: SocialAccount, filter: AccountFilter): boolean {
  switch (filter) {
    case "connected":
      return account.status !== "disconnected";
    case "disconnected":
      return account.status === "disconnected";
    case "sandbox":
      return account.sandbox === true;
    case "all":
    default:
      return true;
  }
}

/** Each filter's count over the accounts the search matches, so a count is what the filter shows. */
export function filterCounts(accounts: SocialAccount[], query = ""): Record<AccountFilter, number> {
  const matching = accounts.filter((account) => matchesSearch(account, query));
  return {
    all: matching.length,
    connected: matching.filter((a) => inFilter(a, "connected")).length,
    disconnected: matching.filter((a) => inFilter(a, "disconnected")).length,
    sandbox: matching.filter((a) => inFilter(a, "sandbox")).length,
  };
}

export function visibleAccounts(accounts: SocialAccount[], filter: AccountFilter, query: string): SocialAccount[] {
  return accounts.filter((account) => inFilter(account, filter) && matchesSearch(account, query));
}
