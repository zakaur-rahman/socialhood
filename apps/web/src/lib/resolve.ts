import type { SocialAccount } from "@/lib/api/types";

/**
 * Where /app sends a signed-in user (F-01, F-02): the last used workspace's inbox, or its Home
 * while no account is connected (the checklist starts there). An expired Instagram connect link
 * lands on /app (the API cannot tell which workspace it was for) and goes on to Connections (F-03).
 * Null while the accounts are still loading.
 */
export function resolveDestination(
  slug: string,
  accounts: SocialAccount[] | undefined,
  connectError: string | null,
): string | null {
  if (connectError === "state_invalid") return `/w/${slug}/settings/connections?error=state_invalid`;
  if (accounts === undefined) return null;
  const connected = accounts.some((account) => account.status !== "disconnected");
  return connected ? `/w/${slug}/inbox` : `/w/${slug}/home`;
}
