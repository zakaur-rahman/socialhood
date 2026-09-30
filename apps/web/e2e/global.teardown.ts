import { deleteUser, usersWithEmailPrefix } from "./support/clerk-admin";
import { SIGN_UP_EMAIL_PREFIX } from "./support/env";

/**
 * After the suite: no signed-up user stays in Clerk (F-01 deletes its own; this catches a run
 * that stopped halfway). The dedicated e2e user stays for the next run. The database is the
 * launcher's to drop.
 */
export default async function globalTeardown() {
  for (const user of await usersWithEmailPrefix(SIGN_UP_EMAIL_PREFIX)) await deleteUser(user.id);
}
