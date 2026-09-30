import { randomBytes } from "node:crypto";

import { deleteUser, findUsers } from "./support/clerk-admin";
import { SIGN_UP_EMAIL_PREFIX } from "./support/env";
import { expect, test } from "./support/fixtures";

/**
 * F-01 Sign up and first run, through Clerk's own sign-up form on the development instance: a
 * +clerk_test address verifies with the code 424242, and the testing token (support/fixtures)
 * skips bot protection. The new user is deleted from Clerk and the database afterwards.
 */
test.use({ storageState: { cookies: [], origins: [] } });

test.describe("F-01 sign up and first run", () => {
  const email = `${SIGN_UP_EMAIL_PREFIX}${Date.now().toString(36)}+clerk_test@example.com`;

  test.afterEach(async ({ api }) => {
    for (const user of await findUsers({ emailAddress: email })) {
      await api.deleteUserData(user.id);
      await deleteUser(user.id);
    }
  });

  test("a new account lands on Home with the setup checklist", async ({ page }) => {
    await page.goto("/sign-up");
    await page.getByLabel("Email address").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(`E2e-${randomBytes(12).toString("hex")}!`);
    await page.getByRole("button", { name: "Continue", exact: true }).click();

    // Email verification: Clerk's test addresses take 424242.
    await expect(page.getByText(/verify your email/i).first()).toBeVisible();
    await page.getByLabel(/verification code/i).first().pressSequentially("424242");

    // /app provisions the user, a workspace and the Free plan (TR-AUTH-03), then sends the user
    // to Home because nothing is connected yet.
    await expect(page).toHaveURL(/\/w\/[^/]+\/home$/, { timeout: 30_000 });
    // No name on the Clerk account: the workspace is "My workspace".
    await expect(page.getByRole("button", { name: "Workspace menu: My workspace" })).toBeVisible();

    // FR-ACC-04: the four steps, none done, the first one open with its button.
    const checklist = page.getByRole("region", { name: "Get set up" });
    await expect(checklist).toContainText("0 of 4 done");
    const steps = checklist.getByRole("listitem");
    await expect(steps).toHaveText([/Connect an account/, /Add knowledge/, /Choose an AI mode/, /Create an automation/]);
    for (const step of await steps.all()) await expect(step.getByRole("img", { name: "Not done" })).toBeVisible();
    const connect = steps.first().getByRole("link", { name: "Connect an account" });
    await expect(connect).toBeVisible();
    await expect(steps.nth(1).getByRole("link")).toHaveCount(0);

    await connect.click();
    await expect(page).toHaveURL(/\/w\/[^/]+\/settings\/connections$/);
    await expect(page.getByRole("heading", { name: "Connections", level: 1 })).toBeVisible();
  });
});
