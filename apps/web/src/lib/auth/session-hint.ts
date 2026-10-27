/**
 * Whether the browser looks signed in, without Clerk's client (C-148).
 *
 * Clerk keeps `__client_uat` (and, from Core 2, `__client_uat_<suffix>`) on the site's registrable
 * domain, so amplychat.com sees the cookie dashboard.amplychat.com's sign-in set. Its value is the
 * time of the client's last update in seconds, and "0" once signed out. It is only a hint for
 * which button the public header shows: a stale one leads to the dashboard, which asks for sign-in.
 */
const CLIENT_UAT = /^__client_uat(?:_[A-Za-z0-9_-]+)?$/;

export function signedInHint(cookie: string): boolean {
  return cookie.split(";").some((pair) => {
    const at = pair.indexOf("=");
    if (at < 0) return false;
    const name = pair.slice(0, at).trim();
    const value = Number(pair.slice(at + 1).trim());
    return CLIENT_UAT.test(name) && Number.isFinite(value) && value > 0;
  });
}
