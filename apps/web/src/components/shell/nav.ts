import type { Route } from "next";
import {
  BookOpen,
  CalendarDays,
  House,
  Inbox,
  MessageSquare,
  Settings,
  Zap,
  type LucideIcon,
} from "lucide-react";

import type { Role } from "@/lib/api/types";

export type NavItem = {
  key: string;
  label: string;
  icon: LucideIcon;
  /** First path segment after /w/{slug}/, used to mark the active item. */
  segment: string;
  roles: readonly Role[];
  href: (slug: string) => Route;
};

export type NavGroup = {
  key: string;
  /** The small section label; null for Home, which stands alone at the top. */
  label: string | null;
  roles: readonly Role[];
  items: readonly NavItem[];
};

const EVERYONE = ["owner", "admin", "agent"] as const;
const ADMINS = ["owner", "admin"] as const;

/**
 * Typed routes check literal hrefs at each <Link>, but a helper that builds `/w/${slug}/…`
 * cannot carry that check, so nav hrefs are cast here, in one place.
 */
function route(path: string): Route {
  return path as Route;
}

const HOME: NavItem = { key: "home", label: "Home", icon: House, segment: "home", roles: EVERYONE, href: (s) => route(`/w/${s}/home`) };
const INBOX: NavItem = { key: "inbox", label: "Inbox", icon: Inbox, segment: "inbox", roles: EVERYONE, href: (s) => route(`/w/${s}/inbox`) };
const COMMENTS: NavItem = { key: "comments", label: "Comments", icon: MessageSquare, segment: "comments", roles: EVERYONE, href: (s) => route(`/w/${s}/comments`) };
const SCHEDULE: NavItem = { key: "schedule", label: "Schedule", icon: CalendarDays, segment: "schedule", roles: ADMINS, href: (s) => route(`/w/${s}/schedule`) };
const AUTOMATIONS: NavItem = { key: "automations", label: "Automations", icon: Zap, segment: "automations", roles: ADMINS, href: (s) => route(`/w/${s}/automations`) };
const KNOWLEDGE: NavItem = { key: "knowledge", label: "Knowledge", icon: BookOpen, segment: "knowledge", roles: ADMINS, href: (s) => route(`/w/${s}/knowledge`) };

// §3.1's sections, grouped: Home alone; Engage (Inbox, Comments); Grow, for owners and admins.
// Agents see Home, Inbox and Comments.
export const NAV_GROUPS: readonly NavGroup[] = [
  { key: "home", label: null, roles: EVERYONE, items: [HOME] },
  { key: "engage", label: "Engage", roles: EVERYONE, items: [INBOX, COMMENTS] },
  { key: "grow", label: "Grow", roles: ADMINS, items: [SCHEDULE, AUTOMATIONS, KNOWLEDGE] },
];

export const PRIMARY_NAV: readonly NavItem[] = NAV_GROUPS.flatMap((group) => group.items);

export const SETTINGS_NAV: NavItem = {
  key: "settings",
  label: "Settings",
  icon: Settings,
  segment: "settings",
  roles: EVERYONE,
  href: (s) => route(`/w/${s}/settings/connections`),
};

export const BILLING_HREF = (slug: string): Route => route(`/w/${slug}/settings/billing`);
export const WORKSPACE_SETTINGS_HREF = (slug: string): Route => route(`/w/${slug}/settings/workspace`);
/** Where switching to another workspace lands. */
export const WORKSPACE_HOME_HREF = (slug: string): Route => route(`/w/${slug}/home`);

/** The groups a role sees, each with the items it may open; a group left empty is dropped. */
export function navGroupsFor(role: Role): NavGroup[] {
  return NAV_GROUPS.filter((group) => group.roles.includes(role))
    .map((group) => ({ ...group, items: group.items.filter((item) => item.roles.includes(role)) }))
    .filter((group) => group.items.length > 0);
}

export function navFor(role: Role): NavItem[] {
  return navGroupsFor(role).flatMap((group) => group.items);
}

export function activeSegment(pathname: string, slug: string): string | null {
  const prefix = `/w/${slug}/`;
  if (!pathname.startsWith(prefix)) return null;
  return pathname.slice(prefix.length).split("/")[0] || null;
}

/** Pages outside the nav that still name the phone top bar. */
const OTHER_TITLES: Record<string, string> = { ask: "Ask Social Hood" };

export function pageTitle(pathname: string, slug: string): string {
  const segment = activeSegment(pathname, slug);
  const item = [...PRIMARY_NAV, SETTINGS_NAV].find((i) => i.segment === segment);
  return item?.label ?? (segment ? OTHER_TITLES[segment] : undefined) ?? "Social Hood";
}
