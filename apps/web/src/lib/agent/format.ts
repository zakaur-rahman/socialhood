/**
 * Ask Social Hood's words (FR-AGT-01, FR-AGT-06, FR-AGT-07; §4.7 voice): run and step statuses,
 * the explicit states of a run that didn't answer, and the suggested prompts.
 */
import type { AgentMode, AgentRunStatus, AgentStepStatus, AnswerRefKind, ErrorInfo, RiskTier } from "@/lib/api/types";
import type { Tone } from "@/lib/inbox/format";
import { dayKey } from "@/lib/tz";

/** A run in one of these statuses won't change again (agent-architecture.html §9). */
export const FINAL_STATUSES: readonly AgentRunStatus[] = ["succeeded", "partial", "failed", "cancelled", "expired"];

export function isFinal(status: AgentRunStatus): boolean {
  return FINAL_STATUSES.includes(status);
}

/** Still working: the panel shows live steps and Cancel. */
export function isActive(status: AgentRunStatus): boolean {
  return !isFinal(status);
}

/** The history's status chip. No "thinking": the agent works through tools, and says so. */
export const RUN_STATUS_LABEL: Record<AgentRunStatus, string> = {
  queued: "Starting",
  planning: "Working",
  running: "Working",
  awaiting_approval: "Waiting for approval",
  succeeded: "Answered",
  partial: "Partly answered",
  failed: "Failed",
  cancelled: "Cancelled",
  expired: "Expired",
};

export const RUN_STATUS_TONE: Record<AgentRunStatus, Tone> = {
  queued: "brand",
  planning: "brand",
  running: "brand",
  awaiting_approval: "warning",
  succeeded: "neutral",
  partial: "warning",
  failed: "danger",
  cancelled: "neutral",
  expired: "neutral",
};

export const STEP_STATUS_LABEL: Record<AgentStepStatus, string> = {
  pending: "Waiting",
  running: "In progress",
  succeeded: "Done",
  failed: "Failed",
  skipped: "Skipped",
  blocked: "Not allowed",
  awaiting_approval: "Waiting for approval",
};

export const MODE_LABEL: Record<AgentMode, string> = {
  read_only: "Read only",
  copilot: "Copilot",
  supervised: "Supervised",
  autonomous: "Autonomous",
};

export const TIER_LABEL: Record<RiskTier, string> = {
  read: "Read",
  draft: "Draft",
  low: "Low risk",
  high: "High risk",
  destructive: "Destructive",
};

/** What a citation opens, in words: the sources list and the link's accessible name. */
export const REF_KIND_LABEL: Record<AnswerRefKind, string> = {
  post: "Post",
  conversation: "Conversation",
  comment: "Comment",
  automation: "Automation",
  scheduled_message: "Scheduled message",
  scheduled_post: "Scheduled post",
  knowledge_source: "Knowledge",
};

export type PromptArea = "inbox" | "comments" | "posts" | "automations";

/** FR-AGT-01 / agent-architecture.html §12: what a member can ask to begin with, one per area. */
export const SUGGESTED_PROMPTS: readonly { area: PromptArea; text: string }[] = [
  { area: "posts", text: "How did my latest post do?" },
  { area: "comments", text: "What are people complaining about this week?" },
  { area: "inbox", text: "Which conversations need a reply today?" },
  { area: "automations", text: "Which automation sent the most DMs this week?" },
];

/** Follow-up questions by what an answer cited (picked in the browser; no API involved). */
const FOLLOW_UPS: Record<AnswerRefKind, readonly string[]> = {
  post: ["Show the negative comments on this post", "Compare it with my previous post"],
  comment: ["Summarise the other complaints", "Which post gets comments like these?"],
  conversation: ["Which conversations need a reply today?", "Summarise this conversation"],
  automation: ["How is this automation doing this week?", "Which automations failed recently?"],
  scheduled_message: ["What else is scheduled this week?"],
  scheduled_post: ["What's scheduled to post this week?", "Which posts beat my average this month?"],
  knowledge_source: ["What questions couldn't the AI answer this week?"],
};
const GENERAL_FOLLOW_UPS = ["Which posts beat my average this month?", "What are people complaining about this week?"];

/**
 * Two or three follow-ups for an answer: taken in turn from each kind it cited (in citation order),
 * never repeating the question just asked; general ones when it cited nothing.
 */
export function followUpsFor(refs: readonly { kind: AnswerRefKind }[], request: string, max = 3): string[] {
  const kinds = [...new Set(refs.map((ref) => ref.kind))];
  const pools = kinds.length > 0 ? kinds.map((kind) => [...FOLLOW_UPS[kind]]) : [[...GENERAL_FOLLOW_UPS]];
  const asked = request.trim().toLowerCase();
  const out: string[] = [];
  for (let round = 0; out.length < max && pools.some((pool) => pool.length > round); round++) {
    for (const pool of pools) {
      const prompt = pool[round];
      if (prompt && prompt.toLowerCase() !== asked && !out.includes(prompt)) out.push(prompt);
      if (out.length === max) break;
    }
  }
  return out;
}

