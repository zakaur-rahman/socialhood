import { setupClerkTestingToken } from "@clerk/testing/playwright";
import { test as base, type BrowserContext, type Page } from "@playwright/test";

import { Api, type SandboxAccount, type Workspace } from "./api";
import { AUTH_FILE, BASE_URL } from "./env";

export { expect } from "@playwright/test";

type ClerkWindow = { Clerk?: { loaded?: boolean; session?: { getToken: () => Promise<string | null> } | null } };

// A 1x1 PNG for every remote image (sandbox posts come from picsum.photos, seeded uploads from
// a made-up Cloudinary cloud), so the suite never waits on the network for pictures.
const PIXEL = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
  "base64",
);
const REMOTE_IMAGES = /^https:\/\/(picsum\.photos|fastly\.picsum\.photos|res\.cloudinary\.com|[^/]+\.cdninstagram\.com|[^/]+\.fbcdn\.net)\//;

async function prepare(context: BrowserContext) {
  await setupClerkTestingToken({ context });
  await context.route(REMOTE_IMAGES, (route) => route.fulfill({ status: 200, contentType: "image/png", body: PIXEL }));
  await context.route("**/_next/image?**", (route) => route.fulfill({ status: 200, contentType: "image/png", body: PIXEL }));
}

/** A fresh Clerk session token from a page where the e2e user is signed in. */
async function sessionToken(page: Page): Promise<string> {
  const token = await page.evaluate(async () => {
    const clerk = (window as unknown as ClerkWindow).Clerk;
    return clerk?.session ? clerk.session.getToken() : null;
  });
  if (!token) throw new Error("No Clerk session: the e2e user isn't signed in (see e2e/auth.setup.ts)");
  return token;
}

type TestFixtures = {
  /**
   * A new workspace owned by the e2e user: every test starts clean. It isn't deleted after the
   * test (its jobs may still be running); the launcher drops the whole database after the run.
   */
  workspace: Workspace;
  /** ``workspace`` with a sandbox Instagram account connected (TR-PL-07). */
  sandbox: { workspace: Workspace; account: SandboxAccount };
};

type WorkerFixtures = { api: Api };

export const test = base.extend<TestFixtures, WorkerFixtures>({
  context: async ({ context }, provide) => {
    await prepare(context);
    await provide(context);
  },

  api: [
    async ({ browser }, provide) => {
      const context = await browser.newContext({ storageState: AUTH_FILE, baseURL: BASE_URL, serviceWorkers: "block" });
      await prepare(context);
      const page = await context.newPage();
      await page.goto("/");
      await page.waitForFunction(() => {
        const clerk = (window as unknown as ClerkWindow).Clerk;
        return Boolean(clerk?.loaded && clerk.session);
      });
      await provide(new Api(() => sessionToken(page)));
      await context.close();
    },
    { scope: "worker" },
  ],

  workspace: async ({ api }, provide, testInfo) => {
    await provide(await api.newWorkspace(`E2E ${testInfo.title}`.slice(0, 60)));
  },

  sandbox: async ({ api, workspace }, provide) => {
    const account = await api.connectSandbox(workspace.id);
    await provide({ workspace, account });
  },
});

/** A marker unique to this run and test, for finding the test's own rows. */
export function unique(label: string): string {
  return `${label} ${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
}
