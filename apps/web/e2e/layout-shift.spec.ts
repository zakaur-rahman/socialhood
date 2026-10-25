import type { Page } from "@playwright/test";

import { expect, test } from "./support/fixtures";
import { requireStack } from "./support/env";

/**
 * Polish B (C-136): cumulative layout shift while the main pages load. For each page the spec
 * records `layout-shift` entries (without recent input) from navigation until the page is idle
 * (the network is quiet and no `aria-busy` region is left), with the API slowed a little so the
 * skeletons really show, and fails above 0.1 (Google's "good" CLS). It runs on a desktop and a
 * phone viewport, with a few contacts, so lists have rows.
 */
const LIMIT = 0.1;
const API_DELAY_MS = 350;

const PAGES = [
  "home",
  "inbox",
  "comments",
  "contacts",
  "leads",
  "orders",
  "products",
  "schedule",
  "automations",
  "sequences",
  "broadcasts",
  "knowledge",
  "ask",
  "reports",
  "settings/workspace",
  "settings/connections",
  "settings/members",
  "settings/billing",
  "settings/ai",
  "settings/agent",
  "settings/hours",
  "settings/replies",
  "settings/integrations",
  "settings/notifications",
  "settings/widget",
  "settings/activity",
  "settings/appearance",
] as const;

const VIEWPORTS = [
  { name: "desktop", size: { width: 1280, height: 800 } },
  { name: "phone", size: { width: 390, height: 844 } },
];

async function startRecording(page: Page) {
  await page.addInitScript(() => {
    const w = window as unknown as { __cls: number };
    w.__cls = 0;
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries() as unknown as Array<{ value: number; hadRecentInput: boolean }>) {
        if (!entry.hadRecentInput) w.__cls += entry.value;
      }
    }).observe({ type: "layout-shift", buffered: true });
  });
}

test.describe("layout shift while pages load", () => {
  for (const viewport of VIEWPORTS) {
    test(`CLS stays under ${LIMIT} on the main pages (${viewport.name})`, async ({ page, api, sandbox }) => {
      test.setTimeout(10 * 60_000);
      const { workspace, account } = sandbox;
      await page.setViewportSize(viewport.size);
      for (const name of ["asha", "bina", "chetan"]) {
        const fromUsername = `e2e_cls_${name}`;
        await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: "hi there", fromId: fromUsername, fromUsername });
      }
      const apiUrl = requireStack().E2E_API_URL;
      await page.route(
        (url) => url.href.startsWith(`${apiUrl}/v1/`),
        async (route) => {
          await new Promise((resolve) => setTimeout(resolve, API_DELAY_MS));
          await route.continue();
        },
      );
      await startRecording(page);

      const results: Record<string, number> = {};
      for (const path of PAGES) {
        await page.goto("about:blank");
        await page.evaluate(() => undefined);
        await page.goto(`/w/${workspace.slug}/${path}`, { waitUntil: "commit" });
        await page.waitForLoadState("networkidle");
        // Skeletons gone: no region is still marked busy.
        await expect(page.locator('[aria-busy="true"]')).toHaveCount(0, { timeout: 20_000 });
        await page.waitForTimeout(600);
        results[path] = await page.evaluate(() => (window as unknown as { __cls: number }).__cls);
      }
      console.log(`CLS (${viewport.name}):`, JSON.stringify(results, null, 1));
      const over = Object.entries(results).filter(([, value]) => value > LIMIT);
      expect(over, `pages over ${LIMIT}`).toEqual([]);
    });
  }
});
