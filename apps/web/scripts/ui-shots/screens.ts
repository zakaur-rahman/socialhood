import { expect, type Locator, type Page } from "@playwright/test";

import type { Seeded } from "./seed";

/**
 * The screens of docs/ui-audit/AGENT_CONTEXT.md §11, in capture order. Each one navigates, opens
 * what it shows and waits for real content (a heading, a row, a draft), never for a fixed time;
 * shots.spec.ts then waits for loading states to end and takes the picture.
 */

export type ShotContext = { page: Page; width: number; phone: boolean; qa?: Seeded };

export type Screen = {
  /** The file name stem: <name>-<width>.png. */
  name: string;
  /** What the picture shows (shots.json, the baseline report). */
  what: string;
  /** Captured signed out (marketing, legal, sign-in). */
  signedOut?: boolean;
  /** Only below 768 px (the phone drawer). */
  phoneOnly?: boolean;
  /** Needs the "QA Reconnect" workspace (skipped when the sandbox couldn't mark the account). */
  needsBanner?: boolean;
  /**
   * The viewport, not the full page: an open overlay, or a layout judged by what fits on screen.
   */
  viewportOnly?: boolean;
  open: (ctx: ShotContext) => Promise<void>;
  /** Undo what open changed (runs even when the shot fails). */
  after?: (ctx: ShotContext) => Promise<void>;
};

function seededOf(ctx: ShotContext): Seeded {
  if (!ctx.qa) throw new Error("This screen needs the seeded workspace");
  return ctx.qa;
}

/** The QA Shop workspace's base path. */
const app = (ctx: ShotContext) => `/w/${seededOf(ctx).main.workspace.slug}`;

/**
 * Navigates without waiting for the load event: every screen waits for its own content, and a slow
 * third-party script (Clerk's) shouldn't fail a shot. A request that hung (a network change on a
 * laptop) leaves the app on its full-page loading skeleton; that gets one reload.
 */
async function go(page: Page, path: string) {
  await page.goto(path, { waitUntil: "domcontentloaded" });
  try {
    await expect(page.locator('[aria-busy="true"][aria-label="Loading"]')).toHaveCount(0, { timeout: 20_000 });
  } catch {
    await page.reload({ waitUntil: "domcontentloaded" });
  }
}

/** The first visible match (phones and desktops render some controls twice, one hidden). */
const shown = (locator: Locator) => locator.filter({ visible: true }).first();

async function heading(page: Page, name?: string | RegExp) {
  await expect(shown(page.getByRole("heading", { level: 1, ...(name ? { name } : {}) }))).toBeVisible();
}

async function settingsPage(ctx: ShotContext, tab: string) {
  await go(ctx.page, `${app(ctx)}/settings/${tab}`);
  await heading(ctx.page);
}

async function schedule(ctx: ShotContext, view: "week" | "month" | "list") {
  // The view is remembered per browser (SchedulePage's VIEW_KEY); set it before the page reads it.
  await ctx.page.addInitScript((value) => window.localStorage.setItem("socialhood:schedule-view", value), view);
  await go(ctx.page, `${app(ctx)}/schedule`);
  await heading(ctx.page, "Schedule");
}

/**
 * Marketing sections reveal as they scroll into view. Scroll through once so a full-page shot
 * shows every section, then back to the top.
 */
async function revealAll(page: Page) {
  const viewport = page.viewportSize() ?? { width: 1280, height: 800 };
  const total = await page.evaluate(() => document.documentElement.scrollHeight);
  for (let y = 0; y < total; y += Math.round(viewport.height * 0.75)) {
    await page.evaluate((top) => window.scrollTo(0, top), y);
    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  }
  await page.evaluate(() => window.scrollTo(0, 0));
}

async function marketingPage(page: Page, path: string) {
  await go(page, path);
  await heading(page);
  await revealAll(page);
}

/** The account's AI mode segment on Settings › AI, by label. */
const aiMode = (page: Page, label: string) =>
  page.getByRole("list", { name: "AI mode per account" }).getByRole("radio", { name: new RegExp(`^${label}`) }).first();

