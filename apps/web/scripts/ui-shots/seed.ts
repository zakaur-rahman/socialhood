import { createHash, randomUUID } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";

import { expect } from "@playwright/test";

import { ApiFailure, type Api, type SandboxAccount, type Workspace } from "../../e2e/support/api";
import { requireStack } from "../../e2e/support/env";

/**
 * The QA workspaces, seeded through the stack's own helpers and the API (no rewrites: every word
 * on screen is what the app rendered for this sandbox data).
 *
 * - "QA Shop": a sandbox Instagram account (which backfills three posts, three conversations and
 *   some comments), four knowledge sources, an active comment-to-DM automation and a draft DM
 *   automation, five customer DMs (one with an AI draft waiting), comments on the posts, three
 *   scheduled posts this week and next and one draft post for the composer.
 * - "QA Reconnect": a second workspace whose sandbox account needs reconnecting, for the banner
 *   (a reply that the sandbox refuses with account_needs_reconnect marks it, as Instagram would).
 *
 * The result is cached in the output folder for the stack that made it (a hash of its API URL
 * and per-run seed token), so a retry or a --grep run on the same stack doesn't seed again.
 */

/** Bumped when the seeded data changes, so an older cache file is ignored. */
const VERSION = 2;

export type Seeded = {
  version: number;
  stack: string;
  main: {
    workspace: Workspace;
    account: SandboxAccount;
    /** The DM with an AI draft waiting. */
    conversationId: string;
    /** The active comment-to-DM automation (the editor and the row menu). */
    automationId: string;
    automationName: string;
    /** A backfilled post with comments (Comments › a post). */
    postId: string;
    /** A draft post with a photo and a caption (the composer). */
    draftPostId: string;
  };
  /** Null when the sandbox didn't mark the account (the banner shots are then skipped). */
  banner: { workspace: Workspace; account: SandboxAccount; conversationId: string } | null;
};

const SHOP = "QA Shop";
const AUTOMATION = "Comment LINK, get the link";

/** The DM whose AI draft the conversation shot shows; the e2e worker's fake AI drafts
 * "Thanks for asking! Yes, it's in stock in every colour and ships this week." */
const DRAFT_DM = { fromId: "qa_mj01", text: "Hi! Is the linen shirt in stock in blue? When would it ship?" };

const DMS = [
  { fromId: "qa_nd04", text: "Can I return it if it doesn't fit?" },
  { fromId: "qa_rs03", text: "Kya ye kurta M size mein milega?" },
  { fromId: "qa_ap02", text: "Do you deliver to Pune? How many days does it take?" },
  { fromId: "qa_gw05", text: "Do you offer gift wrapping? [e2e:unknown]" },
  DRAFT_DM,
];

const COMMENTS = [
  { fromId: "qa_cm01", username: "linen.lover", text: "LINK" },
  { fromId: "qa_cm02", username: "weekend.wardrobe", text: "LINK" },
  { fromId: "qa_cm03", username: "pune.picks", text: "What's the price of the blue one?" },
  { fromId: "qa_cm04", username: "kurta.club", text: "Love this colour! Is M available?" },
];

const KNOWLEDGE = [
  { type: "faq", question: "How long does delivery take?", body: "Orders ship within 2 working days. Delivery takes 3 to 5 days anywhere in India." },
  { type: "faq", question: "Can I return or exchange an item?", body: "Yes, within 7 days of delivery, unused and with the tags on. Exchanges are free." },
  { type: "text", title: "Price list", body: "Linen shirt: ₹1,299. Cotton kurta: ₹1,499. Block-print dupatta: ₹899." },
  { type: "text", title: "Shop timings", body: "Monday to Saturday, 10 am to 8 pm. Sunday, 11 am to 6 pm." },
] as const;

const SCHEDULED = [
  { inHours: 26, caption: "New linen shirts in four colours. Which one is yours? #linen #summerstyle", photo: "linen-shirts.jpg" },
  { inHours: 50, caption: "Block-print dupattas are back in stock. DM us to order.", photo: "dupattas.jpg" },
  { inHours: 8 * 24 + 3, caption: "Festive kurtas: early access for our followers this weekend.", photo: "festive-kurtas.jpg" },
];

