/** Presentation rules for automations (UX-SCR-02, 03, 12). Pure functions, tested directly. */
import type {
  Automation,
  AutomationDefinition,
  DisplayStatus,
  MatchMode,
  OverlapWarning,
  QueueInfo,
  RunResult,
  SurgeOrder,
  TemplateCategory,
  TriggerName,
} from "@/lib/api/types";
import { relativeTime } from "@/lib/time";
import { zonedParts } from "@/lib/tz";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const pad = (n: number) => String(n).padStart(2, "0");

export const TRIGGER_LABEL: Record<TriggerName, string> = {
  comment_keyword: "Comment keyword",
  comment_any: "Any comment",
  dm_keyword: "DM keyword",
};

export const MATCH_LABEL: Record<MatchMode, string> = {
  word: "Whole word",
  exact: "Exact message",
  contains: "Contains",
};

export const MATCH_HINT: Record<MatchMode, string> = {
  word: "“price” matches “What’s the PRICE?” but not “priceless”.",
  exact: "The whole message must be the keyword.",
  contains: "The keyword can appear anywhere, even inside a word.",
};

export const STATUS_LABEL: Record<DisplayStatus, string> = {
  draft: "Draft",
  scheduled: "Scheduled",
  active: "Active",
  paused: "Paused",
  ended: "Ended",
};

export const SURGE_LABEL: Record<SurgeOrder, string> = {
  oldest_first: "Oldest first",
  newest_first: "Newest first",
  public_only: "Public reply only",
};

export const SURGE_HINT: Record<SurgeOrder, string> = {
  oldest_first: "Everyone gets the DM in the order they commented.",
  newest_first: "Reach people who just commented first.",
  public_only: "Skip the DM and post only the public reply.",
};

export const CATEGORY_LABEL: Record<TemplateCategory, string> = { grow: "Grow", sell: "Sell", support: "Support" };

export const RESULT_LABEL: Record<RunResult, string> = {
  sent: "Sent",
  queued: "Queued",
  partial: "Partial",
  failed: "Failed",
  skipped_cooldown: "Skipped: cooldown",
  skipped_expired: "Skipped: 7-day limit passed",
  escalated: "Escalated",
};

const numberFormat = new Intl.NumberFormat("en-US");

/** "2,140" */
export function formatCount(n: number): string {
  return numberFormat.format(n);
}

function plural(n: number, one: string, many: string): string {
  return `${formatCount(n)} ${n === 1 ? one : many}`;
}

/** The row's trigger label: "Comment on 3 posts", "Any comment on next post", "DM keyword". */
export function triggerSummary(automation: Pick<Automation, "trigger" | "post_scope" | "posts">): string {
  const { trigger, post_scope: scope, posts } = automation;
  if (!trigger) return "No trigger yet";
  if (trigger === "dm_keyword") return "DM keyword";
  const lead = trigger === "comment_any" ? "Any comment" : "Comment";
  if (scope === "next_post") return `${lead} on next post`;
  if (scope === "selected") return `${lead} on ${plural(posts.length, "post", "posts")}`;
  return `${lead} on any post`;
}

/** The action badge: Message, Message + link, AI reply. */
export function actionBadge(automation: Pick<Automation, "action" | "message_buttons">): string | null {
  if (automation.action === "ai_reply") return "AI reply";
  if (automation.action === "send_message") return automation.message_buttons.length > 0 ? "Message + link" : "Message";
  return null;
}

/** "about 3 h", "about 25 min", "under a minute". */
export function etaText(minutes: number | null | undefined): string | null {
  if (minutes === null || minutes === undefined) return null;
  if (minutes < 1) return "under a minute";
  if (minutes < 60) return `about ${Math.round(minutes)} min`;
  return `about ${Math.round(minutes / 60)} h`;
}