export const SCREENS: Screen[] = [
  {
    name: "home",
    what: "Home: greeting, range, metric tiles, priority queue, account health and the first-run checklist",
    open: async (ctx) => {
      await go(ctx.page, `${app(ctx)}/home`);
      await heading(ctx.page);
    },
  },
  {
    name: "inbox-list",
    what: "Inbox: the conversation list (DMs, comment-to-DM threads, the backfill) with filters; no conversation open",
    open: async (ctx) => {
      await go(ctx.page, `${app(ctx)}/inbox`);
      await expect(shown(ctx.page.getByRole("list", { name: "Conversations" }).getByRole("link"))).toBeVisible();
    },
  },
  {
    name: "conversation",
    what: "A conversation with the AI draft waiting above the composer (list and details beside it on wide screens)",
    open: async (ctx) => {
      await go(ctx.page, `${app(ctx)}/inbox/${seededOf(ctx).main.conversationId}`);
      await expect(shown(ctx.page.getByText("Thanks for asking! Yes, it's in stock"))).toBeVisible({ timeout: 60_000 });
    },
  },
  {
    name: "comments",
    what: "Comments: the posts grid with comment counts",
    open: async (ctx) => {
      await go(ctx.page, `${app(ctx)}/comments`);
      await expect(shown(ctx.page.getByTestId("posts-grid").getByRole("link"))).toBeVisible();
    },
  },
  {
    name: "post-comments",
    what: "Comments › a post: the post, its summary and its comments",
    open: async (ctx) => {
      await go(ctx.page, `${app(ctx)}/comments/${seededOf(ctx).main.postId}`);
      await heading(ctx.page);
    },
  },
  {
    name: "automations",
    what: "Automations: the 7-day stats, one active comment-to-DM automation and one draft",
    open: async (ctx) => {
      await go(ctx.page, `${app(ctx)}/automations`);
      await expect(shown(ctx.page.getByRole("switch", { name: `Active: ${seededOf(ctx).main.automationName}` }))).toBeVisible();
    },
  },
  {
    name: "automation-editor",
    what: "The automation editor on the active automation: steps, preview, test, runs and stats",
    open: async (ctx) => {
      const { automationId, automationName } = seededOf(ctx).main;
      await go(ctx.page, `${app(ctx)}/automations/${automationId}`);
      await expect(ctx.page.getByRole("textbox", { name: "Automation name" })).toHaveValue(automationName);
    },
  },
  {
    name: "template-gallery",
    what: "Automations › New automation: the template gallery dialog",
    viewportOnly: true,
    open: async (ctx) => {
      await go(ctx.page, `${app(ctx)}/automations`);
      await shown(ctx.page.getByRole("button", { name: "New automation" })).click();
      const gallery = ctx.page.getByRole("dialog", { name: "New automation" });
      await expect(shown(gallery.getByRole("button", { name: /^Use template:/ }))).toBeVisible();
    },
  },
  {
    name: "schedule-week",
    what: "Schedule, week view (below 768 px the app shows the agenda instead)",
    open: (ctx) => schedule(ctx, "week"),
  },
  {
    name: "schedule-month",
    what: "Schedule, month view (below 768 px the app shows the agenda of the month instead)",
    open: (ctx) => schedule(ctx, "month"),
  },
  {
    name: "schedule-list",
    what: "Schedule, list view: scheduled posts and drafts",
    open: (ctx) => schedule(ctx, "list"),
  },
  {
    name: "composer",
    what: "The post composer on a draft with a photo and a caption: accounts, media, caption, when, checklist, preview",
    open: async (ctx) => {
      await go(ctx.page, `${app(ctx)}/schedule/${seededOf(ctx).main.draftPostId}`);
      await heading(ctx.page, "Post");
      await expect(shown(ctx.page.getByRole("textbox", { name: "Caption" }))).toHaveValue(/monsoon edit/);
    },
  },
  {
    name: "knowledge",
    what: "Knowledge: sources (two FAQs, two texts), brand voice, gaps and the test box",
    open: async (ctx) => {
      await go(ctx.page, `${app(ctx)}/knowledge`);
      await heading(ctx.page);
      await expect(shown(ctx.page.getByText("How long does delivery take?"))).toBeVisible();
    },
  },
  {
    name: "ask-panel",
    what: "The Ask Social Hood panel open over Home (no thread yet)",
    viewportOnly: true,
    open: async (ctx) => {
      await go(ctx.page, `${app(ctx)}/home`);
      await heading(ctx.page);
      await shown(ctx.page.getByRole("button", { name: "Ask Social Hood" })).click();
      await expect(ctx.page.getByRole("dialog", { name: "Ask Social Hood" })).toBeVisible();
    },
  },
  {
    name: "ask-page",
    what: "The Ask Social Hood page (no thread yet)",
    open: async (ctx) => {
      await go(ctx.page, `${app(ctx)}/ask`);
      await heading(ctx.page, "Ask Social Hood");
    },
  },
  {
    name: "settings-connections",
    what: "Settings › Connections: the connected sandbox Instagram account",
    open: async (ctx) => {
      await settingsPage(ctx, "connections");
      await expect(shown(ctx.page.getByText("Connected", { exact: true }))).toBeVisible();
    },
  },
  {
    name: "settings-ai",
    what: "Settings › AI: AI mode per account (Auto locked on Free), rules and phrases",
    open: async (ctx) => {
      await settingsPage(ctx, "ai");
      await expect(ctx.page.getByRole("list", { name: "AI mode per account" })).toBeVisible();
    },
  },
  {
    name: "settings-workspace",
    what: "Settings › Workspace: name, time zone, members, danger zone",
    open: (ctx) => settingsPage(ctx, "workspace"),
  },
  {
    name: "settings-notifications",
    what: "Settings › Notifications: email and push preferences",
    open: (ctx) => settingsPage(ctx, "notifications"),
  },
  {
    name: "settings-billing",
    what: "Settings › Billing: the Free plan, usage meters, plan cards and payment history",
    open: async (ctx) => {
      await settingsPage(ctx, "billing");
      await expect(ctx.page.getByRole("region", { name: "Free" })).toBeVisible();
    },
  },
  {
    name: "settings-agent",
    what: "Settings › Agent: Ask Social Hood's settings and run history",
    open: (ctx) => settingsPage(ctx, "agent"),
  },
  {
    name: "upgrade-dialog",
    what: "The upgrade dialog, opened by Settings › AI's \"Upgrade for Auto\"",
    viewportOnly: true,
    open: async (ctx) => {
      await settingsPage(ctx, "ai");
      await shown(ctx.page.getByRole("button", { name: "Upgrade for Auto" })).click();
      const dialog = ctx.page.getByTestId("upgrade-dialog");
      await expect(dialog).toContainText("₹");
      // The checkout button waits for the workspace's billing state (trial or not).
      await expect(dialog.getByRole("button", { name: /Start .*trial|Upgrade to Pro/ })).toBeEnabled();
    },
  },
  {
    name: "menu-open",
    what: "An open menu: an automation row's ⋯ menu on Automations",
    viewportOnly: true,
    open: async (ctx) => {
      await go(ctx.page, `${app(ctx)}/automations`);
      await shown(ctx.page.getByRole("button", { name: `More actions for ${seededOf(ctx).main.automationName}` })).click();
      await expect(ctx.page.getByRole("menu")).toBeVisible();
    },
  },
  {
    name: "dialog-open",
    what: "An open dialog: Settings › Connections' \"Disconnect @account?\" confirmation",
    viewportOnly: true,
    open: async (ctx) => {
      await settingsPage(ctx, "connections");
      await shown(ctx.page.getByRole("button", { name: "Disconnect", exact: true })).click();
      await expect(ctx.page.getByRole("alertdialog")).toBeVisible();
    },
  },
  {
    name: "phone-drawer",
    what: "The phone navigation drawer, open over Home",
    phoneOnly: true,
    viewportOnly: true,
    open: async (ctx) => {
      await go(ctx.page, `${app(ctx)}/home`);
      await heading(ctx.page);
      await ctx.page.getByRole("button", { name: "Open menu" }).click();
      await expect(ctx.page.getByRole("dialog", { name: "Menu" })).toBeVisible();
    },
  },
  {
    name: "toast",
    what: "A toast: Settings › AI after switching the account's AI mode (switched back afterwards)",
    viewportOnly: true,
    open: async (ctx) => {
      await settingsPage(ctx, "ai");
      const off = aiMode(ctx.page, "Off");
      const target = (await off.getAttribute("aria-checked")) === "true" ? aiMode(ctx.page, "Suggest") : off;
      await target.click();
      await expect(ctx.page.locator("[data-sonner-toast]").first()).toBeVisible();
    },
    after: async (ctx) => {
      const suggest = aiMode(ctx.page, "Suggest");
      if ((await suggest.getAttribute("aria-checked")) !== "true") {
        await suggest.click();
        await expect(suggest).toHaveAttribute("aria-checked", "true");
      }
    },
  },
  {
    name: "banner",
    what: "An app banner: Home of the \"QA Reconnect\" workspace, whose account needs reconnecting",
    needsBanner: true,
    open: async (ctx) => {
      const banner = seededOf(ctx).banner;
      if (!banner) throw new Error("No reconnect workspace");
      await go(ctx.page, `/w/${banner.workspace.slug}/home`);
      await heading(ctx.page);
      await expect(ctx.page.locator('[data-banner^="reconnect:"]')).toBeVisible();
    },
  },
  {
    name: "banner-inbox",
    what: "The same workspace's conversation with the banner above the inbox (UI-ISS-020: where the composer lands)",
    needsBanner: true,
    viewportOnly: true,
    open: async (ctx) => {
      const banner = seededOf(ctx).banner;
      if (!banner) throw new Error("No reconnect workspace");
      await go(ctx.page, `/w/${banner.workspace.slug}/inbox/${banner.conversationId}`);
      await expect(ctx.page.locator('[data-banner^="reconnect:"]')).toBeVisible();
      await expect(shown(ctx.page.getByText("Hello, are you open today?"))).toBeVisible();
    },
  },
  {
    name: "landing",
    what: "The landing page (/), signed out, every section revealed",
    signedOut: true,
    open: (ctx) => marketingPage(ctx.page, "/"),
  },
  {
    name: "privacy",
    what: "The privacy policy (/privacy), signed out",
    signedOut: true,
    open: (ctx) => marketingPage(ctx.page, "/privacy"),
  },
  {
    name: "data-deletion",
    what: "Data deletion instructions (/data-deletion), signed out",
    signedOut: true,
    open: (ctx) => marketingPage(ctx.page, "/data-deletion"),
  },
  {
    name: "sign-in",
    what: "Sign in (Clerk's form with the app's appearance), signed out",
    signedOut: true,
    open: async (ctx) => {
      await go(ctx.page, "/sign-in");
      await expect(ctx.page.locator("input[name=identifier]")).toBeVisible();
    },
  },
];
