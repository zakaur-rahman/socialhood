import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import type { Locator, Page } from "@playwright/test";

import type { Api, SandboxAccount, Workspace } from "../../e2e/support/api";
import { expect, test } from "../../e2e/support/fixtures";

/**
 * The landing page's product screenshots, from the real app on the e2e stack (README.md here).
 *
 * It seeds a demo workspace through the stack's own helpers (a sandbox Instagram account, DMs,
 * comments, knowledge and an active automation), opens the screens the landing page shows and
 * saves each one at 2x as WebP in public/marketing/. Nothing reaches Meta or a model: the sandbox
 * and the fake AI answer.
 *
 * Display-only rewrites (installRewrites): the sandbox names its customers "Sandbox customer
 * 1a2b" and its account "Sandbox shop", marks the account with a Sandbox badge, and the e2e user
 * has a test email. The page's fetch is wrapped so those read as a made-up shop, made-up first
 * names and no email. Every other word and number on screen is what the app rendered.
 */

const OUT = join(__dirname, "..", "..", "public", "marketing");

// ---------------------------------------------------------------- made-up demo data

const SHOP = "Indigo Lane";

/** Made-up first names with an initial, in place of the sandbox's "Sandbox customer 1a2b". */
const KNOWN_NAMES: Record<string, string> = { mj01: "Meera K.", ap02: "Arjun P.", rs03: "Riya S.", nd04: "Neha D." };
const OTHER_NAMES = ["Vikram T.", "Sana M.", "Kabir R.", "Ishaan B."];

const DMS: { fromId: string; text: string; intent: string; sentiment: string }[] = [
  { fromId: "demo_nd04", text: "Can I return it if it doesn't fit?", intent: "refund", sentiment: "neutral" },
  { fromId: "demo_rs03", text: "Kya ye kurta M size mein milega?", intent: "product_inquiry", sentiment: "neutral" },
  { fromId: "demo_ap02", text: "Do you deliver to Pune? How many days does it take?", intent: "shipping", sentiment: "neutral" },
  // The e2e worker's fake AI drafts "Thanks for asking! Yes, it's in stock in every colour and
  // ships this week." for every question, so the hero's question is one that answer fits.
  { fromId: "demo_mj01", text: "Hi! Is the linen shirt in stock in blue? When would it ship?", intent: "product_inquiry", sentiment: "positive" },
];

const KNOWLEDGE = [
  { type: "faq", question: "How long does delivery take?", body: "Orders ship within 2 working days. Delivery takes 3 to 5 days anywhere in India." },
  { type: "faq", question: "Can I return or exchange an item?", body: "Yes, within 7 days of delivery, unused and with the tags on. Exchanges are free." },
  { type: "text", title: "Price list", body: "Linen shirt: ₹1,299. Cotton kurta: ₹1,499. Block-print dupatta: ₹899." },
  { type: "text", title: "Shop timings", body: "Monday to Saturday, 10 am to 8 pm. Sunday, 11 am to 6 pm." },
] as const;

// ---------------------------------------------------------------- display-only rewrites

type RewriteConfig = { known: Record<string, string>; others: string[]; shop: string; handle: string };

/** Runs in the page before the app: rewrites the API's JSON and its event stream (see above). */
function installRewrites(config: RewriteConfig) {
  const nameFor = (code: string) => config.known[code] ?? config.others[code.charCodeAt(code.length - 1) % config.others.length];
  const rewrite = (text: string) =>
    text
      .replace(/Sandbox customer (\w{4})/g, (_m, code: string) => nameFor(code))
      .replace(/"sandbox":true/g, '"sandbox":false')
      .replace(/Sandbox shop/g, config.shop)
      .replace(/sandbox\.shop\.\w{4}/g, config.handle)
      .replace(/"email":"[^"]*"/g, '"email":""');
  const isApi = /:\d+\/v1\//;
  const original = window.fetch.bind(window);
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const response = await original(input, init);
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    if (!isApi.test(url) || [101, 204, 205, 304].includes(response.status)) return response;
    const type = response.headers.get("content-type") ?? "";
    const meta = { status: response.status, statusText: response.statusText, headers: response.headers };
    if (type.includes("text/event-stream") && response.body) {
      // Line by line, so a name is never split across two chunks.
      const decoder = new TextDecoder();
      const encoder = new TextEncoder();
      let pending = "";
      const stream = new TransformStream<Uint8Array, Uint8Array>({
        transform(chunk, controller) {
          pending += decoder.decode(chunk, { stream: true });
          const end = pending.lastIndexOf("\n");
          if (end < 0) return;
          controller.enqueue(encoder.encode(rewrite(pending.slice(0, end + 1))));
          pending = pending.slice(end + 1);
        },
        flush(controller) {
          if (pending) controller.enqueue(encoder.encode(rewrite(pending)));
        },
      });
      return new Response(response.body.pipeThrough(stream), meta);
    }
    if (type.includes("json")) return new Response(rewrite(await response.text()), meta);
    return response;
  };
}

