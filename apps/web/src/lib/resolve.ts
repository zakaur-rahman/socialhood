import type { SocialAccount } from "@/lib/api/types";

/**
 * Workspace pages a link from outside the app can ask /app for, as `/app?next=<page>`. Their URLs
 * need a workspace's slug, which a public page doesn't know (the digest's unsubscribe page, which
 * links to Settings › Notifications: UI-ISS-110). A fixed list, so the parameter can't send anyone
 * anywhere else.
 */
export const APP_NEXT_PAGES = ["settings/notifications"] as const;

export type AppNextPage = (typeof APP_NEXT_PAGES)[number];

/** A link to `page` in the signed-in user's last used workspace, through /app. */
export function appLink(page: AppNextPage): string {
  return `/app?next=${page}`;
}

function isNextPage(value: string | null): value is AppNextPage {
  return value !== null && (APP_NEXT_PAGES as readonly string[]).includes(value);
}

/**
 * Where /app sends a signed-in user (F-01, F-02): the last used workspace's inbox, or its Home
 * while no account is connected (the checklist starts there). An expired Instagram connect link
 * lands on /app (the API cannot tell which workspace it was for) and goes on to Connections (F-03).
 * A `next` page from APP_NEXT_PAGES opens that page instead. Null while the accounts are still
 * loading.
 */
export function resolveDestination(
  slug: string,
  accounts: SocialAccount[] | undefined,
  connectError: string | null,
  next: string | null = null,
): string | null {
  if (connectError === "state_invalid") return `/w/${slug}/settings/connections?error=state_invalid`;
  if (isNextPage(next)) return `/w/${slug}/${next}`;
  if (accounts === undefined) return null;
  const connected = accounts.some((account) => account.status !== "disconnected");
  return connected ? `/w/${slug}/inbox` : `/w/${slug}/home`;
}
