/**
 * Test helpers: the real API client and query code against a fake fetch, and inbox fixtures.
 * Handlers match "METHOD /path" with :params, e.g. "GET /v1/w/:wid/conversations".
 */
import type { QueryClient } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";

import { UpgradeDialog } from "@/components/billing/UpgradeDialog";
import { TooltipProvider } from "@/components/ui/tooltip";
import { makeApi } from "@/lib/api/client";
import { ApiClientProvider, makeQueryClient } from "@/lib/api/provider";
import type {
  AiSettings,
  Automation,
  AutomationTemplate,
  BillingState,
  Conversation,
  ConversationListItem,
  KnowledgeGap,
  KnowledgeSource,
  Message,
  MessageAnalysis,
  MetricComparison,
  PostComment,
  PostComparison,
  PostDetail,
  PostPerformance,
  PlanList,
  PlanOffer,
  PostSummary,
  SocialAccount,
  Suggestion,
  WorkspaceSummary,
} from "@/lib/api/types";
import { WorkspaceProvider } from "@/lib/workspace";

export type Call = { method: string; path: string; url: URL; headers: Headers; body: unknown };
type Handler = (call: Call, params: Record<string, string>) => Response | Promise<Response>;

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

export function problem(
  status: number,
  code: string,
  detail?: string,
  extra: { entitlement?: string; limit?: number | null } = {},
): Response {
  return new Response(JSON.stringify({ type: "about:blank", title: code, status, code, detail, ...extra }), {
    status,
    headers: { "Content-Type": "application/problem+json" },
  });
}

export function noContent(): Response {
  return new Response(null, { status: 204 });
}

/** 202 with no body: the work continues in the background (regenerate, summary refresh). */
export function accepted(): Response {
  return new Response(null, { status: 202 });
}

export function fakeApi(handlers: Record<string, Handler>) {
  const calls: Call[] = [];
  const routes = Object.entries(handlers).map(([pattern, handler]) => {
    const [method, path] = pattern.split(" ");
    const names: string[] = [];
    const regex = new RegExp(
      `^${path.replace(/:([a-z_]+)/g, (_, name: string) => {
        names.push(name);
        return "([^/]+)";
      })}$`,
    );
    return { method, regex, names, handler };
  });
  const fetch = async (request: Request): Promise<Response> => {
    const url = new URL(request.url);
    const text = request.method === "GET" ? "" : await request.text();
    const call: Call = {
      method: request.method,
      path: url.pathname,
      url,
      headers: request.headers,
      body: text ? JSON.parse(text) : undefined,
    };
    calls.push(call);
    for (const route of routes) {
      if (route.method !== request.method) continue;
      const match = route.regex.exec(url.pathname);
      if (!match) continue;
      const params = Object.fromEntries(route.names.map((name, i) => [name, decodeURIComponent(match[i + 1])]));
      return route.handler(call, params);
    }
    return problem(404, "not_found", `No fake for ${request.method} ${url.pathname}`);
  };
  const api = makeApi(async () => "test-token", { baseUrl: "http://api.test", fetch });
  return { api, calls };
}

export const workspace: WorkspaceSummary = {
  id: "w1",
  name: "Maple Bakery",
  slug: "maple",
  plan: "pro",
  role: "owner",
  timezone: "Asia/Kolkata",
};

export function renderWithApi(
  ui: ReactElement,
  {
    handlers = {},
    queryClient = makeQueryClient(),
    ws = workspace,
    upgradeDialog = false,
  }: {
    handlers?: Record<string, Handler>;
    queryClient?: QueryClient;
    ws?: WorkspaceSummary;
    /** Render the app's upgrade dialog, which every 402 opens (AppShell renders it in the app). */
    upgradeDialog?: boolean;
  } = {},
) {
  queryClient.setDefaultOptions({ queries: { retry: false, staleTime: Infinity, refetchOnWindowFocus: false } });
  const { api, calls } = fakeApi(handlers);
  const wrap = (node: ReactNode) => (
    <ApiClientProvider api={api} queryClient={queryClient}>
      <WorkspaceProvider value={ws}>
        <TooltipProvider>
          {node}
          {upgradeDialog ? <UpgradeDialog /> : null}
        </TooltipProvider>
      </WorkspaceProvider>
    </ApiClientProvider>
  );
  const result = render(wrap(ui));
  return { ...result, calls, queryClient, rerender: (next: ReactElement) => result.rerender(wrap(next)) };
}

