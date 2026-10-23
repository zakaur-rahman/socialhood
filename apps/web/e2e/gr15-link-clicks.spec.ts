import { requireStack } from "./support/env";
import { expect, test } from "./support/fixtures";

/**
 * GR-15 Link click tracking and flow analytics on the sandbox. A flow sends a link button; the
 * button's address is our /l/<code> redirect (no run, step or contact in it); a person's click is
 * redirected and shows on the step's funnel in the editor's Stats tab, a link preview's does not;
 * and an automation can opt out so the raw link is sent.
 */
const DESTINATION = "https://example.com/catalogue";
const PERSON = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) Instagram 330.0.0.34.89";
const PREVIEW = "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)";

type Run = { id: string; result: string; conversation_id: string | null };
type Message = { direction: string; buttons: { title: string; url: string }[] };
type Funnel = { steps: { step_id: string; link_clicks: number; link_clickers: number }[] };

const FLOW = {
  start: "hello",
  steps: [{ type: "send", id: "hello", text: "Here's the catalogue.", buttons: [{ title: "Open", url: DESTINATION }] }],
};

/** The tracked address as the app serves it: the stack's API host, whatever base the API sent. */
function onStack(sent: string): string {
  return `${requireStack().E2E_API_URL}${new URL(sent).pathname}`;
}

test.describe("GR-15 link click tracking", () => {
  test("a click is redirected and shows on the step's funnel; a preview does not", async ({ page, api, sandbox }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    const { workspace, account } = sandbox;
    const keyword = `link${Date.now().toString(36)}`;
    const automation = await api.flowAutomation(workspace.id, account.id, keyword, FLOW);
    const fromId = `e2e_gr15_${Date.now().toString(36)}`;
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: keyword, fromId });

    const runs = () => api.call<{ items: Run[] }>("GET", `/v1/w/${workspace.id}/automations/${automation.id}/runs`);
    await expect.poll(async () => (await runs()).items[0]?.conversation_id, { timeout: 60_000 }).not.toBeNull();
    const conversation = (await runs()).items[0].conversation_id as string;

    // The message goes out with our address on the button, not the destination.
    const sentButton = async () => {
      const list = await api.call<{ items: Message[] }>(
        "GET",
        `/v1/w/${workspace.id}/conversations/${conversation}/messages`,
      );
      return list.items.find((m) => m.direction === "outbound" && m.buttons.length > 0)?.buttons[0];
    };
    await expect.poll(async () => (await sentButton())?.url, { timeout: 60_000 }).toContain("/l/");
    const url = (await sentButton())?.url as string;
    expect(url).not.toContain(DESTINATION);
    expect(new URL(url).pathname).toMatch(/^\/l\/[A-Za-z0-9_-]{16,}$/);

    // A preview fetcher is redirected but not counted; a person is redirected and counted.
    const followed = (agent: string) => fetch(onStack(url), { redirect: "manual", headers: { "user-agent": agent } });
    const preview = await followed(PREVIEW);
    expect([preview.status, preview.headers.get("location")]).toEqual([302, DESTINATION]);
    const person = await followed(PERSON);
    expect([person.status, person.headers.get("location")]).toEqual([302, DESTINATION]);

    const funnel = () => api.call<Funnel>("GET", `/v1/w/${workspace.id}/automations/${automation.id}/funnel?days=7`);
    await expect
      .poll(async () => (await funnel()).steps.find((s) => s.step_id === "hello")?.link_clicks, { timeout: 60_000 })
      .toBe(1);

    // The Stats tab shows it on the step.
    await page.goto(`/w/${workspace.slug}/automations/${automation.id}`);
    await page.getByRole("tab", { name: "Stats" }).click();
    const step = page.getByTestId("funnel-step").first();
    await expect(step).toContainText("Link clicks");
    await expect(step).toContainText("1 (1 person)");

    // An unknown code is not found.
    const missing = await fetch(`${requireStack().E2E_API_URL}/l/${"x".repeat(16)}`, { redirect: "manual" });
    expect(missing.status).toBe(404);
  });

  test("an automation that opts out sends the raw link", async ({ api, sandbox }) => {
    const { workspace, account } = sandbox;
    const keyword = `raw${Date.now().toString(36)}`;
    const automation = await api.flowAutomation(workspace.id, account.id, keyword, FLOW);
    const current = await api.call<Record<string, unknown>>("GET", `/v1/w/${workspace.id}/automations/${automation.id}`);
    await api.call("POST", `/v1/w/${workspace.id}/automations/${automation.id}/pause`);
    await api.call("PUT", `/v1/w/${workspace.id}/automations/${automation.id}`, {
      name: current.name,
      social_account_id: account.id,
      trigger: "dm_keyword",
      keywords: [keyword],
      match_mode: "word",
      track_links: false,
    });
    await api.call("POST", `/v1/w/${workspace.id}/automations/${automation.id}/activate`);

    const fromId = `e2e_gr15_raw_${Date.now().toString(36)}`;
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: keyword, fromId });
    const runs = () => api.call<{ items: Run[] }>("GET", `/v1/w/${workspace.id}/automations/${automation.id}/runs`);
    await expect.poll(async () => (await runs()).items[0]?.conversation_id, { timeout: 60_000 }).not.toBeNull();
    const conversation = (await runs()).items[0].conversation_id as string;
    await expect
      .poll(
        async () => {
          const list = await api.call<{ items: Message[] }>(
            "GET",
            `/v1/w/${workspace.id}/conversations/${conversation}/messages`,
          );
          return list.items.find((m) => m.direction === "outbound" && m.buttons.length > 0)?.buttons[0]?.url;
        },
        { timeout: 60_000 },
      )
      .toBe(DESTINATION);
  });
});
