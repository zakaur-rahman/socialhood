import { createHmac, timingSafeEqual } from "node:crypto";
import { createServer, type IncomingMessage, type Server } from "node:http";
import type { AddressInfo } from "node:net";

import { expect, test } from "./support/fixtures";

/**
 * GR-26 Zapier triggers over REST hooks, on the sandbox. Zapier itself cannot run here, so the spec
 * plays its part: it subscribes a local receiver through POST /public/v1/hooks with an API key, gets
 * a signed delivery when a customer writes, checks the polling list a Zap is tested with, and
 * unsubscribes. The Zap that moves captured leads to a Google Sheet is the manual test in
 * integrations/zapier/README.md.
 */
type Received = { headers: IncomingMessage["headers"]; body: string };
type Hook = { id: string; trigger: string; status: string; signing_secret: string };

async function receiver(): Promise<{ server: Server; url: string; received: Received[] }> {
  const received: Received[] = [];
  const server = createServer((req, res) => {
    let body = "";
    req.on("data", (chunk) => (body += chunk));
    req.on("end", () => {
      received.push({ headers: req.headers, body });
      res.statusCode = 200;
      res.end();
    });
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address() as AddressInfo;
  return { server, url: `http://127.0.0.1:${port}/zap`, received };
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

test.describe("GR-26 Zapier REST hooks", () => {
  test("a subscribed trigger gets a signed delivery, and unsubscribing stops them", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    await api.setPlan(workspace.id, "pro");
    const made = await api.call<{ key: string }>("POST", `/v1/w/${workspace.id}/api-keys`, {
      name: "Zapier",
      scopes: ["webhooks:subscribe", "contacts:read"],
    });
    const hook = await receiver();
    try {
      const subscribed = await api.publicCall<Hook>(made.key, "POST", "/hooks", {
        trigger: "new_contact",
        target_url: hook.url,
      });
      expect(subscribed.status).toBe(201);
      expect(subscribed.body.trigger).toBe("new_contact");
      expect(subscribed.body.signing_secret).toMatch(/^whsec_/);

      // It is an ordinary endpoint in Settings > Integrations, named for the trigger.
      await page.goto(`/w/${workspace.slug}/settings/integrations`);
      await expect(page.getByRole("region", { name: "Zapier: new contact" })).toBeVisible();

      // A new customer writes: Zapier's trigger URL gets contact.created, signed.
      const fromId = `e2e_gr26_${Date.now().toString(36)}`;
      await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: "Hi there", fromId });
      await expect.poll(() => hook.received.length, { timeout: 30_000 }).toBe(1);
      const [request] = hook.received;
      const event = JSON.parse(request.body) as { id: string; type: string; data: { contact: { id: string } } };
      expect(event.type).toBe("contact.created");
      expect(request.headers["webhook-id"]).toBe(event.id);
      expect(signed(subscribed.body.signing_secret, request)).toBe(true);

      // The polling list a Zap is tested with has the same contact.
      const listed = await api.publicCall<{ items: { id: string }[] }>(made.key, "GET", "/contacts?sort=created&limit=10");
      expect(listed.status).toBe(200);
      expect(listed.body.items.map((c) => c.id)).toContain(event.data.contact.id);

      // Turning the Zap off unsubscribes; a second customer is not delivered.
      const gone = await api.publicCall(made.key, "DELETE", `/hooks/${subscribed.body.id}`);
      expect(gone.status).toBe(204);
      expect((await api.publicCall(made.key, "DELETE", `/hooks/${subscribed.body.id}`)).status).toBe(404);
      await api.inbound(workspace.id, {
        accountId: account.id,
        kind: "dm",
        text: "Hello again",
        fromId: `${fromId}_2`,
      });
      await expect
        .poll(
          async () =>
            (await api.call<{ items: unknown[] }>("GET", `/v1/w/${workspace.id}/webhook-endpoints`)).items.length,
        )
        .toBe(0);
      await page.waitForTimeout(3_000); // a delivery would have arrived by now
      expect(hook.received).toHaveLength(1);
    } finally {
      hook.server.close();
    }
  });

  test("subscribing needs the scope, a plan with the API, and a valid address", async ({ api, sandbox }) => {
    const { workspace } = sandbox;
    await api.setPlan(workspace.id, "pro");
    const readOnly = await api.call<{ key: string }>("POST", `/v1/w/${workspace.id}/api-keys`, {
      name: "Read only",
      scopes: ["contacts:read"],
    });
    const refused = await api.publicCall<{ code: string }>(readOnly.key, "POST", "/hooks", {
      trigger: "new_contact",
      target_url: "https://hooks.zapier.com/hooks/standard/1/abc/",
    });
    expect(refused.status).toBe(403);
    expect(refused.body.code).toBe("forbidden");

    const subscriber = await api.call<{ key: string }>("POST", `/v1/w/${workspace.id}/api-keys`, {
      name: "Zapier",
      scopes: ["webhooks:subscribe"],
    });
    const badTrigger = await api.publicCall(subscriber.key, "POST", "/hooks", {
      trigger: "contact.created",
      target_url: "https://hooks.zapier.com/hooks/standard/1/abc/",
    });
    expect(badTrigger.status).toBe(422);

    // Back on Free the key stops working at once (PD-6).
    await api.setPlan(workspace.id, "free");
    const free = await api.publicCall<{ code: string; entitlement: string }>(subscriber.key, "GET", "/hooks");
    expect(free.status).toBe(402);
    expect(free.body).toMatchObject({ code: "entitlement_required", entitlement: "public_api" });
  });
});
