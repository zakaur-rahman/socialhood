import {
  Activity,
  Bell,
  Bot,
  Building2,
  CreditCard,
  Globe,
  KeyRound,
  Link2,
  MessageSquareText,
  MoreHorizontal,
  Palette,
  Plug,
  ScrollText,
  Sparkles,
  Timer,
  Users,
  Webhook,
  type LucideIcon,
} from "lucide-react";

import type { Role } from "@/lib/api/types";

import { SETTINGS_SECTIONS, type SettingsSection } from "./sections";

/**
 * The settings rail's grouping. `sections.ts` stays the list of pages and who sees them; this file
 * says how they are grouped, and gives each an icon, a one-line description and search keywords.
 * A segment named here that `SETTINGS_SECTIONS` lacks (a page on another branch) is skipped; a
 * section named in no group lands in a final "More" group, so nothing disappears.
 */
export type SettingsSegmentMeta = {
  icon: LucideIcon;
  description: string;
  keywords: readonly string[];
};

export const SEGMENT_META: Record<string, SettingsSegmentMeta> = {
  workspace: {
    icon: Building2,
    description: "Name, logo and basics",
    keywords: ["general", "name", "logo", "timezone"],
  },
  members: {
    icon: Users,
    description: "Who can use this workspace",
    keywords: ["team", "invite", "roles", "people"],
  },
  hours: {
    icon: Timer,
    description: "Open hours and the away message",
    keywords: ["schedule", "away", "opening", "time"],
  },
  connections: {
    icon: Link2,
    description: "Instagram and WhatsApp accounts",
    keywords: ["instagram", "whatsapp", "facebook", "accounts", "connect"],
  },
  widget: {
    icon: Globe,
    description: "Chat widget for your website",
    keywords: ["website", "embed", "chat", "install"],
  },
  ai: {
    icon: Sparkles,
    description: "When the AI replies and when a person takes over",
    keywords: ["spam", "takeover", "auto", "escalation", "rules"],
  },
  replies: {
    icon: MessageSquareText,
    description: "Snippets you type after a slash",
    keywords: ["snippets", "templates", "canned", "shortcuts"],
  },
  agent: {
    icon: Bot,
    description: "Ask Amplychat and its run history",
    keywords: ["assistant", "ask", "runs", "history"],
  },
  "ai-apps": {
    icon: Plug,
    description: "Claude, ChatGPT and Codex",
    keywords: ["mcp", "claude", "chatgpt", "codex", "oauth", "connectors", "ai apps"],
  },
  "api-keys": {
    icon: KeyRound,
    description: "For the public API and AI apps",
    keywords: ["api", "key", "token", "mcp", "claude code", "codex", "zapier", "bearer"],
  },
  billing: {
    icon: CreditCard,
    description: "Plan, usage and invoices",
    keywords: ["plan", "upgrade", "invoice", "payment", "usage"],
  },
  integrations: {
    icon: Webhook,
    description: "Webhooks and outside tools",
    keywords: ["webhook", "zapier", "outbound", "sheets"],
  },
  audit: {
    icon: ScrollText,
    description: "Who changed what",
    keywords: ["log", "security", "changes", "history"],
  },
  activity: {
    icon: Activity,
    description: "What automations and sends did",
    keywords: ["failures", "errors", "sends", "log"],
  },
  notifications: {
    icon: Bell,
    description: "Your digest and push alerts",
    keywords: ["email", "push", "digest", "alerts"],
  },
  appearance: {
    icon: Palette,
    description: "Dark, light or system theme",
    keywords: ["theme", "dark", "light", "colour", "color"],
  },
};

export type SettingsGroupDef = {
  id: string;
  label: string;
  hint?: string;
  segments: readonly string[];
};

export const SETTINGS_GROUPS: readonly SettingsGroupDef[] = [
  {
    id: "workspace",
    label: "Workspace",
    segments: ["workspace", "members", "hours"],
  },
  { id: "channels", label: "Channels", segments: ["connections", "widget"] },
  {
    id: "automation",
    label: "Automation and AI",
    segments: ["ai", "replies", "agent", "ai-apps"],
  },
  {
    id: "admin",
    label: "Admin",
    segments: ["billing", "integrations", "api-keys", "audit", "activity"],
  },
  {
    id: "you",
    label: "Just for you",
    hint: "Only changes things for you",
    segments: ["notifications", "appearance"],
  },
];

export type SettingsItem = {
  segment: string;
  label: string;
  description: string;
  icon: LucideIcon;
  keywords: readonly string[];
};
export type SettingsGroup = {
  id: string;
  label: string;
  hint?: string;
  items: SettingsItem[];
};

const FALLBACK_META: SettingsSegmentMeta = {
  icon: MoreHorizontal,
  description: "",
  keywords: [],
};

function toItem(section: SettingsSection): SettingsItem {
  const meta = SEGMENT_META[section.segment] ?? FALLBACK_META;
  return { segment: section.segment, label: section.label, ...meta };
}

/** The groups this role sees, in order; a group with no visible page is left out. */
export function visibleGroups(role: Role, sections: readonly SettingsSection[] = SETTINGS_SECTIONS): SettingsGroup[] {
  const allowed = new Map(sections.filter((s) => s.roles.includes(role)).map((s) => [s.segment, s]));
  const placed = new Set<string>();
  const groups: SettingsGroup[] = SETTINGS_GROUPS.map((group) => ({
    id: group.id,
    label: group.label,
    hint: group.hint,
    items: group.segments.flatMap((segment) => {
      const section = allowed.get(segment);
      if (!section) return [];
      placed.add(segment);
      return [toItem(section)];
    }),
  }));
  const more = [...allowed.values()].filter((s) => !placed.has(s.segment)).map(toItem);
  if (more.length > 0) groups.push({ id: "more", label: "More", items: more });
  return groups.filter((group) => group.items.length > 0);
}

/** Label or keyword contains the text (any case); groups left empty drop out. */
export function filterGroups(groups: SettingsGroup[], query: string): SettingsGroup[] {
  const q = query.trim().toLowerCase();
  if (!q) return groups;
  return groups
    .map((group) => ({
      ...group,
      items: group.items.filter(
        (item) => item.label.toLowerCase().includes(q) || item.keywords.some((k) => k.toLowerCase().includes(q)),
      ),
    }))
    .filter((group) => group.items.length > 0);
}