// ---- fixtures

export function account(overrides: Partial<SocialAccount> = {}): SocialAccount {
  return {
    id: "a1",
    platform: "instagram",
    display_name: "Maple Bakery",
    username: "maple.bakery",
    profile_picture_url: null,
    phone_number: null,
    status: "active",
    last_error: null,
    ai_mode: "suggest",
    ai_analysis_enabled: true,
    auto_hide_spam: false,
    connected_at: "2026-09-20T10:00:00Z",
    token_expires_at: null,
    capabilities: ["dm_send", "dm_attachments"],
    sandbox: false,
    deleting: false,
    ...overrides,
  };
}

export function listItem(overrides: Partial<ConversationListItem> = {}): ConversationListItem {
  return {
    id: "c1",
    platform: "instagram",
    social_account_id: "a1",
    contact: { id: "p1", display_name: "Priya Nair", username: "priya.styles", profile_picture_url: null },
    status: "open",
    last_message_at: "2026-09-28T11:55:00Z",
    last_message_preview: "Do you ship to Dubai?",
    last_message_direction: "inbound",
    last_message_source: "customer",
    last_message_kind: "text",
    unread_count: 0,
    awaiting_reply: true,
    needs_human: false,
    needs_human_reason: null,
    signal: null,
    reply_window_closes_at: "2026-09-29T11:55:00Z",
    lead_score: null,
    ...overrides,
  };
}

export function conversation(overrides: Partial<Conversation> = {}): Conversation {
  const base = listItem();
  return {
    ...base,
    contact: {
      ...base.contact,
      first_seen_at: "2026-09-27T09:00:00Z",
      platform_user_id: "17841400000000000",
    },
    reply_window: { state: "open", closes_at: "2026-09-29T11:55:00Z" },
    ai: { effective_mode: "suggest", override: null, paused_until: null },
    latest_analysis: null,
    pending_suggestion: null,
    summary: null,
    social_account: { id: "a1", username: "maple.bakery", display_name: "Maple Bakery", status: "active" },
    scheduled_count: 0,
    ...overrides,
  };
}

let messageSeq = 0;

export function message(overrides: Partial<Message> = {}): Message {
  messageSeq += 1;
  return {
    id: `m${messageSeq}`,
    conversation_id: "c1",
    client_id: null,
    direction: "inbound",
    source: "customer",
    kind: "text",
    text: "Hello",
    attachments: [],
    template: null,
    status: "received",
    error: null,
    occurred_at: "2026-09-28T11:55:00Z",
    sent_at: null,
    delivered_at: null,
    read_at: null,
    sent_by: null,
    automation: null,
    suggestion_id: null,
    human_agent_tag: false,
    reactions: [],
    ...overrides,
  };
}

// ---- AI and knowledge (P5)

export function analysis(overrides: Partial<MessageAnalysis> = {}): MessageAnalysis {
  return {
    id: "an1",
    message_id: "m1",
    intent: "shipping",
    sentiment: "positive",
    sentiment_score: 0.4,
    priority: "medium",
    lead_score: 72,
    language: "en",
    topics: ["shipping to uae"],
    needs_reply: true,
    needs_human: false,
    needs_human_reason: null,
    corrected: false,
    created_at: "2026-09-28T11:55:05Z",
    ...overrides,
  };
}

export function suggestion(overrides: Partial<Suggestion> = {}): Suggestion {
  return {
    id: "s1",
    conversation_id: "c1",
    message_id: "m1",
    status: "pending",
    can_answer: true,
    reply_text: "Yes, we ship to the UAE! Delivery to Dubai takes 5–7 business days.",
    missing_info: null,
    low_confidence: false,
    sources: [{ id: "k1", title: "Shipping policy" }],
    regenerations_left: 5,
    created_at: "2026-09-28T11:55:10Z",
    ...overrides,
  };
}

export function aiSettings(overrides: Partial<AiSettings> = {}): AiSettings {
  return {
    business_name: null,
    business_description: null,
    tone: "friendly",
    emoji_policy: "light",
    do_list: [],
    dont_list: [],
    escalation_phrases: [],
    sign_off: null,
    takeover_minutes: 120,
    updated_at: "2026-09-28T10:00:00Z",
    ...overrides,
  };
}

