import { clerkSetup } from "@clerk/testing/playwright";

import { deleteUser, ensureUser, usersWithEmailPrefix } from "./support/clerk-admin";
import { E2E_USER, SIGN_UP_EMAIL_PREFIX, requireStack } from "./support/env";

/**
 * Before the suite: the stack must be up; Clerk hands out a testing token (so sign-in and sign-up
 * skip bot protection); the dedicated e2e user exists on the development instance (created once,
 * reused after); users an earlier F-01 run signed up and left behind are deleted.
 */
export default async function globalSetup() {
  requireStack();
  // Keys from the environment (the launcher, CI) or apps/web/.env.local (a local --serve run).
  await clerkSetup();
  await ensureUser(E2E_USER);
  for (const user of await usersWithEmailPrefix(SIGN_UP_EMAIL_PREFIX)) await deleteUser(user.id);
}
