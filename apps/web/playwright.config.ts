import { defineConfig, devices } from "@playwright/test";

import { AUTH_FILE, BASE_URL } from "./e2e/support/env";

/**
 * T9.4, TR-TEST-01: the end-to-end suite for F-01, F-06, F-07, F-08, F-11, F-13 and F-15 against
 * the sandbox stack. Run it through the launcher, which starts and stops the stack:
 * `pnpm e2e` from the repository root (scripts/e2e-stack.mjs). See docs/testing-e2e.md.
 */
export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results/e2e",
  globalSetup: "./e2e/global.setup.ts",
  globalTeardown: "./e2e/global.teardown.ts",
  timeout: 120_000,
  // Most assertions wait on the worker (webhook, analysis, suggestion, send, publish jobs).
  expect: { timeout: 30_000 },
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : 3,
  reporter: process.env.CI
    ? [["list"], ["github"], ["html", { open: "never", outputFolder: "playwright-report" }]]
    : [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  use: {
    baseURL: BASE_URL,
    locale: "en-GB",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    // The production build registers a service worker (TR-FE-09); it would cache between tests.
    serviceWorkers: "block",
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },
  projects: [
    { name: "setup", testMatch: /auth\.setup\.ts/ },
    {
      name: "chromium",
      testMatch: /.*\.spec\.ts/,
      dependencies: ["setup"],
      use: { ...devices["Desktop Chrome"], storageState: AUTH_FILE },
    },
  ],
});