/** The row's queue badge: "2,140 waiting · about 3 h", or null when nobody waits. */
export function queueBadge(queue: Pick<QueueInfo, "waiting" | "eta_minutes">): string | null {
  if (queue.waiting <= 0) return null;
  const eta = etaText(queue.eta_minutes);
  return eta ? `${formatCount(queue.waiting)} waiting · ${eta}` : `${formatCount(queue.waiting)} waiting`;
}

/** The editor's queue banner (FR-AUT-10): "2,140 DMs waiting · all sent in about 3 h". */
export function queueBanner(queue: Pick<QueueInfo, "waiting" | "eta_minutes">): string {
  const count = plural(queue.waiting, "DM waiting", "DMs waiting");
  const eta = etaText(queue.eta_minutes);
  return eta ? `${count} · all sent in ${eta}` : count;
}

/** "1 Oct" in the workspace timezone. */
export function shortDate(iso: string, timeZone: string): string {
  const p = zonedParts(new Date(iso), timeZone);
  return `${p.day} ${MONTHS[p.month - 1]}`;
}

/** "15 Oct, 23:59" in the workspace timezone. */
export function shortDateTime(iso: string, timeZone: string): string {
  const p = zonedParts(new Date(iso), timeZone);
  return `${p.day} ${MONTHS[p.month - 1]}, ${pad(p.hour)}:${pad(p.minute)}`;
}

/** Status text in the row for Scheduled ("Starts 1 Oct") and Ended. */
export function statusText(
  automation: Pick<Automation, "display_status" | "starts_at" | "ends_at">,
  timeZone: string,
): string | null {
  if (automation.display_status === "scheduled" && automation.starts_at) {
    return `Starts ${shortDate(automation.starts_at, timeZone)}`;
  }
  if (automation.display_status === "ended") {
    return automation.ends_at ? `Ended ${shortDate(automation.ends_at, timeZone)}` : "Ended";
  }
  return null;
}

/** "12m ago", "just now", "No runs yet". */
export function lastRunText(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return "No runs yet";
  const relative = relativeTime(iso, now);
  if (relative === "now") return "just now";
  return /^\d+[mhd]$/.test(relative) ? `${relative} ago` : relative;
}

export function cooldownText(hours: number): string {
  if (hours <= 0) return "Every time someone matches";
  if (hours === 1) return "Once per person every hour";
  return `Once per person every ${hours} h`;
}

export function runWindowText(startsAt: string | null | undefined, endsAt: string | null | undefined, timeZone: string): string {
  if (startsAt && endsAt) return `Runs ${shortDateTime(startsAt, timeZone)} to ${shortDateTime(endsAt, timeZone)}`;
  if (startsAt) return `Starts ${shortDateTime(startsAt, timeZone)}`;
  if (endsAt) return `Runs until ${shortDateTime(endsAt, timeZone)}`;
  return "No end date";
}

/** Settings collapsed to one line (UX-SCR-03). */
export function settingsSummary(
  draft: Pick<AutomationDefinition, "cooldown_hours" | "surge_order" | "starts_at" | "ends_at" | "trigger">,
  timeZone: string,
  disclosure: string | null | undefined,
): string {
  const parts = [cooldownText(draft.cooldown_hours)];
  if (draft.trigger === "comment_keyword" || draft.trigger === "comment_any") {
    parts.push(`${SURGE_LABEL[draft.surge_order]} when busy`);
  }
  parts.push(runWindowText(draft.starts_at, draft.ends_at, timeZone));
  parts.push(disclosure ? "Disclosure on" : "Disclosure off");
  return parts.join(" · ");
}

/** FR-AUT-15: name the other automation and say which runs first. */
export function overlapText(overlap: OverlapWarning): { before: string; name: string; after: string } {
  return {
    before: `“${overlap.keyword}” is also used by `,
    name: overlap.automation_name,
    after: overlap.this_runs_first ? ". This automation runs first." : ", which runs first.",
  };
}

/** "Replied" as a share of DMs sent, or "—" before any DM (UX-SCR-12). */
export function repliedShare(replied: number, sent: number): string {
  if (sent <= 0) return "—";
  return `${Math.round((replied / sent) * 100)}%`;
}
