import type { Role } from "@/lib/api/types";

const EVERYONE: readonly Role[] = ["owner", "admin", "agent"];

export type SettingsSection = { segment: string; label: string; roles: readonly Role[] };

/**
 * UX-SCR-07 sections in the spec's order, then Ask Social Hood. Role visibility is unchanged
 * (C-066). D-08: each tab's label equals its page's title.
 */
export const SETTINGS_SECTIONS: readonly SettingsSection[] = [
  { segment: "connections", label: "Connections", roles: EVERYONE },
  { segment: "ai", label: "AI rules and takeover", roles: EVERYONE },
  { segment: "workspace", label: "Workspace", roles: EVERYONE },
  // T8.6: every member's own digest and push settings.
  { segment: "notifications", label: "Notifications", roles: EVERYONE },
  // §3.1: billing is the owner's (admins see it read-only, C-048's Upgrade leads there).
  { segment: "billing", label: "Billing and usage", roles: ["owner", "admin"] },
  // agent-architecture.html §12: Settings → Agent, with the run history (FR-AGT-07).
  { segment: "agent", label: "Ask Social Hood", roles: EVERYONE },
];
