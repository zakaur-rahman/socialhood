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

  mediaAsset(wid: string, filename = "e2e-post.jpg"): Promise<{ id: string; secure_url: string }> {
    return this.seed("POST", `/workspaces/${wid}/media-assets`, { filename });
  }

  // ---------------------------------------------------------------- the app's own endpoints

  connectSandbox(wid: string): Promise<SandboxAccount> {
    return this.call<SandboxAccount>("POST", `/v1/w/${wid}/dev/sandbox/accounts`);
  }

  /** A DM or comment from a customer, through the same intake as a real webhook. */
  inbound(
    wid: string,
    event: { accountId: string; kind: "dm" | "comment"; text: string; fromId?: string; fromUsername?: string },
  ): Promise<{ stored: number }> {
    return this.call("POST", `/v1/w/${wid}/dev/sandbox/inbound`, {
      account_id: event.accountId,
      kind: event.kind,
      text: event.text,
      from_id: event.fromId,
      from_username: event.fromUsername,
    });
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

  get proProduct(): string {
    return this.stack.E2E_DODO_PRO_PRODUCT;
  }
}
