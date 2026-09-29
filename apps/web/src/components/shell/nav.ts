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

const EVERYONE = ["owner", "admin", "agent"] as const;
const ADMINS = ["owner", "admin"] as const;

/**
 * Typed routes check literal hrefs at each <Link>, but a helper that builds `/w/${slug}/…`
 * cannot carry that check, so nav hrefs are cast here, in one place.
 */
function route(path: string): Route {
  return path as Route;
}

/** A page built in a later phase: the link exists before the page does. */
function later(path: string, phase: "P5" | "P6" | "P7" | "P8"): Route {
  void phase; // documents where the page arrives
  return route(path);
}

// §3.1: Home, Inbox, Comments, Automations, Schedule, Knowledge. Agents see the first three.
export const PRIMARY_NAV: readonly NavItem[] = [
  { key: "home", label: "Home", icon: House, segment: "home", roles: EVERYONE, href: (s) => route(`/w/${s}/home`) },
  { key: "inbox", label: "Inbox", icon: Inbox, segment: "inbox", roles: EVERYONE, href: (s) => route(`/w/${s}/inbox`) },
  { key: "comments", label: "Comments", icon: MessageSquare, segment: "comments", roles: EVERYONE, href: (s) => later(`/w/${s}/comments`, "P6") },
  { key: "automations", label: "Automations", icon: Zap, segment: "automations", roles: ADMINS, href: (s) => route(`/w/${s}/automations`) },
  { key: "schedule", label: "Schedule", icon: CalendarDays, segment: "schedule", roles: ADMINS, href: (s) => later(`/w/${s}/schedule`, "P7") },
  { key: "knowledge", label: "Knowledge", icon: BookOpen, segment: "knowledge", roles: ADMINS, href: (s) => later(`/w/${s}/knowledge`, "P5") },
];

export const SETTINGS_NAV: NavItem = {
  key: "settings",
  label: "Settings",
  icon: Settings,
  segment: "settings",
  roles: EVERYONE,
  href: (s) => route(`/w/${s}/settings/connections`),
};

export const BILLING_HREF = (slug: string): Route => later(`/w/${slug}/settings/billing`, "P8");

export function navFor(role: Role): NavItem[] {
  return PRIMARY_NAV.filter((item) => item.roles.includes(role));
}

export function activeSegment(pathname: string, slug: string): string | null {
  const prefix = `/w/${slug}/`;
  if (!pathname.startsWith(prefix)) return null;
  return pathname.slice(prefix.length).split("/")[0] || null;
}

export function pageTitle(pathname: string, slug: string): string {
  const segment = activeSegment(pathname, slug);
  const item = [...PRIMARY_NAV, SETTINGS_NAV].find((i) => i.segment === segment);
  return item?.label ?? "Social Hood";
}
