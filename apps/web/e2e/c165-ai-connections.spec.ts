import { createHash, randomBytes } from "node:crypto";

import { requireStack } from "./support/env";
import { expect, test } from "./support/fixtures";

/**
 * C-165 phase C: an AI app connects over OAuth. The test plays the AI app (MCP Inspector-like):
 * it registers with DCR, starts the authorization, and the signed-in member answers on the
 * consent page (/connect/authorize). The browser goes back to the app's loopback redirect, which
 * the test intercepts, the code is exchanged for tokens, and a tool call works on /mcp. Then
 * Settings › Connected AI apps lists it with its activity, and Disconnect stops it at once.
 * Plus the public setup guide, /developers/mcp.
 */
const REDIRECT = "http://127.0.0.1:43219/callback";

function pkce() {
  const verifier = randomBytes(48).toString("base64url");
  return { verifier, challenge: createHash("sha256").update(verifier).digest("base64url") };
}

async function mcp(token: string, method: string, params: Record<string, unknown> = {}) {
  const { E2E_API_URL } = requireStack();
  return fetch(`${E2E_API_URL}/mcp`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      Accept: "application/json, text/event-stream",
      "MCP-Protocol-Version": "2025-11-25",
    },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
  });
}

test.describe("C-165 AI app connections", () => {
  test("connect, consent, call a tool, see it in Settings, disconnect", async ({ page, workspace }) => {
    const { E2E_API_URL } = requireStack();
    const registered = await fetch(`${E2E_API_URL}/oauth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ client_name: "E2E Agent", redirect_uris: [REDIRECT], token_endpoint_auth_method: "none" }),
    });
    expect(registered.status).toBe(201);
    const { client_id: clientId } = (await registered.json()) as { client_id: string };

    const { verifier, challenge } = pkce();
    const state = randomBytes(8).toString("hex");
    const authorize = new URL(`${E2E_API_URL}/oauth/authorize`);
    for (const [key, value] of Object.entries({
      response_type: "code",
      client_id: clientId,
      redirect_uri: REDIRECT,
      code_challenge: challenge,
      code_challenge_method: "S256",
      state,
      scope: "posts:read conversations:read offline_access",
    })) {
      authorize.searchParams.set(key, value);
    }
    const started = await fetch(authorize, { redirect: "manual" });
    expect(started.status).toBe(302);
    const consent = new URL(started.headers.get("location") ?? "");
    expect(consent.pathname).toBe("/connect/authorize");

    // The app's loopback callback: answered by the test, which keeps the query.
    let callback: URL | null = null;
    await page.route(`${REDIRECT}**`, async (route) => {
      callback = new URL(route.request().url());
      await route.fulfill({ status: 200, contentType: "text/html", body: "<p>You can close this tab.</p>" });
    });

    await page.goto(`${consent.pathname}${consent.search}`);
    await expect(page.getByRole("heading", { name: "E2E Agent wants to connect to Amplychat" })).toBeVisible();
    await expect(page.getByRole("note")).toContainText("started the connection on this computer");
    await expect(page.getByText(/registered itself/)).toBeVisible();
    const picker = page.getByRole("group", { name: "Workspace" });
    await picker.getByRole("radio", { name: new RegExp(workspace.name) }).check();
    await expect(page.getByRole("checkbox", { name: "Publishing" })).toBeChecked();
    await page.getByRole("button", { name: "Allow" }).click();
    await expect.poll(() => callback?.searchParams.get("code") ?? null).not.toBeNull();
    const back = callback as unknown as URL;
    expect(back.searchParams.get("state")).toBe(state);
    expect(back.searchParams.get("iss")).toBeTruthy();

    const tokenResponse = await fetch(`${E2E_API_URL}/oauth/token`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        grant_type: "authorization_code",
        code: back.searchParams.get("code") ?? "",
        redirect_uri: REDIRECT,
        client_id: clientId,
        code_verifier: verifier,
      }),
    });
    expect(tokenResponse.status).toBe(200);
    const tokens = (await tokenResponse.json()) as { access_token: string; refresh_token: string };
    expect(tokens.access_token).toMatch(/^sho_/);
    const called = await mcp(tokens.access_token, "tools/call", { name: "get_workspace", arguments: {} });
    expect(called.status).toBe(200);
    const result = (await called.json()) as { result: { structuredContent: { workspace: { id: string } } } };
    expect(result.result.structuredContent.workspace.id).toBe(workspace.id);

    await page.unroute(`${REDIRECT}**`);
    await page.goto(`/w/${workspace.slug}/settings/ai-apps`);
    await expect(page.getByRole("heading", { name: "Connected AI apps", level: 1 })).toBeVisible();
    await expect(page.getByRole("radio", { name: /^Read and drafts/ })).toBeVisible();
    const row = page.getByTestId("ai-connection").filter({ hasText: "E2E Agent" });
    await expect(row).toContainText("get_workspace");
    await expect(row).toContainText("Read the inbox");
    await row.getByRole("button", { name: "Disconnect" }).click();
    await page.getByRole("alertdialog", { name: "Disconnect E2E Agent?" }).getByRole("button", { name: "Disconnect" }).click();
    await expect(page.getByText(/No AI apps are connected/)).toBeVisible();
    expect((await mcp(tokens.access_token, "tools/list")).status).toBe(401);
  });

  test("Cancel on the consent page sends access_denied back", async ({ page }) => {
    const { E2E_API_URL } = requireStack();
    const registered = await fetch(`${E2E_API_URL}/oauth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ client_name: "E2E Deny", redirect_uris: [REDIRECT], token_endpoint_auth_method: "none" }),
    });
    const { client_id: clientId } = (await registered.json()) as { client_id: string };
    const authorize = new URL(`${E2E_API_URL}/oauth/authorize`);
    authorize.search = new URLSearchParams({
      response_type: "code",
      client_id: clientId,
      redirect_uri: REDIRECT,
      code_challenge: pkce().challenge,
      code_challenge_method: "S256",
      state: "s1",
    }).toString();
    const consent = new URL((await fetch(authorize, { redirect: "manual" })).headers.get("location") ?? "");
    let callback: URL | null = null;
    await page.route(`${REDIRECT}**`, async (route) => {
      callback = new URL(route.request().url());
      await route.fulfill({ status: 200, contentType: "text/html", body: "<p>Denied.</p>" });
    });
    await page.goto(`${consent.pathname}${consent.search}`);
    await page.getByRole("button", { name: "Cancel" }).click();
    await expect.poll(() => callback?.searchParams.get("error") ?? null).toBe("access_denied");
    // Decided once: the page now says it has expired.
    await page.goto(`${consent.pathname}${consent.search}`);
    await expect(page.getByRole("heading", { name: "This request has expired" })).toBeVisible();
  });

  test("the public setup guide", async ({ page }) => {
    await page.goto("/developers/mcp");
    await expect(page.getByRole("heading", { level: 1, name: "Connect Amplychat to Claude, ChatGPT and Codex" })).toBeVisible();
    for (const name of ["Claude Code", "ChatGPT", "Codex"]) {
      await expect(page.getByRole("heading", { level: 3, name })).toBeVisible();
    }
    await expect(page.getByRole("table", { name: "What each plan includes for AI apps" })).toBeVisible();
    await expect(page.locator('script[type="application/ld+json"]').filter({ hasText: "FAQPage" })).toHaveCount(1);
    await expect(page.getByRole("link", { name: "Using an API key instead" }).first()).toHaveAttribute("href", "/developers/mcp/api-key");
  });

  test("the MCP product page and the API-key page", async ({ page }) => {
    await page.goto("/mcp");
    await expect(page.getByRole("heading", { level: 1, name: "Use Amplychat from Claude, ChatGPT and Codex" })).toBeVisible();
    await expect(page.getByRole("heading", { level: 3, name: "Other MCP apps" })).toBeVisible();
    await expect(page.getByRole("table", { name: "What each plan includes for AI apps" })).toBeVisible();
    await page.getByRole("link", { name: "Set it up" }).first().click();
    await expect(page).toHaveURL(/\/developers\/mcp$/);

    await page.goto("/developers/mcp/api-key");
    await expect(page.getByRole("heading", { level: 1, name: "Connect an AI app with an API key" })).toBeVisible();
    await expect(page.getByText("bearer_token_env_var", { exact: false }).first()).toBeVisible();
    await expect(page.locator('script[type="application/ld+json"]').filter({ hasText: "FAQPage" })).toHaveCount(1);
  });

  test("API keys are their own Settings section, not under Integrations", async ({ page, workspace }) => {
    await page.goto(`/w/${workspace.slug}/settings/api-keys`);
    await expect(page.getByRole("heading", { level: 1, name: "API keys" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Settings" }).getByRole("link", { name: "API keys" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Connect an AI app with a key" })).toHaveAttribute("href", /\/developers\/mcp\/api-key$/);
    await page.goto(`/w/${workspace.slug}/settings/integrations`);
    await expect(page.getByRole("heading", { level: 1, name: "Integrations" })).toBeVisible();
    await expect(page.getByTestId("api-key")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Create API key" })).toHaveCount(0);
  });
});
