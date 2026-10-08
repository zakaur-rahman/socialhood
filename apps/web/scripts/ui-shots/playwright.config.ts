import { defineConfig, devices } from "@playwright/test";

import { AUTH_FILE, BASE_URL } from "../../e2e/support/env";
import { outDir, reducedMotion } from "./options";

outDir(); // fails before sign-in when UI_SHOTS_OUT is missing or inside the repository

/**
 * Visual QA screenshots and axe (UI-019 and every later UI task): the screens in
 * docs/ui-audit/AGENT_CONTEXT.md §11 at 375, 768, 1280 and 1536 px, from the real app on the
 * isolated e2e stack with sandbox data. See README.md in this folder.
 *
 *   node scripts/e2e-stack.mjs --serve                  # repository root, your own ports and database
 *   UI_SHOTS_OUT=/abs/path/outside/repo pnpm shots:ui   # apps/web
 */
export default defineConfig({
  testDir: ".",
  outputDir: "../../test-results/ui-shots",
  globalSetup: "../../e2e/global.setup.ts",
  globalTeardown: "./report.ts",
  // The first test also seeds the workspaces (about a minute); the others take seconds.
  timeout: 120_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  retries: 2,
  reporter: [["list"]],
  use: {
    baseURL: BASE_URL,
    locale: "en-GB",
    timezoneId: "Asia/Kolkata",
    colorScheme: "dark",
    reducedMotion: reducedMotion(),
    // The production build registers a service worker; it would cache between tests.
    serviceWorkers: "block",
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },
  projects: [
    // The e2e suite's sign-in, reused: it saves the e2e user's browser state.
    { name: "setup", testDir: "../../e2e", testMatch: /auth\.setup\.ts/ },
    {
      name: "ui-shots",
      testMatch: /shots\.spec\.ts/,
      dependencies: ["setup"],
      // Viewport, touch and the scale factor are set per width in shots.spec.ts.
      use: { ...devices["Desktop Chrome"], storageState: AUTH_FILE },
    },
  ],
});