type Items<T> = { items: T[] };
type ConversationItem = { id: string; contact: { display_name: string | null; username: string | null } };
type ConversationDetail = { pending_suggestion: unknown; latest_analysis: unknown };
type AccountItem = { id: string; status: string };
type PostItem = { id: string; comments_count: number | null };

const contactOf = (fromId: string) => `customer_${fromId.slice(-4)}`;

function stackKey(): string {
  const stack = requireStack();
  return createHash("sha256").update(`${stack.E2E_API_URL}|${stack.E2E_SEED_TOKEN}`).digest("hex").slice(0, 16);
}

function poll<T>(probe: () => Promise<T>, message: string, timeout = 150_000) {
  return expect.poll(probe, { message, timeout, intervals: [1000] });
}

async function automation(api: Api, wid: string, accountId: string): Promise<string> {
  const created = await api.call<{ id: string }>("POST", `/v1/w/${wid}/automations`, { name: AUTOMATION, social_account_id: accountId });
  await api.call("PUT", `/v1/w/${wid}/automations/${created.id}`, {
    name: AUTOMATION,
    social_account_id: accountId,
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
  await api.call("POST", `/v1/w/${wid}/automations/${created.id}/activate`);

  // A second one left as a draft, so the list shows both states.
  const draft = await api.call<{ id: string }>("POST", `/v1/w/${wid}/automations`, { name: "Price by DM", social_account_id: accountId });
  await api.call("PUT", `/v1/w/${wid}/automations/${draft.id}`, {
    name: "Price by DM",
    social_account_id: accountId,
    trigger: "dm_keyword",
    keywords: ["price", "rate"],
    match_mode: "word",
    action: "send_message",
    message_text: "Hi {first_name|there}! Our price list is here.",
  });
  return created.id;
}

async function posts(api: Api, wid: string, accountId: string): Promise<string> {
  const hour = 60 * 60 * 1000;
  // On the hour, so the calendar places them cleanly.
  const at = (hours: number) => new Date(Math.ceil((Date.now() + hours * hour) / hour) * hour).toISOString();
  for (const post of SCHEDULED) {
    const asset = await api.mediaAsset(wid, post.photo);
    const draft = await api.call<{ id: string }>("POST", `/v1/w/${wid}/scheduled-posts`, {
      targets: [{ social_account_id: accountId, caption_override: null }],
      asset_ids: [asset.id],
      caption: post.caption,
      first_comment: null,
      publish_at: null,
    });
    await api.call("POST", `/v1/w/${wid}/scheduled-posts/${draft.id}/schedule`, { publish_at: at(post.inHours) });
  }
  const asset = await api.mediaAsset(wid, "monsoon-edit.jpg");
  const draft = await api.call<{ id: string }>("POST", `/v1/w/${wid}/scheduled-posts`, {
    targets: [{ social_account_id: accountId, caption_override: null }],
    asset_ids: [asset.id],
    caption: "The monsoon edit: breathable cotton in five new prints. Tap to shop. #monsoon #cotton",
    first_comment: null,
    publish_at: null,
  });
  return draft.id;
}

async function seedMain(api: Api): Promise<Seeded["main"]> {
  const workspace = await api.newWorkspace(SHOP);
  const account = await api.connectSandbox(workspace.id);
  const wid = workspace.id;

  for (const source of KNOWLEDGE) await api.call("POST", `/v1/w/${wid}/knowledge-sources`, source);
  const automationId = await automation(api, wid, account.id);

  for (const dm of DMS) {
    await api.inbound(wid, { accountId: account.id, kind: "dm", text: dm.text, fromId: dm.fromId });
    await new Promise((r) => setTimeout(r, 400)); // distinct times, so the list order is stable
  }
  for (const comment of COMMENTS) {
    await api.inbound(wid, { accountId: account.id, kind: "comment", text: comment.text, fromId: comment.fromId, fromUsername: comment.username });
  }
  const draftPostId = await posts(api, wid, account.id);

  // Names arrive after a profile fetch, the backfill's posts and conversations after its jobs.
  let list: ConversationItem[] = [];
  await poll(async () => {
    list = (await api.call<Items<ConversationItem>>("GET", `/v1/w/${wid}/conversations?view=all&limit=50`)).items;
    // The sandbox names a contact "customer_" plus the last four characters of its id.
    return DMS.every((dm) => list.some((c) => c.contact.username === contactOf(dm.fromId) && c.contact.display_name));
  }, "the seeded conversations and their contacts' names").toBe(true);

  const conversation = list.find((c) => c.contact.username === contactOf(DRAFT_DM.fromId));
  if (!conversation) throw new Error(`No conversation for ${DRAFT_DM.fromId}`);
  await poll(async () => {
    const detail = await api.call<ConversationDetail>("GET", `/v1/w/${wid}/conversations/${conversation.id}`);
    return Boolean(detail.pending_suggestion);
  }, "the AI draft on the seeded conversation").toBe(true);

  let postId = "";
  await poll(async () => {
    const items = (await api.call<Items<PostItem>>("GET", `/v1/w/${wid}/posts?limit=10`)).items;
    // The post with the most comments.
    postId = [...items].sort((a, b) => (b.comments_count ?? 0) - (a.comments_count ?? 0))[0]?.id ?? "";
    return items.length >= 3;
  }, "the sandbox's backfilled posts").toBe(true);

  return { workspace, account, conversationId: conversation.id, automationId, automationName: AUTOMATION, postId, draftPostId };
}

async function seedBanner(api: Api): Promise<Seeded["banner"]> {
  const workspace = await api.newWorkspace("QA Reconnect");
  const account = await api.connectSandbox(workspace.id);
  const wid = workspace.id;
  await api.inbound(wid, { accountId: account.id, kind: "dm", text: "Hello, are you open today?", fromId: "qa_rc01" });
  let conversationId = "";
  await poll(async () => {
    const items = (await api.call<Items<ConversationItem>>("GET", `/v1/w/${wid}/conversations?view=all&limit=20`)).items;
    conversationId = items.find((c) => c.contact.username === contactOf("qa_rc01"))?.id ?? "";
    return Boolean(conversationId);
  }, "the reconnect workspace's conversation").toBe(true);

  // The sandbox refuses this send as Instagram refuses a revoked token; the account is marked.
  const clientId = randomUUID();
  await api.call(
    "POST",
    `/v1/w/${wid}/conversations/${conversationId}/messages`,
    { client_id: clientId, text: "We open at 10. [sandbox:fail=account_needs_reconnect]" },
    { "Idempotency-Key": `qa-${clientId}` },
  );
  try {
    await poll(async () => {
      const items = (await api.call<Items<AccountItem>>("GET", `/v1/w/${wid}/social-accounts`)).items;
      return items.find((a) => a.id === account.id)?.status;
    }, "the reconnect workspace's account status", 60_000).toBe("needs_reconnect");
  } catch (error) {
    console.warn(`[ui-shots] the sandbox account wasn't marked needs_reconnect; no banner shot (${String(error).split("\n")[0]})`);
    return null;
  }
  return { workspace, account, conversationId };
}

async function stillThere(api: Api, seeded: Seeded): Promise<boolean> {
  try {
    await api.call("GET", `/v1/w/${seeded.main.workspace.id}/social-accounts`);
    return true;
  } catch (error) {
    if (error instanceof ApiFailure) return false;
    throw error;
  }
}

/** The seeded workspaces for this stack: from the cache file, else seeded now. */
export async function seeded(api: Api, cacheFile: string): Promise<Seeded> {
  const stack = stackKey();
  if (existsSync(cacheFile)) {
    const cached = JSON.parse(readFileSync(cacheFile, "utf8")) as Seeded;
    if (cached.version === VERSION && cached.stack === stack && (await stillThere(api, cached))) return cached;
  }
  const started = Date.now();
  const main = await seedMain(api);
  const banner = await seedBanner(api);
  const result: Seeded = { version: VERSION, stack, main, banner };
  mkdirSync(dirname(cacheFile), { recursive: true });
  writeFileSync(cacheFile, JSON.stringify(result, null, 2));
  console.log(`[ui-shots] seeded ${main.workspace.slug} and ${banner?.workspace.slug ?? "no banner workspace"} in ${Math.round((Date.now() - started) / 1000)} s`);
  return result;
}
