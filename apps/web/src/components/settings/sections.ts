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
  // GR-21: the snippets typed after / in a reply. Everyone reads and uses them; owners and admins edit.
  { segment: "replies", label: "Saved replies", roles: EVERYONE },
  // GR-22: when the workspace is open, the away message and Auto mode's hours (agents read them).
  { segment: "hours", label: "Business hours", roles: EVERYONE },
  // T8.6: every member's own digest and push settings.
  { segment: "notifications", label: "Notifications", roles: EVERYONE },
  // §3.1: billing is the owner's (admins see it read-only, C-048's Upgrade leads there).
  { segment: "billing", label: "Billing and usage", roles: ["owner", "admin"] },
  // GR-04: outbound webhooks, for owners and admins like the API's integrations routes.
  { segment: "integrations", label: "Integrations", roles: ["owner", "admin"] },
  // GR-19: the team and who did what, for owners and admins (the API enforces members.read and
  // audit.read; the pages also ask the API what the caller may do).
  { segment: "members", label: "Members", roles: ["owner", "admin"] },
  { segment: "audit", label: "Audit log", roles: ["owner", "admin"] },
  // GR-05: what automations and sends did and what failed, for owners and admins (the API's
  // activity route is admin-only, like the automations it reports on).
  { segment: "activity", label: "Activity", roles: ["owner", "admin"] },
  // agent-architecture.html §12: Settings → Agent, with the run history (FR-AGT-07).
  { segment: "agent", label: "Ask Social Hood", roles: EVERYONE },
];