// ---------------------------------------------------------------- seeding

type Contact = { display_name: string | null; username: string | null };
type ListBody = { items: { id: string; contact: Contact }[] };
type Detail = { latest_analysis: { id: string } | null };

async function seed(api: Api): Promise<{ workspace: Workspace; account: SandboxAccount; automationId: string }> {
  const workspace = await api.newWorkspace(SHOP);
  const account = await api.connectSandbox(workspace.id);
  const wid = workspace.id;

  for (const source of KNOWLEDGE) await api.call("POST", `/v1/w/${wid}/knowledge-sources`, source);

  const automation = await api.call<{ id: string }>("POST", `/v1/w/${wid}/automations`, {
    name: "Comment LINK, get the link",
    social_account_id: account.id,
  });
  await api.call("PUT", `/v1/w/${wid}/automations/${automation.id}`, {
    name: "Comment LINK, get the link",
    social_account_id: account.id,
    trigger: "comment_keyword",
    keywords: ["link"],
    match_mode: "word",
    action: "send_message",
    message_text: "Hi {first_name|there}! Here's the new linen collection.",
    message_buttons: [{ title: "See the collection", url: "https://example.com/linen" }],
    public_reply_texts: ["Sent you a DM!"],
    confirm_first: true,
    opening_text: "Hi! Tap below and we'll send you the link.",
    opening_button: "Send me the link",
    follow_nudge: true,
    follow_nudge_text: "Follow us to see new drops first.",
  });
  await api.call("POST", `/v1/w/${wid}/automations/${automation.id}/activate`);

  for (const dm of DMS) {
    await api.inbound(wid, { accountId: account.id, kind: "dm", text: dm.text, fromId: dm.fromId });
    await new Promise((r) => setTimeout(r, 400));
  }
  for (const [fromId, username] of [
    ["demo_cm05", "linen.lover"],
    ["demo_cm06", "weekend.wardrobe"],
  ]) {
    await api.inbound(wid, { accountId: account.id, kind: "comment", text: "LINK", fromId, fromUsername: username });
  }

  // Names arrive after a profile fetch; analyses after the worker reads each message.
  let list: ListBody = { items: [] };
  await expect
    .poll(
      async () => {
        list = await api.call<ListBody>("GET", `/v1/w/${wid}/conversations?view=all&limit=30`);
        // Commenters' conversations show their handle; DM contacts get a fetched name.
        const dmContacts = list.items.filter((c) => c.contact.username?.startsWith("customer_"));
        return list.items.length >= 9 && dmContacts.length >= 7 && dmContacts.every((c) => c.contact.display_name);
      },
      { timeout: 90_000, intervals: [1000] },
    )
    .toBe(true);

  // The fake AI tags every message "other"; the demo DMs are corrected as an owner would.
  for (const dm of DMS) {
    const conversation = list.items.find((c) => c.contact.username === `customer_${dm.fromId.slice(-4)}`);
    if (!conversation) throw new Error(`No conversation for ${dm.fromId}`);
    let detail: Detail = { latest_analysis: null };
    await expect
      .poll(
        async () => {
          detail = await api.call<Detail>("GET", `/v1/w/${wid}/conversations/${conversation.id}`);
          return Boolean(detail.latest_analysis);
        },
        { timeout: 60_000, intervals: [1000] },
      )
      .toBe(true);
    await api.call("PATCH", `/v1/w/${wid}/message-analyses/${detail.latest_analysis?.id}`, {
      intent: dm.intent,
      sentiment: dm.sentiment,
    });
  }
  return { workspace, account, automationId: automation.id };
}