export function knowledgeSource(overrides: Partial<KnowledgeSource> = {}): KnowledgeSource {
  return {
    id: "ks1",
    type: "faq",
    title: "Do you ship to Dubai?",
    question: "Do you ship to Dubai?",
    body: "Yes, 5–7 business days.",
    url: null,
    file_asset_id: null,
    file_name: null,
    status: "ready",
    error: null,
    version: 1,
    char_count: 1240,
    chunk_count: 1,
    last_ingested_at: "2026-09-28T10:00:00Z",
    created_at: "2026-09-28T10:00:00Z",
    updated_at: "2026-09-28T10:00:00Z",
    ...overrides,
  };
}

export function knowledgeGap(overrides: Partial<KnowledgeGap> = {}): KnowledgeGap {
  return {
    id: "g1",
    topic: "shipping to uae",
    status: "open",
    occurrences: 14,
    first_seen_at: "2026-09-20T10:00:00Z",
    last_seen_at: "2026-09-28T10:00:00Z",
    examples: [
      {
        message_id: "m1",
        conversation_id: "c1",
        text: "Do you ship to Dubai?",
        occurred_at: "2026-09-28T10:00:00Z",
      },
    ],
    ...overrides,
  };
}

export function billingState(overrides: Partial<BillingState> = {}): BillingState {
  return {
    plan: "pro",
    status: "active",
    current_period_end: "2026-10-01T00:00:00Z",
    trial_ends_at: null,
    cancel_at_period_end: false,
    grace_until: null,
    trial_eligible: false,
    prices: [],
    entitlements: [{ key: "ai_modes", value: ["off", "suggest", "auto"] }],
    usage: [{ metric: "ai_credits", used: 120, limit: 5000, period_end: "2026-10-01" }],
    ...overrides,
  };
}

/** GET /v1/billing/plans (C-049): Free, Pro with its Dodo price and trial, Max not yet available. */
export function planList(overrides: { proPrice?: PlanOffer["price"] } = {}): PlanList {
  const ent = (plan: "free" | "pro" | "max") => [
    { key: "accounts_per_platform", value: { free: 1, pro: 3, max: 10 }[plan] },
    { key: "active_automations", value: { free: 3, pro: 50, max: null }[plan] },
    { key: "ai_modes", value: plan === "free" ? ["off", "suggest"] : ["off", "suggest", "auto"] },
    { key: "ai_credits_monthly", value: { free: 200, pro: 5000, max: 25000 }[plan] },
    { key: "knowledge_characters", value: { free: 200_000, pro: 5_000_000, max: 50_000_000 }[plan] },
    { key: "scheduled_posts_monthly", value: { free: 10, pro: 300, max: null }[plan] },
  ];
  return {
    items: [
      { plan: "free", available: true, entitlements: ent("free"), price: null, trial_days: 0 },
      {
        plan: "pro",
        available: true,
        entitlements: ent("pro"),
        price: "proPrice" in overrides ? overrides.proPrice : { plan: "pro", amount_minor: 99_900, currency: "INR", interval: "month" },
        trial_days: 7,
      },
      { plan: "max", available: false, entitlements: ent("max"), price: null, trial_days: 0 },
    ],
  };
}

// ---- automations (P4)

export function automation(overrides: Partial<Automation> = {}): Automation {
  return {
    id: "au1",
    name: "Comment LINK, DM the link",
    status: "draft",
    display_status: "draft",
    social_account_id: "a1",
    trigger: "comment_keyword",
    keywords: ["link"],
    match_mode: "word",
    action: "send_message",
    message_text: "Hi {first_name|there}! Here's the link.",
    message_buttons: [{ title: "Shop now", url: "https://maple.example/shop" }],
    message_media_asset_id: null,
    message_media_url: null,
    ai_instructions: null,
    public_reply_texts: ["Sent you a DM!"],
    post_scope: "all",
    posts: [],
    cooldown_hours: 24,
    starts_at: null,
    ends_at: null,
    surge_order: "oldest_first",
    confirm_first: false,
    opening_text: null,
    opening_button: null,
    follow_nudge: false,
    follow_nudge_text: null,
    priority: 1,
    template_key: null,
    activated_at: null,
    paused_at: null,
    last_run_at: null,
    created_at: "2026-09-20T10:00:00Z",
    updated_at: "2026-09-20T10:00:00Z",
    stats: { runs_7d: 0, daily_7d: [0, 0, 0, 0, 0, 0, 0], last_run_at: null },
    queue: { waiting: 0, eta_minutes: null, order: "oldest_first" },
    missing_for_activation: [],
    overlaps: [],
    ...overrides,
  };
}

