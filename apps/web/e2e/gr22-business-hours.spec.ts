import { expect, test } from "./support/fixtures";

/**
 * GR-22 Business hours. While the workspace is closed, a message that no automation answers gets the
 * away message once; while it is open, none. An automation can require "outside hours". Hours are
 * edited in Settings → Business hours (which works at phone width). The hours below are built from
 * the clock in UTC (the workspace's time zone is set to UTC), three hours from now, so the test is
 * closed now and open at the other times whatever time it runs.
 */
type Message = { direction: string; source: string; text: string | null };
type Conversation = { id: string };

const AWAY = "Thanks for writing. We are closed right now and reply from the next opening time.";

function closedNow(): { start: string; end: string } {
  const hour = (new Date().getUTCHours() + 3) % 24;
  const pad = (n: number) => String(n).padStart(2, "0");
  return { start: `${pad(hour)}:00`, end: hour === 23 ? "24:00" : `${pad(hour + 1)}:00` };
}

async function outbound(api: import("./support/api").Api, wid: string): Promise<string[]> {
  const list = await api.call<{ items: Conversation[] }>("GET", `/v1/w/${wid}/conversations`);
  const texts: string[] = [];
  for (const conversation of list.items) {
    const messages = await api.call<{ items: Message[] }>("GET", `/v1/w/${wid}/conversations/${conversation.id}/messages`);
    texts.push(...messages.items.filter((m) => m.direction === "outbound").map((m) => m.text ?? ""));
  }
  return texts;
}

test.describe("GR-22 business hours", () => {
  test("a message while closed gets the away message once", async ({ api, sandbox }) => {
    const { workspace, account } = sandbox;
    await api.setTimezone(workspace.id, "UTC");
    await api.setAiMode(workspace.id, account.id, "suggest");
    await api.setHours(workspace.id, { open: closedNow(), away: AWAY });

    const fan = `e2e_gr22_${Date.now().toString(36)}`;
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: "Are you open?", fromId: fan });
    await expect.poll(async () => (await outbound(api, workspace.id)).filter((t) => t === AWAY).length, { timeout: 30_000 }).toBe(1);

    // Another message in the same closed window: no second away message.
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: "Hello?", fromId: fan });
    await new Promise((resolve) => setTimeout(resolve, 8_000));
    expect((await outbound(api, workspace.id)).filter((t) => t === AWAY)).toHaveLength(1);
  });

  test("no away message while open", async ({ api, sandbox }) => {
    const { workspace, account } = sandbox;
    await api.setTimezone(workspace.id, "UTC");
    await api.setHours(workspace.id, { open: { start: "00:00", end: "24:00" }, away: AWAY });

    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: "Are you open?", fromId: "e2e_gr22_open" });
    await new Promise((resolve) => setTimeout(resolve, 8_000));
    expect((await outbound(api, workspace.id)).filter((t) => t === AWAY)).toHaveLength(0);
  });

  test("an automation that needs outside hours answers while closed and not while open", async ({ api, sandbox }) => {
    const { workspace, account } = sandbox;
    await api.setTimezone(workspace.id, "UTC");
    const keyword = `hours${Date.now().toString(36)}`;
    const draft = await api.call<{ id: string }>("POST", `/v1/w/${workspace.id}/automations`, {
      name: "Night owl",
      social_account_id: account.id,
    });
    await api.call("PUT", `/v1/w/${workspace.id}/automations/${draft.id}`, {
      name: "Night owl",
      social_account_id: account.id,
      trigger: "dm_keyword",
      keywords: [keyword],
      match_mode: "word",
      action: "send_message",
      message_text: "Leave your number and we will call you back.",
      hours_condition: "outside",
    });
    await api.call("POST", `/v1/w/${workspace.id}/automations/${draft.id}/activate`);
    const runs = () => api.call<{ items: unknown[] }>("GET", `/v1/w/${workspace.id}/automations/${draft.id}/runs`);

    await api.setHours(workspace.id, { open: { start: "00:00", end: "24:00" } });
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: keyword, fromId: "e2e_gr22_day" });
    await new Promise((resolve) => setTimeout(resolve, 8_000));
    expect((await runs()).items).toHaveLength(0);

    await api.setHours(workspace.id, { open: closedNow() });
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: keyword, fromId: "e2e_gr22_night" });
    await expect.poll(async () => (await runs()).items.length, { timeout: 30_000 }).toBe(1);
  });

  test("the hours are edited in Settings, also on a phone", async ({ page, sandbox }) => {
    const { workspace } = sandbox;
    await page.setViewportSize({ width: 375, height: 800 });
    await page.goto(`/w/${workspace.slug}/settings/hours`);
    await expect(page.getByRole("heading", { name: "Business hours", level: 1 })).toBeVisible();

    await page.getByRole("switch", { name: "Use business hours" }).first().click();
    await page.getByLabel("Monday closes at").first().fill("18:00");
    await page.getByRole("switch", { name: "Away message" }).first().click();
    await page.getByLabel("Message", { exact: true }).first().fill("We are closed. Back at 9.");
    await page.getByRole("button", { name: "Save hours" }).first().click();
    await expect(page.getByText("Business hours saved")).toBeVisible();

    // No sideways scroll at 375 px.
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);

    await page.reload();
    await expect(page.getByLabel("Monday closes at").first()).toHaveValue("18:00");
  });
});
