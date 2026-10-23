import { createHmac, timingSafeEqual } from "node:crypto";
import { createServer, type IncomingMessage, type Server } from "node:http";
import type { AddressInfo } from "node:net";

import { expect, test } from "./support/fixtures";

/**
 * GR-04 Outbound webhooks on the sandbox: a test receiver (a local HTTP server; the e2e stack allows
 * local addresses) gets a signed lead.captured when a flow's question saves an email, and a failing
 * receiver's retries show in Settings › Integrations.
 */
type Received = { headers: IncomingMessage["headers"]; body: string };

async function receiver(status: number): Promise<{ server: Server; url: string; received: Received[] }> {
  const received: Received[] = [];
  const server = createServer((req, res) => {
    let body = "";
    req.on("data", (chunk) => (body += chunk));
    req.on("end", () => {
      received.push({ headers: req.headers, body });
      res.statusCode = status;
      res.end();
    });
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address() as AddressInfo;
  return { server, url: `http://127.0.0.1:${port}/hook`, received };
}

/** Standard Webhooks: v1,base64(HMAC-SHA256(key, "{id}.{timestamp}.{body}")), key = the secret's base64 part. */
function signed(secret: string, request: Received): boolean {
  const id = String(request.headers["webhook-id"]);
  const timestamp = String(request.headers["webhook-timestamp"]);
  const key = Buffer.from(secret.slice("whsec_".length), "base64");
  const expected = createHmac("sha256", key).update(`${id}.${timestamp}.${request.body}`).digest();
  return String(request.headers["webhook-signature"])
    .split(" ")
    .some((part) => {
      const given = Buffer.from(part.replace(/^v1,/, ""), "base64");
      return given.length === expected.length && timingSafeEqual(given, expected);
    });
}

test.describe("GR-04 outbound webhooks", () => {
  test("a captured email reaches the endpoint, signed", async ({ api, sandbox }) => {
    const { workspace, account } = sandbox;
    const hook = await receiver(200);
    try {
      const endpoint = await api.call<{ id: string; signing_secret: string }>(
        "POST",
        `/v1/w/${workspace.id}/webhook-endpoints`,
        { url: hook.url, description: "e2e receiver", events: ["lead.captured"] },
      );
      const keyword = `lead${Date.now().toString(36)}`;
      const automation = await api.flowAutomation(workspace.id, account.id, keyword, {
        start: "q",
        steps: [{ type: "ask", id: "q", text: "What's your email?", expect: "email" }],
      });
      const fromId = `e2e_gr04_${Date.now().toString(36)}`;
      await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: keyword, fromId });
      await expect
        .poll(
          async () =>
            (await api.call<{ items: { result: string }[] }>("GET", `/v1/w/${workspace.id}/automations/${automation.id}/runs`))
              .items[0]?.result,
          { timeout: 30_000 },
        )
        .toBe("awaiting_reply");
      await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: "Priya@Example.com", fromId });

      await expect.poll(() => hook.received.length, { timeout: 30_000 }).toBe(1);
      const [request] = hook.received;
      const event = JSON.parse(request.body) as { id: string; type: string; data: { captured: { value: string } } };
      expect(event.type).toBe("lead.captured");
      expect(event.data.captured.value).toBe("priya@example.com");
      expect(request.headers["webhook-id"]).toBe(event.id);
      expect(signed(endpoint.signing_secret, request)).toBe(true);
      expect(signed(`whsec_${Buffer.from("not the secret").toString("base64")}`, request)).toBe(false);
    } finally {
      hook.server.close();
    }
  });

  test("a failing endpoint shows its retry in the log", async ({ page, api, sandbox }) => {
    const { workspace } = sandbox;
    const hook = await receiver(500);
    try {
      await page.goto(`/w/${workspace.slug}/settings/integrations`);
      await expect(page.getByRole("heading", { name: "Integrations", level: 1 })).toBeVisible();
      await page.getByRole("button", { name: "Add endpoint" }).first().click();
      const dialog = page.getByRole("dialog", { name: "Add a webhook endpoint" });
      await dialog.getByRole("textbox", { name: "Endpoint address" }).fill(hook.url);
      await dialog.getByRole("textbox", { name: "Name (optional)" }).fill("Failing receiver");
      await dialog.getByRole("button", { name: "Add endpoint" }).click();

      const secret = page.getByRole("dialog", { name: "Your signing secret" });
      await expect(secret.getByTestId("signing-secret")).toHaveText(/^whsec_/);
      await secret.getByRole("button", { name: "Done" }).click();

      const card = page.getByRole("region", { name: "Failing receiver" });
      await card.getByRole("button", { name: "Send test event" }).click();
      await expect.poll(() => hook.received.length, { timeout: 30_000 }).toBeGreaterThanOrEqual(1);
      const row = card.getByTestId("webhook-delivery").first();
      await expect(row).toContainText("webhook.test", { timeout: 30_000 });
      await expect(row).toContainText("Trying", { timeout: 30_000 });
      await expect(row).toContainText("The endpoint answered 500.");
      await expect(row).toContainText("500");
      const endpoints = await api.call<{ items: { id: string }[] }>("GET", `/v1/w/${workspace.id}/webhook-endpoints`);
      const log = await api.call<{ items: { attempts: number; next_attempt_at: string | null }[] }>(
        "GET",
        `/v1/w/${workspace.id}/webhook-endpoints/${endpoints.items[0].id}/deliveries`,
      );
      expect(log.items[0].attempts).toBe(1);
      expect(log.items[0].next_attempt_at).not.toBeNull(); // tried again in a minute
    } finally {
      hook.server.close();
    }
  });
});
