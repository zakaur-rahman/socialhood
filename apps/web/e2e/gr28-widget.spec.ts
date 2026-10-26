import type { Page } from "@playwright/test";

import type { Api, Workspace } from "./support/api";
import { requireStack } from "./support/env";
import { expect, test, unique } from "./support/fixtures";

/**
 * GR-28 Website chat widget. A local test page (served by the test itself, so no file ships with the
 * app) embeds the widget with the one-line script from Settings. A visitor's chat arrives in the
 * inbox as "Website" with the AI's suggestion (the e2e worker's fake AI answers every question with
 * SUGGESTED), and the reply sent from the inbox reaches the widget without a reload. A page on a
 * site that is not on the allowed list gets no widget. The test page is on http://localhost, which
 * is on the list, because the API is on http too (a browser will not frame http inside https).
 */
const SUGGESTED = "Thanks for asking! Yes, it's in stock in every colour and ships this week.";
const PAGE_ORIGIN = "http://localhost:4010";
const OTHER_ORIGIN = "http://127.0.0.1:4011";

type WidgetSettings = { widget_id: string; allowed_domains: string[]; account_id: string };

async function setUp(api: Api, workspace: Workspace, settings: Record<string, unknown> = {}): Promise<WidgetSettings> {
  await api.call("GET", `/v1/w/${workspace.id}/widget`);
  return api.call<WidgetSettings>("PUT", `/v1/w/${workspace.id}/widget`, {
    allowed_domains: ["localhost"],
    ...settings,
  });
}

