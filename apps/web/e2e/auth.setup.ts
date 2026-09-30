import { clerk, setupClerkTestingToken } from "@clerk/testing/playwright";
import { expect, test as setup } from "@playwright/test";

import { AUTH_FILE, E2E_USER } from "./support/env";

/**
 * Signs the dedicated e2e user in once (a Clerk sign-in token, so no password or email code) and
 * saves the browser state every other test starts from. Opening /app provisions the user and
 * its first workspace in the API (TR-AUTH-03).
 */
setup("sign in the e2e user", async ({ page }) => {
  await setupClerkTestingToken({ page });
  await page.goto("/sign-in");
  await clerk.signIn({ page, emailAddress: E2E_USER.email });
  await page.goto("/app");
  await expect(page).toHaveURL(/\/w\/[^/]+\/(home|inbox)/, { timeout: 30_000 });
  await page.context().storageState({ path: AUTH_FILE });
});
