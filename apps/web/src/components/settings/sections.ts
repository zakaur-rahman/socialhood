import type { Role } from "@/lib/api/types";

const EVERYONE: readonly Role[] = ["owner", "admin", "agent"];

export type SettingsSection = { segment: string; label: string; roles: readonly Role[] };

/** UX-SCR-07 sections in the spec's order, then Agent. Role visibility is unchanged (C-066). */
export const SETTINGS_SECTIONS: readonly SettingsSection[] = [
  { segment: "connections", label: "Connections", roles: EVERYONE },
  { segment: "ai", label: "AI Rules & Takeover", roles: EVERYONE },
  { segment: "workspace", label: "Workspace", roles: EVERYONE },
  // T8.6: every member's own digest and push settings.
  { segment: "notifications", label: "Notifications", roles: EVERYONE },
  // §3.1: billing is the owner's (admins see it read-only, C-048's Upgrade leads there).
  { segment: "billing", label: "Billing", roles: ["owner", "admin"] },
  // agent-architecture.html §12: Settings → Agent, with the run history (FR-AGT-07).
  { segment: "agent", label: "Agent", roles: EVERYONE },
];

/** The settings section a path is in ("/w/maple/settings/billing" → Billing), or null. */
export function currentSection(pathname: string): SettingsSection | null {
  const segment = /\/settings\/([^/?#]+)/.exec(pathname)?.[1];
  return SETTINGS_SECTIONS.find((section) => section.segment === segment) ?? null;
}
