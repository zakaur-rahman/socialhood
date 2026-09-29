/**
 * Test helpers: the real API client and query code against a fake fetch, and inbox fixtures.
 * Handlers match "METHOD /path" with :params, e.g. "GET /v1/w/:wid/conversations".
 */
import type { QueryClient } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";

import { TooltipProvider } from "@/components/ui/tooltip";
import { makeApi } from "@/lib/api/client";
import { ApiClientProvider, makeQueryClient } from "@/lib/api/provider";
import type {
  Automation,
  AutomationTemplate,
  Conversation,
  ConversationListItem,
  Message,
  SocialAccount,
  WorkspaceSummary,
} from "@/lib/api/types";
import { WorkspaceProvider } from "@/lib/workspace";

export type Call = { method: string; path: string; url: URL; headers: Headers; body: unknown };
type Handler = (call: Call, params: Record<string, string>) => Response | Promise<Response>;

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

export function problem(status: number, code: string, detail?: string): Response {
  return new Response(JSON.stringify({ type: "about:blank", title: code, status, code, detail }), {
    status,
    headers: { "Content-Type": "application/problem+json" },
  });
}

export function noContent(): Response {
  return new Response(null, { status: 204 });
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
  }: { handlers?: Record<string, Handler>; queryClient?: QueryClient; ws?: WorkspaceSummary } = {},
) {
  queryClient.setDefaultOptions({ queries: { retry: false, staleTime: Infinity, refetchOnWindowFocus: false } });
  const { api, calls } = fakeApi(handlers);
  const wrap = (node: ReactNode) => (
    <ApiClientProvider api={api} queryClient={queryClient}>
      <WorkspaceProvider value={ws}>
        <TooltipProvider>{node}</TooltipProvider>
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