function shop(widgetId: string): string {
  const { E2E_API_URL } = requireStack();
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Maple test shop</title></head><body><main><h1>Maple test shop</h1><p>Linen shirts, scarves and more.</p>
<button type="button">A button on the page</button></main>
<script src="${E2E_API_URL}/widget.js" data-widget="${widgetId}" async></script></body></html>`;
}

async function serveShop(page: Page, origin: string, widgetId: string): Promise<void> {
  await page.route(`${origin}/**`, (route) =>
    route.fulfill({ status: 200, contentType: "text/html; charset=utf-8", body: shop(widgetId) }),
  );
}

function chatOn(page: Page) {
  const frame = page.frameLocator('iframe[title="Chat"]');
  return {
    frame,
    launcher: frame.getByRole("button", { name: /^Open chat/ }),
    panel: frame.getByRole("dialog"),
    log: frame.getByRole("log", { name: "Conversation" }),
    input: frame.getByRole("textbox", { name: "Your message" }),
  };
}

test.describe("GR-28 website chat", () => {
  test("a chat reaches the inbox with the AI's suggestion, and the reply reaches the widget", async ({ page, context, api, workspace }) => {
    const widget = await setUp(api, workspace);
    await serveShop(page, PAGE_ORIGIN, widget.widget_id);
    await page.goto(`${PAGE_ORIGIN}/shop`);

    const chat = chatOn(page);
    await expect(chat.launcher).toBeVisible();
    await chat.launcher.click();
    await expect(chat.panel).toBeVisible();
    await expect(chat.log).toContainText("Hi! How can we help?");
    await expect(chat.frame.getByRole("link", { name: "Powered by Amplychat" })).toBeVisible(); // Free

    const question = unique("Do you have the linen shirt?");
    await chat.input.fill(question);
    await chat.input.press("Enter");
    await expect(chat.log.getByText(question)).toBeVisible();

    // The inbox: a Website conversation with the AI's draft.
    const inbox = await context.newPage();
    await inbox.goto(`/w/${workspace.slug}/inbox`);
    await inbox.getByRole("list", { name: "Conversations" }).getByRole("link").filter({ hasText: question }).click();
    const thread = inbox.getByRole("region", { name: "Conversation", exact: true });
    await expect(thread.getByTestId("thread-identity")).toContainText("Website");
    const card = thread.getByRole("region", { name: "Suggested reply" });
    await expect(card).toContainText(SUGGESTED);

    // Sending it reaches the open widget in real time, with no reload.
    await card.getByRole("button", { name: "Send", exact: true }).click();
    await expect(chat.log.getByText(SUGGESTED)).toBeVisible({ timeout: 20_000 });
  });

  test("a reply typed in the inbox shows in the widget while it is closed, as a badge", async ({ page, context, api, workspace }) => {
    const widget = await setUp(api, workspace, { email_capture: "off" });
    await serveShop(page, PAGE_ORIGIN, widget.widget_id);
    await page.goto(`${PAGE_ORIGIN}/shop`);
    const chat = chatOn(page);
    await chat.launcher.click();
    const question = unique("Is the blue scarf back [e2e:unknown]?");
    await chat.input.fill(question);
    await chat.input.press("Enter");
    await expect(chat.log.getByText(question)).toBeVisible();
    await chat.input.press("Escape"); // focus is in the frame
    await expect(chat.panel).toBeHidden();

    const inbox = await context.newPage();
    await inbox.goto(`/w/${workspace.slug}/inbox`);
    await inbox.getByRole("list", { name: "Conversations" }).getByRole("link").filter({ hasText: question }).click();
    const reply = unique("Yes, it is back on Friday.");
    const composer = inbox.getByRole("region", { name: "Conversation", exact: true }).getByRole("textbox", { name: /^Reply to / });
    await composer.fill(reply);
    await composer.press("Enter");

    await expect(chat.launcher).toHaveAccessibleName(/1 new message/, { timeout: 20_000 });
    await chat.launcher.click();
    await expect(chat.log.getByText(reply)).toBeVisible();
    // Read out as the team's: the hand-off line the unknown question gets, and the reply.
    await expect.poll(() => chat.log.locator(".sr", { hasText: "Team:" }).count()).toBeGreaterThanOrEqual(2);
  });

  test("an email given in the widget becomes the contact's email", async ({ page, api, workspace }) => {
    const widget = await setUp(api, workspace, {
      marketing_consent_enabled: true,
      marketing_consent_text: "Email me offers.",
    });
    await serveShop(page, PAGE_ORIGIN, widget.widget_id);
    await page.goto(`${PAGE_ORIGIN}/shop`);
    const chat = chatOn(page);
    await chat.launcher.click();
    await chat.input.fill(unique("Hello, do you ship abroad?"));
    await chat.input.press("Enter");

    const form = chat.frame.getByRole("form", { name: "Your email address" });
    await expect(form).toBeVisible();
    await form.getByRole("textbox", { name: "Your email address" }).fill("pat@shop.example");
    await form.getByRole("checkbox", { name: "Email me offers." }).check();
    await form.getByRole("button", { name: "Save" }).click();
    await expect(form).toBeHidden();

    await expect
      .poll(
        async () => {
          const list = await api.call<{ items: { email: string | null }[] }>(
            "GET",
            `/v1/w/${workspace.id}/contacts?has_email=true`,
          );
          return list.items.map((c) => c.email);
        },
        { timeout: 20_000 },
      )
      .toContain("pat@shop.example");
  });

  test("it works from the keyboard: Enter opens it, Tab stays inside, Escape closes it", async ({ page, api, workspace }) => {
    const widget = await setUp(api, workspace);
    await serveShop(page, PAGE_ORIGIN, widget.widget_id);
    await page.goto(`${PAGE_ORIGIN}/shop`);
    const chat = chatOn(page);
    await expect(chat.launcher).toBeVisible();
    await chat.launcher.focus();
    await chat.launcher.press("Enter");
    await expect(chat.panel).toBeVisible();
    await expect(chat.input).toBeFocused();

    for (let i = 0; i < 8; i += 1) await chat.frame.locator(":focus").press("Tab");
    const inside = await chat.frame.locator(":focus").evaluate((node) => Boolean(node.closest("#panel")));
    expect(inside).toBe(true); // focus never left the open chat

    await chat.frame.locator(":focus").press("Escape");
    await expect(chat.panel).toBeHidden();
    await expect(chat.launcher).toBeFocused();
  });

  test("on a phone the open chat fills the screen", async ({ page, api, workspace }) => {
    const widget = await setUp(api, workspace);
    await page.setViewportSize({ width: 390, height: 800 });
    await serveShop(page, PAGE_ORIGIN, widget.widget_id);
    await page.goto(`${PAGE_ORIGIN}/shop`);
    const chat = chatOn(page);
    await chat.launcher.click();
    await expect(chat.panel).toBeVisible();
    const box = await page.locator('iframe[title="Chat"]').boundingBox();
    expect(box?.width).toBeCloseTo(390, 0);
    expect(box?.height).toBeCloseTo(800, 0);
  });

  test("a site that is not on the list gets no chat", async ({ page, api, workspace }) => {
    const widget = await setUp(api, workspace);
    await serveShop(page, OTHER_ORIGIN, widget.widget_id);
    await page.goto(`${OTHER_ORIGIN}/shop`);
    await expect(page.getByRole("heading", { name: "Maple test shop" })).toBeVisible();
    await expect(page.locator('iframe[title="Chat"]')).toBeHidden({ timeout: 15_000 });

    // The frame itself is refused for that host, and says where it may be framed: nowhere.
    const { E2E_API_URL } = requireStack();
    const refused = await page.request.get(`${E2E_API_URL}/widget/frame`, {
      params: { w: widget.widget_id, h: "127.0.0.1" },
    });
    expect(refused.status()).toBe(403);
    expect(refused.headers()["content-security-policy"]).toContain("frame-ancestors 'none'");
    const allowed = await page.request.get(`${E2E_API_URL}/widget/frame`, {
      params: { w: widget.widget_id, h: "localhost" },
    });
    expect(allowed.status()).toBe(200);
    expect(allowed.headers()["content-security-policy"]).toContain("frame-ancestors http://localhost:*");
  });

  test("Settings → Website chat shows the embed code and saves a new greeting", async ({ page, api, workspace }) => {
    await setUp(api, workspace);
    await page.goto(`/w/${workspace.slug}/settings/widget`);
    await expect(page.getByRole("heading", { level: 1, name: "Website chat" })).toBeVisible();
    await expect(page.getByText(/data-widget="wgt_/)).toBeVisible();
    await expect(page.getByRole("list", { name: "Allowed sites" })).toContainText("localhost");

    const greeting = unique("Welcome to Maple");
    await page.getByLabel("Greeting").fill(greeting);
    await page.getByRole("region", { name: "Save changes" }).getByRole("button", { name: "Save" }).click();
    await expect(page.getByRole("region", { name: "Save changes" })).toBeHidden();
    await page.reload();
    await expect(page.getByLabel("Greeting")).toHaveValue(greeting);

    // Free keeps the link: the switch is locked.
    await expect(page.getByRole("switch", { name: /Powered by Amplychat/ })).toBeDisabled();
  });
});
