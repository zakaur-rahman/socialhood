import { defineConfig, devices } from "@playwright/test";

import { AUTH_FILE, BASE_URL } from "../../e2e/support/env";

/**
 * The landing page's product screenshots (public/marketing/*.webp), taken from the real app on
 * the isolated e2e stack with sandbox data. See README.md in this folder.
 *
 *   node scripts/e2e-stack.mjs --serve        # repository root, with your own ports and database
 *   pnpm shots:marketing                      # apps/web
 */
export default defineConfig({
  testDir: ".",
  outputDir: "../../test-results/marketing-shots",
  globalSetup: "../../e2e/global.setup.ts",
  timeout: 240_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: BASE_URL,
    locale: "en-GB",
    timezoneId: "Asia/Kolkata",
    colorScheme: "dark",
    serviceWorkers: "block",
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },
  projects: [
    // The e2e suite's sign-in, reused: it saves the e2e user's browser state.
    { name: "setup", testDir: "../../e2e", testMatch: /auth\.setup\.ts/ },
    {
      name: "shots",
      testMatch: /capture\.spec\.ts/,
      dependencies: ["setup"],
      use: {
        ...devices["Desktop Chrome"],
        storageState: AUTH_FILE,
        viewport: { width: 1440, height: 900 },
        deviceScaleFactor: 2,
      },
    },
  ],
});