// ---------------------------------------------------------------- saving

/** A PNG screenshot as WebP, encoded by Chromium on a blank page (no image library needed). */
async function saveWebp(page: Page, png: Buffer, name: string, quality = 0.85) {
  const encoder = await page.context().newPage();
  const dataUrl = await encoder.evaluate(
    async ({ base64, q }) => {
      const image = new Image();
      image.src = `data:image/png;base64,${base64}`;
      await image.decode();
      const canvas = document.createElement("canvas");
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      canvas.getContext("2d")?.drawImage(image, 0, 0);
      return canvas.toDataURL("image/webp", q);
    },
    { base64: png.toString("base64"), q: quality },
  );
  await encoder.close();
  const bytes = Buffer.from(dataUrl.slice(dataUrl.indexOf(",") + 1), "base64");
  writeFileSync(join(OUT, name), bytes);
  console.log(`${name}: ${Math.round(bytes.length / 1024)} KiB`);
}

async function shot(page: Page, target: Page | Locator, name: string) {
  // Animations settled, caret hidden.
  await page.waitForTimeout(800);
  const png = await target.screenshot({ animations: "disabled", caret: "hide" });
  await saveWebp(page, png, name);
}

test("capture the landing page's product screenshots", async ({ page, api }) => {
  mkdirSync(OUT, { recursive: true });
  await page.addInitScript(installRewrites, {
    known: KNOWN_NAMES,
    others: OTHER_NAMES,
    shop: SHOP,
    handle: "indigolane.example",
  } satisfies RewriteConfig);
  const { workspace, automationId } = await seed(api);
  const base = `/w/${workspace.slug}`;

  // 1. The hero: the inbox with an AI draft waiting (1440 x 900).
  await page.goto(`${base}/inbox`);
  await page.getByRole("list", { name: "Conversations" }).getByRole("link").filter({ hasText: "linen shirt" }).click();
  const thread = page.getByRole("region", { name: "Conversation", exact: true });
  await expect(thread.getByRole("region", { name: "Suggested reply" })).toContainText("Thanks for asking", { timeout: 60_000 });
  await expect(thread.getByText("Product question").first()).toBeVisible();
  await shot(page, page, "inbox.webp");

  // 2. How it works, step 3: the thread and its draft, closer (a shorter window).
  await page.setViewportSize({ width: 1440, height: 580 });
  await shot(page, thread, "ai-draft.webp");
  await page.setViewportSize({ width: 1440, height: 900 });

  // 3. Step 1: the connected Instagram account, with its AI mode.
  await page.goto(`${base}/settings/connections`);
  const card = page.getByRole("article", { name: SHOP });
  await expect(card.getByText("Connected", { exact: true })).toBeVisible();
  await shot(page, card, "connect.webp");

  // 4. Step 2: an FAQ in the knowledge base.
  await page.goto(`${base}/knowledge`);
  await page.getByRole("button", { name: "Edit How long does delivery take?" }).click();
  const sheet = page.getByRole("dialog");
  await expect(sheet.getByRole("textbox").first()).toHaveValue(/How long does delivery take\?|Orders ship/);
  // The sheet opens with the question selected; blur it, and keep only the header and the form.
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
  await page.waitForTimeout(800); // the sheet has slid in
  const box = await sheet.boundingBox();
  const form = await sheet.locator("form").boundingBox();
  if (!box || !form) throw new Error("The source sheet isn't on screen");
  const png = await page.screenshot({
    animations: "disabled",
    caret: "hide",
    clip: { x: box.x, y: box.y, width: box.width, height: form.y + form.height - box.y + 8 },
  });
  await saveWebp(page, png, "knowledge.webp");

  // 5. The automation showcase: the editor's live preview of comment → tap → link → follow.
  await page.goto(`${base}/automations/${automationId}`);
  const preview = page.getByRole("tabpanel", { name: "Preview" });
  await expect(preview).toContainText("Send me the link");
  await shot(page, preview, "automation-preview.webp");
});