export type ThreadGroup = "Today" | "Yesterday" | "Previous 7 days" | "Older";

function dayNumber(iso: string | Date, timeZone: string): number {
  const [year, month, day] = dayKey(iso, timeZone).split("-").map(Number);
  return Date.UTC(year, month - 1, day) / 86_400_000;
}

/** Which group a thread's latest activity falls in, by calendar day in the workspace zone. */
export function threadGroup(lastRunAt: string, timeZone: string, now: Date): ThreadGroup {
  const days = dayNumber(now, timeZone) - dayNumber(lastRunAt, timeZone);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days <= 7) return "Previous 7 days";
  return "Older";
}

/** Items grouped in that order, keeping their order within each group; empty groups left out. */
export function groupThreads<T extends { last_run_at: string }>(
  items: readonly T[],
  timeZone: string,
  now: Date,
): { group: ThreadGroup; items: T[] }[] {
  const order: ThreadGroup[] = ["Today", "Yesterday", "Previous 7 days", "Older"];
  const groups = new Map<ThreadGroup, T[]>(order.map((group) => [group, []]));
  for (const item of items) groups.get(threadGroup(item.last_run_at, timeZone, now))!.push(item);
  return order.filter((group) => groups.get(group)!.length > 0).map((group) => ({ group, items: groups.get(group)! }));
}

/** POST …/agent/runs caps the request (schemas/agent.py REQUEST_MAX_CHARS). */
export const REQUEST_MAX_CHARS = 2000;

export type RunOutcome =
  | { kind: "quota"; title: string; body: string }
  | { kind: "failed"; title: string; body: string }
  | { kind: "cancelled"; title: string; body: string }
  | { kind: "expired"; title: string; body: string };

function isQuota(error: ErrorInfo | null | undefined): boolean {
  return error?.code === "quota_exceeded";
}

/**
 * The explicit state of a run that ended without a full answer (FR-AGT-06: say so, never guess).
 * Partial runs still have an answer; its missing pieces are named in it.
 */
export function runOutcome(status: AgentRunStatus, error: ErrorInfo | null | undefined): RunOutcome | null {
  if (isQuota(error) && (status === "failed" || status === "partial")) {
    return {
      kind: "quota",
      title: "Out of AI credits",
      body: error?.message?.trim() || "This workspace has used all its AI credits for this month.",
    };
  }
  switch (status) {
    case "failed":
      return {
        kind: "failed",
        title: "This question didn't get an answer",
        body: error?.message?.trim() || "The AI didn't respond. Try again.",
      };
    case "cancelled":
      return { kind: "cancelled", title: "Cancelled", body: "You stopped this question. Steps that had finished are kept." };
    case "expired":
      return { kind: "expired", title: "Expired", body: "This question waited too long and stopped." };
    default:
      return null;
  }
}

/** "1 credit", "3 credits" */
export function creditsText(credits: number): string {
  return credits === 1 ? "1 credit" : `${credits} credits`;
}

/** "850 ms", "4.2 s", "1 min 5 s" */
export function durationText(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || !Number.isFinite(ms) || ms < 0) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds < 10 ? seconds.toFixed(1) : Math.round(seconds)} s`;
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds - minutes * 60);
  return rest ? `${minutes} min ${rest} s` : `${minutes} min`;
}

/** How long a run took, from its start (or creation) to its end. */
export function runDuration(run: {
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
}): number | null {
  if (!run.completed_at) return null;
  const start = new Date(run.started_at ?? run.created_at).getTime();
  const end = new Date(run.completed_at).getTime();
  return Number.isFinite(start) && Number.isFinite(end) ? Math.max(0, end - start) : null;
}

/** "8 s", "1 min 5 s": whole seconds, at least one. */
export function secondsText(ms: number): string {
  const seconds = Math.max(1, Math.round(ms / 1000));
  if (seconds < 60) return `${seconds} s`;
  const minutes = Math.floor(seconds / 60);
  const rest = seconds - minutes * 60;
  return rest ? `${minutes} min ${rest} s` : `${minutes} min`;
}

/** How long a run worked, only when it has both a start and an end. */
export function workedFor(run: { started_at?: string | null; completed_at?: string | null }): string | null {
  if (!run.started_at || !run.completed_at) return null;
  const ms = new Date(run.completed_at).getTime() - new Date(run.started_at).getTime();
  return Number.isFinite(ms) && ms >= 0 ? secondsText(ms) : null;
}

/** A queued run waiting longer than this says so instead of "Starting". */
export const WAITING_AFTER_MS = 20_000;

/** The Ctrl or ⌘ key's name for the shortcut hint. */
export function modifierKey(platform: string | undefined): "⌘" | "Ctrl" {
  return platform && /mac|iphone|ipad/i.test(platform) ? "⌘" : "Ctrl";
}
