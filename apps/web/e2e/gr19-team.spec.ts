import { randomBytes } from "node:crypto";

import type { Page } from "@playwright/test";

import { Api, ApiFailure } from "./support/api";
import { deleteUser, findUsers } from "./support/clerk-admin";
import { SIGN_UP_EMAIL_PREFIX } from "./support/env";
import { expect, test } from "./support/fixtures";

/**
 * GR-19 Team members and roles. The owner invites an agent by email (the stack's fake Clerk
 * invitations keep the email in memory); the agent signs up with that address through Clerk's own
 * form (a +clerk_test address verifies with 424242) and lands in the owner's workspace. They can
 * reply and see the inbox, get 403 from the API on automations and billing, and the UI doesn't
 * offer what they can't do. The sign-up user is deleted afterwards.
 */
type ClerkWindow = { Clerk?: { session?: { getToken: () => Promise<string | null> } | null } };

async function token(page: Page): Promise<string> {
  const value = await page.evaluate(async () => {
    const clerk = (window as unknown as ClerkWindow).Clerk;
    return clerk?.session ? clerk.session.getToken() : null;
  });
  if (!value) throw new Error("The agent isn't signed in");
  return value;
}

test.describe("GR-19 team", () => {
  const email = `${SIGN_UP_EMAIL_PREFIX}team${Date.now().toString(36)}+clerk_test@example.com`;

  test.afterEach(async ({ api }) => {
    for (const user of await findUsers({ emailAddress: email })) {
      await api.deleteUserData(user.id);
      await deleteUser(user.id);
    }
  });

  test("an invited agent replies but cannot manage, and the UI hides it", async ({ browser, page, api, workspace }) => {
    // The owner raises the plan so there is a second seat, then invites from Settings → Members.
    await api.setPlan(workspace.id, "pro");
    await page.goto(`/w/${workspace.slug}/settings/members`);
    await expect(page.getByRole("heading", { name: "Members", level: 1 })).toBeVisible();
    await page.getByRole("button", { name: /Invite/ }).click();
    await page.getByLabel("Email").fill(email);
    await page.getByRole("button", { name: "Send invitation" }).click();
    const pending = page.getByTestId("invitation-row").filter({ hasText: email });
    await expect(pending).toBeVisible();
    await expect(pending).toContainText("Agent");

    // The invited person signs up; /app sends them to the workspace they were invited to.
    // A new context inherits the project's signed-in state; the invited person has none.
    const context = await browser.newContext({ baseURL: page.url().split("/w/")[0], storageState: { cookies: [], origins: [] } });
    const agentPage = await context.newPage();
    const { setupClerkTestingToken } = await import("@clerk/testing/playwright");
    await setupClerkTestingToken({ context });
    await agentPage.goto("/sign-up");
    await agentPage.getByLabel("Email address").fill(email);
    await agentPage.getByLabel("Password", { exact: true }).fill(`E2e-${randomBytes(12).toString("hex")}!`);
    await agentPage.getByRole("button", { name: "Continue", exact: true }).click();
    await agentPage.getByLabel(/verification code/i).first().pressSequentially("424242");
    await expect(agentPage).toHaveURL(new RegExp(`/w/${workspace.slug}/`), { timeout: 30_000 });

    // The UI hides what an agent can't do: no Automations or Knowledge in the nav, no Billing,
    // Members or Audit log among the settings tabs.
    await expect(agentPage.getByRole("link", { name: "Automations" })).toHaveCount(0);
    await expect(agentPage.getByRole("link", { name: "Knowledge" })).toHaveCount(0);
    await agentPage.goto(`/w/${workspace.slug}/settings/notifications`);
    const tabs = agentPage.getByRole("navigation", { name: "Settings" });
    await expect(tabs.getByRole("link", { name: "Notifications" })).toBeVisible();
    for (const hidden of ["Billing and usage", "Members", "Audit log", "Integrations"]) {
      await expect(tabs.getByRole("link", { name: hidden })).toHaveCount(0);
    }

    // The API agrees: 403 on automations and billing, and the agent can read the inbox.
    const agentApi = new Api(() => token(agentPage));
    const refused = async (method: string, path: string, body: unknown) => {
      const failure = await agentApi.call(method, path, body).then(
        () => null,
        (error: unknown) => (error instanceof ApiFailure ? error : Promise.reject(error)),
      );
      expect(failure?.status, `${method} ${path}`).toBe(403);
    };
    await refused("POST", `/v1/w/${workspace.id}/automations`, { name: "Not allowed" });
    await refused("POST", `/v1/w/${workspace.id}/billing/checkout`, { plan: "pro" });
    await refused("GET", `/v1/w/${workspace.id}/members`, undefined);
    await agentApi.call("GET", `/v1/w/${workspace.id}/conversations`);
    const permissions = await agentApi.call<{ role: string; permissions: string[] }>(
      "GET",
      `/v1/w/${workspace.id}/permissions`,
    );
    expect(permissions.role).toBe("agent");
    expect(permissions.permissions).toContain("inbox.reply");

    // Back in the owner's view the invitation is gone and the agent is a member.
    await page.reload();
    const row = page.getByTestId("member-row").filter({ hasText: email });
    await row.first().waitFor({ timeout: 15_000 });
    await expect(row).toContainText("Agent");
    await expect(page.getByTestId("invitation-row").filter({ hasText: email })).toHaveCount(0);

    // The audit log has the invitation and the join.
    await page.goto(`/w/${workspace.slug}/settings/audit`);
    await expect(page.getByTestId("audit-row").filter({ hasText: "Member invited" }).first()).toBeVisible();
    await context.close();
  });
});
