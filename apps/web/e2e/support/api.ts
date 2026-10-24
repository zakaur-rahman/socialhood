import { createHmac, randomUUID } from "node:crypto";

import { requireStack } from "./env";

export type Workspace = { id: string; slug: string; name: string };
export type SandboxAccount = { id: string; username: string | null; display_name: string | null };

export class ApiFailure extends Error {
  constructor(
    readonly status: number,
    readonly body: string,
    what: string,
  ) {
    super(`${what}: HTTP ${status} ${body.slice(0, 500)}`);
  }
}

/**
 * The API as the signed-in e2e user, for setup the UI isn't under test for: seeding a workspace,
 * connecting a sandbox account, injecting inbound events (POST …/dev/sandbox/inbound, TR-PL-07)
 * and Dodo's signed webhook. ``token`` returns a fresh Clerk session token.
 */
export class Api {
  private readonly stack = requireStack();

  constructor(private readonly token: () => Promise<string>) {}

  async call<T>(method: string, path: string, body?: unknown, extra: Record<string, string> = {}): Promise<T> {
    const headers: Record<string, string> = { Authorization: `Bearer ${await this.token()}`, ...extra };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    const response = await fetch(`${this.stack.E2E_API_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const text = await response.text();
    if (!response.ok) throw new ApiFailure(response.status, text, `${method} ${path}`);
    return (text ? JSON.parse(text) : undefined) as T;
  }

  private seed<T>(method: string, path: string, body?: unknown): Promise<T> {
    return this.call<T>(method, `/__e2e${path}`, body, { "X-E2E-Token": this.stack.E2E_SEED_TOKEN });
  }

  // ---------------------------------------------------------------- seed routes (apps/api/scripts/e2e/api.py)

  newWorkspace(name: string): Promise<Workspace> {
    return this.seed<Workspace>("POST", "/workspaces", { name });
  }

  /** A signed-up user's workspaces and row (F-01 cleans up after itself). */
  deleteUserData(clerkUserId: string): Promise<void> {
    return this.seed<void>("DELETE", `/users/${clerkUserId}`);
  }

  /** GR-19: the workspace on a plan, without a checkout. */
  setPlan(wid: string, plan: "free" | "pro" | "max"): Promise<void> {
    return this.seed<void>("POST", `/workspaces/${wid}/plan`, { plan });
  }

  /** GR-27: the header and rows the fake Google holds for a sheet. */
  googleSheet(sheetId: string): Promise<{ header: string[]; rows: string[][] }> {
    return this.seed("GET", `/google-sheets/${sheetId}`);
  }

  /** GR-27: delete the sheet as the person would in Google Drive. */
  deleteGoogleSheet(sheetId: string): Promise<void> {
    return this.seed<void>("POST", `/google-sheets/${sheetId}/delete`);
  }

  /**
   * GR-25, GR-26: a call to the public API with an API key (not the Clerk session). Resolves with
   * the status and parsed body instead of throwing, so a spec can check a 403 or a 401.
   */
  async publicCall<T = unknown>(
    key: string,
    method: string,
    path: string,
    body?: unknown,
    extra: Record<string, string> = {},
  ): Promise<{ status: number; body: T }> {
    const headers: Record<string, string> = { Authorization: `Bearer ${key}`, ...extra };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    const response = await fetch(`${this.stack.E2E_API_URL}/public/v1${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const text = await response.text();
    return { status: response.status, body: (text ? JSON.parse(text) : undefined) as T };
  }

  mediaAsset(wid: string, filename = "e2e-post.jpg"): Promise<{ id: string; secure_url: string }> {
    return this.seed("POST", `/workspaces/${wid}/media-assets`, { filename });
  }

  /**
   * GR-38: a finished Ask run of the signed-in owner (the fake model calls no tools). With `visual`
   * it seeds the account's metrics for the last `days` complete days and the `days` before them,
   * and the run holds the metric_comparison the real service and builder make from them.
   */
  agentRun(
    wid: string,
    run: { request: string; answer: string; accountId?: string; visual?: boolean; days?: number },
  ): Promise<{ id: string; thread_id: string }> {
    return this.seed("POST", `/workspaces/${wid}/agent-runs`, {
      request: run.request,
      answer: run.answer,
      account_id: run.accountId,
      visual: run.visual ?? false,
      days: run.days ?? 14,
    });
  }

  /**
   * GR-36: a finished Ask run whose draft step called propose_flow or propose_segment through the
   * real tool and gateway (the fake model calls no tools): a pending approval and its card. A
   * segment's `tag` must already exist in the workspace.
   */
  agentProposal(
    wid: string,
    proposal: { request: string; kind: "flow" | "segment"; name: string; keyword?: string; tag?: string },
  ): Promise<{ run_id: string; thread_id: string; approval_id: string }> {
    return this.seed("POST", `/workspaces/${wid}/agent-proposals`, proposal);
  }

  // ---------------------------------------------------------------- the app's own endpoints

  /** A sandbox Instagram account, a Facebook Page (GR-29) or a WhatsApp number with approved templates (GR-23). */
  connectSandbox(wid: string, platform: "instagram" | "facebook" | "whatsapp" = "instagram"): Promise<SandboxAccount> {
    return this.call<SandboxAccount>(
      "POST",
      `/v1/w/${wid}/dev/sandbox/accounts`,
      platform === "instagram" ? undefined : { platform },
    );
  }

  /**
   * A DM or comment from a customer, through the same intake as a real webhook. GR-01 adds a
   * referral without a message (an entry link opened, an ad tapped), a postback, an opt-in and a
   * Live comment; a DM may carry an ad referral.
   */
  inbound(
    wid: string,
    event: {
      accountId: string;
      kind:
        | "dm"
        | "comment"
        | "live_comment"
        | "referral"
        | "postback"
        | "optin"
        | "story_reply"
        | "story_like"
        | "story_mention"
        // GR-23, a sandbox WhatsApp number: a delivery status for the last message sent to
        // `fromId`, and a number's quality or tier change.
        | "status"
        | "quality"
        // GR-33, a sandbox WhatsApp number: a customer's cart (retailer ids are variant or product ids).
        | "order";
      deliveryStatus?: "sent" | "delivered" | "read" | "failed";
      cart?: { retailerId: string; quantity: number; price?: string }[];
      errorCode?: number;
      errorText?: string;
      qualityEvent?: "ONBOARDING" | "UPGRADE" | "DOWNGRADE" | "FLAGGED" | "UNFLAGGED";
      tier?: string;
      /** GR-10: how old a comment or Live comment is when it arrives, in seconds. */
      ageSeconds?: number;
      text?: string;
      fromId?: string;
      fromUsername?: string;
      referralSource?: "ad" | "link";
      ref?: string;
      adId?: string;
      adTitle?: string;
      postbackPayload?: string;
      quickReplyPayload?: string;
      /** GR-06: the story a story reply or like answers (the sandbox lists `<account>_story_0`, `_1`). */
      storyId?: string;
    },
  ): Promise<{ stored: number }> {
    return this.call("POST", `/v1/w/${wid}/dev/sandbox/inbound`, {
      account_id: event.accountId,
      kind: event.kind,
      text: event.text,
      from_id: event.fromId,
      from_username: event.fromUsername,
      referral_source: event.referralSource,
      ref: event.ref,
      ad_id: event.adId,
      ad_title: event.adTitle,
      postback_payload: event.postbackPayload,
      quick_reply_payload: event.quickReplyPayload,
      story_id: event.storyId,
      age_seconds: event.ageSeconds,
      delivery_status: event.deliveryStatus,
      error_code: event.errorCode,
      error_text: event.errorText,
      quality_event: event.qualityEvent,
      tier: event.tier,
      cart: event.cart?.map((item) => ({ retailer_id: item.retailerId, quantity: item.quantity, price: item.price })),
    });
  }

  /** GR-06, GR-07: an active automation on a story trigger (no keywords answers every event). */
  async storyAutomation(
    wid: string,
    accountId: string,
    trigger: "story_reply" | "story_mention",
    values: { keywords?: string[]; messageText: string; storyIds?: string[]; heart?: boolean },
  ): Promise<{ id: string }> {
    const name = `Story ${trigger} ${Date.now().toString(36)}`;
    const draft = await this.call<{ id: string }>("POST", `/v1/w/${wid}/automations`, {
      name,
      social_account_id: accountId,
    });
    await this.call("PUT", `/v1/w/${wid}/automations/${draft.id}`, {
      name,
      social_account_id: accountId,
      trigger,
      keywords: values.keywords ?? [],
      match_mode: "word",
      action: "send_message",
      message_text: values.messageText,
      post_scope: values.storyIds?.length ? "selected" : "all",
      story_ids: values.storyIds ?? [],
      story_heart: values.heart ?? false,
    });
    await this.call("POST", `/v1/w/${wid}/automations/${draft.id}/activate`);
    return draft;
  }

  /** GR-08, GR-09: an active entry link or ad click automation (no keywords; ``adIds`` limits the ads). */
  async entryAutomation(
    wid: string,
    accountId: string,
    trigger: "entry_link" | "ad_click",
    values: { messageText: string; adIds?: string[] },
  ): Promise<{ id: string }> {
    const name = `Entry ${trigger} ${Date.now().toString(36)}`;
    const draft = await this.call<{ id: string }>("POST", `/v1/w/${wid}/automations`, {
      name,
      social_account_id: accountId,
    });
    await this.call("PUT", `/v1/w/${wid}/automations/${draft.id}`, {
      name,
      social_account_id: accountId,
      trigger,
      keywords: [],
      match_mode: "word",
      action: "send_message",
      message_text: values.messageText,
      post_scope: values.adIds?.length ? "selected" : "all",
      ad_ids: values.adIds ?? [],
    });
    await this.call("POST", `/v1/w/${wid}/automations/${draft.id}/activate`);
    return draft;
  }

  /** GR-29: an active comment keyword automation: a public reply and a private message. */
  async commentAutomation(
    wid: string,
    accountId: string,
    keyword: string,
    values: { messageText: string; publicReplies: string[] },
  ): Promise<{ id: string }> {
    const name = `Comment ${keyword}`;
    const draft = await this.call<{ id: string }>("POST", `/v1/w/${wid}/automations`, {
      name,
      social_account_id: accountId,
    });
    await this.call("PUT", `/v1/w/${wid}/automations/${draft.id}`, {
      name,
      social_account_id: accountId,
      trigger: "comment_keyword",
      keywords: [keyword],
      match_mode: "word",
      action: "send_message",
      message_text: values.messageText,
      public_reply_texts: values.publicReplies,
      post_scope: "all",
      confirm_first: false,
    });
    await this.call("POST", `/v1/w/${wid}/automations/${draft.id}/activate`);
    return draft;
  }

  /** GR-10: an active comment keyword automation on Lives (``surface`` "live"), no post scope. */
  async liveAutomation(
    wid: string,
    accountId: string,
    keyword: string,
    messageText: string,
  ): Promise<{ id: string }> {
    const name = `Live ${keyword}`;
    const draft = await this.call<{ id: string }>("POST", `/v1/w/${wid}/automations`, {
      name,
      social_account_id: accountId,
    });
    await this.call("PUT", `/v1/w/${wid}/automations/${draft.id}`, {
      name,
      social_account_id: accountId,
      trigger: "comment_keyword",
      keywords: [keyword],
      match_mode: "word",
      action: "send_message",
      message_text: messageText,
      comment_surface: "live",
      post_scope: "all",
      confirm_first: false,
    });
    await this.call("POST", `/v1/w/${wid}/automations/${draft.id}/activate`);
    return draft;
  }

  /** GR-08: an entry link on the account that starts ``automationId``. */
  entryLink(
    wid: string,
    accountId: string,
    values: { name: string; automationId?: string; code?: string },
  ): Promise<{ id: string; code: string; url: string }> {
    return this.call("POST", `/v1/w/${wid}/entry-links`, {
      social_account_id: accountId,
      name: values.name,
      automation_id: values.automationId,
      code: values.code,
    });
  }

  /** GR-11: an active automation on the conversation starter trigger (a tap starts it). */
  async iceBreakerAutomation(wid: string, accountId: string, messageText: string): Promise<{ id: string }> {
    const name = `Starter ${Date.now().toString(36)}`;
    const draft = await this.call<{ id: string }>("POST", `/v1/w/${wid}/automations`, {
      name,
      social_account_id: accountId,
    });
    await this.call("PUT", `/v1/w/${wid}/automations/${draft.id}`, {
      name,
      social_account_id: accountId,
      trigger: "ice_breaker",
      keywords: [],
      match_mode: "word",
      action: "send_message",
      message_text: messageText,
    });
    await this.call("POST", `/v1/w/${wid}/automations/${draft.id}/activate`);
    return draft;
  }

  /** GR-12: an active welcome (first_message) or default reply (default_reply) automation. */
  async fallbackAutomation(
    wid: string,
    accountId: string,
    trigger: "first_message" | "default_reply",
    messageText: string,
  ): Promise<{ id: string }> {
    const name = `Fallback ${trigger} ${Date.now().toString(36)}`;
    const draft = await this.call<{ id: string }>("POST", `/v1/w/${wid}/automations`, {
      name,
      social_account_id: accountId,
    });
    await this.call("PUT", `/v1/w/${wid}/automations/${draft.id}`, {
      name,
      social_account_id: accountId,
      trigger,
      keywords: [],
      match_mode: "word",
      action: "send_message",
      message_text: messageText,
      post_scope: "all",
    });
    await this.call("POST", `/v1/w/${wid}/automations/${draft.id}/activate`);
    return draft;
  }

  /** GR-21: a saved reply (``shortcut`` is typed after / in the composer). */
  savedReply(
    wid: string,
    values: { title: string; shortcut: string; body: string },
  ): Promise<{ id: string; shortcut: string }> {
    return this.call("POST", `/v1/w/${wid}/saved-replies`, values);
  }

  /** GR-22: the workspace's time zone, so the hours below mean the same wall clock as the test. */
  async setTimezone(wid: string, timezone: string): Promise<void> {
    await this.call("PATCH", `/v1/w/${wid}`, { timezone });
  }

  /**
   * GR-22: the workspace's business hours. ``open`` is one range for every day ("00:00" to "24:00"
   * is always open); ``away`` turns the away message on.
   */
  async setHours(
    wid: string,
    values: { open: { start: string; end: string }; away?: string; autoMode?: "always" | "out_of_hours" },
  ): Promise<void> {
    await this.call("PUT", `/v1/w/${wid}/business-hours`, {
      enabled: true,
      days: [0, 1, 2, 3, 4, 5, 6].map((day) => ({ day, ranges: [values.open] })),
      away_enabled: Boolean(values.away),
      away_message: values.away ?? null,
      auto_mode: values.autoMode ?? "always",
    });
  }

  /** GR-12: the account's AI mode (the default reply answers only while it is off). */
  async setAiMode(wid: string, accountId: string, mode: "off" | "suggest" | "auto"): Promise<void> {
    await this.call("PATCH", `/v1/w/${wid}/social-accounts/${accountId}`, { ai_mode: mode });
  }

  /** GR-03: an active DM keyword automation saved as ``flow`` (PUT …/flow). */
  async flowAutomation(wid: string, accountId: string, keyword: string, flow: unknown): Promise<{ id: string }> {
    const draft = await this.call<{ id: string }>("POST", `/v1/w/${wid}/automations`, {
      name: `Flow for ${keyword}`,
      social_account_id: accountId,
    });
    await this.call("PUT", `/v1/w/${wid}/automations/${draft.id}`, {
      name: `Flow for ${keyword}`,
      social_account_id: accountId,
      trigger: "dm_keyword",
      keywords: [keyword],
      match_mode: "word",
    });
    await this.call("PUT", `/v1/w/${wid}/automations/${draft.id}/flow`, flow);
    await this.call("POST", `/v1/w/${wid}/automations/${draft.id}/activate`);
    return draft;
  }

  /** A draft automation made active through the API (setup for the plan limit in F-15). */
  async activeAutomation(wid: string, accountId: string, keyword: string): Promise<{ id: string }> {
    const draft = await this.call<{ id: string }>("POST", `/v1/w/${wid}/automations`, {
      name: `Reply to ${keyword}`,
      social_account_id: accountId,
    });
    await this.call("PUT", `/v1/w/${wid}/automations/${draft.id}`, {
      name: `Reply to ${keyword}`,
      social_account_id: accountId,
      trigger: "dm_keyword",
      keywords: [keyword],
      match_mode: "word",
      action: "send_message",
      message_text: `Hi {first_name|there}! Thanks for asking about ${keyword}.`,
    });
    await this.call("POST", `/v1/w/${wid}/automations/${draft.id}/activate`);
    return draft;
  }

  /**
   * Dodo's webhook as Dodo sends it (Standard Webhooks): signed with DODO_WEBHOOK_SECRET, the
   * value the launcher generated for the API.
   */
  async dodoWebhook(payload: Record<string, unknown>): Promise<number> {
    const secret = this.stack.E2E_DODO_WEBHOOK_SECRET;
    if (!secret.startsWith("whsec_")) throw new Error("E2E_DODO_WEBHOOK_SECRET is missing");
    const id = `msg_e2e_${randomUUID()}`;
    const timestamp = Math.floor(Date.now() / 1000).toString();
    const body = JSON.stringify(payload);
    const key = Buffer.from(secret.slice("whsec_".length), "base64");
    const signature = createHmac("sha256", key).update(`${id}.${timestamp}.${body}`).digest("base64");
    const response = await fetch(`${this.stack.E2E_API_URL}/webhooks/dodo`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "webhook-id": id,
        "webhook-timestamp": timestamp,
        "webhook-signature": `v1,${signature}`,
      },
      body,
    });
    return response.status;
  }