export function template(overrides: Partial<AutomationTemplate> = {}): AutomationTemplate {
  return {
    key: "link_to_commenters",
    name: "Send a link to commenters",
    outcome: "Send your link to everyone who comments LINK",
    category: "grow",
    icon: "link",
    trigger: "comment_keyword",
    action: "send_message",
    requires_paid_plan: false,
    ...overrides,
  };
}

// ---- comments and post analytics (P6)

export function post(overrides: Partial<PostSummary> = {}): PostSummary {
  return {
    id: "po1",
    social_account_id: "a1",
    platform_media_id: "17900000000000001",
    media_type: "image",
    caption: "New linen dresses are here",
    media_url: "https://scontent.cdninstagram.com/po1.jpg",
    thumbnail_url: null,
    permalink: "https://www.instagram.com/p/po1/",
    posted_at: "2026-09-27T12:00:00Z",
    like_count: 1204,
    comments_count: 212,
    stats: { total: 12, analysed: 12, positive: 7, neutral: 3, negative: 1, spam: 1 },
    ...overrides,
  };
}

export function postDetail(overrides: Partial<PostDetail> = {}): PostDetail {
  return {
    ...post(),
    summary: "People love the colours and ask about sizes. A few want shipping to the UAE.",
    summary_updated_at: "2026-09-28T10:00:00Z",
    topics: [
      { label: "sizes", count: 5, positive: 3, neutral: 2, negative: 0 },
      { label: "shipping to uae", count: 3, positive: 1, neutral: 1, negative: 1 },
    ],
    ...overrides,
  };
}

let commentSeq = 0;

export function comment(overrides: Partial<PostComment> = {}): PostComment {
  commentSeq += 1;
  return {
    id: `cm${commentSeq}`,
    post_id: "po1",
    social_account_id: "a1",
    contact_id: "p1",
    platform_comment_id: `1790000000000${commentSeq}`,
    parent_platform_comment_id: null,
    author_username: "priya.styles",
    author_profile_picture_url: null,
    text: "What sizes do you have?",
    like_count: 0,
    hidden: false,
    commented_at: "2026-09-28T11:00:00Z",
    deleted_at: null,
    analysis_status: "done",
    analysis: { sentiment: "positive", sentiment_score: 0.6, intent: "product_inquiry", is_spam: false, topic: "sizes" },
    public_reply: null,
    private_reply: null,
    ...overrides,
  };
}

export function performance(overrides: Partial<PostPerformance> = {}): PostPerformance {
  return {
    post_id: "po1",
    media_type: "image",
    posted_at: "2026-09-27T12:00:00Z",
    requested_age: null,
    age: "24h",
    captured_at: "2026-09-28T12:05:00Z",
    insights_granted: true,
    insights_final: false,
    metrics: {
      reach: 1240,
      views: 3100,
      likes: 180,
      comments: 12,
      shares: 9,
      saves: 21,
      engagement_rate: 17.8,
    },
    ...overrides,
  };
}

export function metricRow(overrides: Partial<MetricComparison> = {}): MetricComparison {
  return {
    metric: "reach",
    value: 1240,
    baseline_median: 1050,
    baseline_mean: 1100,
    diff_pct: 18.1,
    z_score: 0.6,
    sample_size: 8,
    ...overrides,
  };
}

export function comparison(overrides: Partial<PostComparison> = {}): PostComparison {
  return {
    post: performance(),
    age: "24h",
    baseline: { kind: "previous", n: 10, since: null, until: null, same_format: true, post_ids: [] },
    baseline_size: 8,
    enough_history: true,
    metrics: [
      metricRow(),
      metricRow({ metric: "views", value: 3100, baseline_median: 3400, baseline_mean: 3500, diff_pct: -8.8 }),
      metricRow({ metric: "likes", value: 180, baseline_median: 180, baseline_mean: 170, diff_pct: 0 }),
      metricRow({ metric: "comments", value: 12, baseline_median: 9, baseline_mean: 10, diff_pct: 33.3 }),
      metricRow({ metric: "shares", value: 9, baseline_median: 0, baseline_mean: 1, diff_pct: null, sample_size: 6 }),
      metricRow({ metric: "saves", value: 21, baseline_median: 15, baseline_mean: 16, diff_pct: 40 }),
      metricRow({ metric: "engagement_rate", value: 17.8, baseline_median: 15.2, baseline_mean: 15, diff_pct: 17.1 }),
    ],
    ...overrides,
  };
}