  /**
   * GR-31: a Shopify webhook as Shopify sends it. The API signs it with the app's secret (which
   * never leaves its environment: /__e2e/shopify/sign), and the suite posts it to /webhooks/shopify.
   */
  async shopifyWebhook(topic: string, shop: string, body: Record<string, unknown>): Promise<number> {
    const signed = await this.seed<{ raw: string; headers: Record<string, string> }>("POST", "/shopify/sign", {
      topic,
      shop,
      body,
      webhook_id: `e2e-${randomUUID()}`,
    });
    const response = await fetch(`${this.stack.E2E_API_URL}/webhooks/shopify`, {
      method: "POST",
      headers: signed.headers,
      body: signed.raw,
    });
    return response.status;
  }

  /**
   * GR-32: a Razorpay webhook as Razorpay sends it, signed with the webhook secret the suite typed
   * into the Payments card (hex HMAC-SHA256 of the raw body), posted to the workspace's address.
   */
  async razorpayWebhook(token: string, secret: string, eventId: string, body: Record<string, unknown>): Promise<number> {
    const raw = JSON.stringify(body);
    const response = await fetch(`${this.stack.E2E_API_URL}/webhooks/razorpay/${token}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Razorpay-Signature": createHmac("sha256", secret).update(raw).digest("hex"),
        "X-Razorpay-Event-Id": eventId,
      },
      body: raw,
    });
    return response.status;
  }

  get proProduct(): string {
    return this.stack.E2E_DODO_PRO_PRODUCT;
  }
}
