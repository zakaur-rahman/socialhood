import { describe, expect, it } from "vitest";

import { account } from "@/test/api";

import { PRO_SIGN_UP_PATH, appLink, resolveDestination } from "./resolve";

describe("/app resolver (F-01, F-02)", () => {
  it("opens a page a link from outside the app asked for, without waiting for the accounts (UI-ISS-110)", () => {
    expect(appLink("settings/notifications")).toBe("/app?next=settings/notifications");
    expect(resolveDestination("maple", undefined, null, "settings/notifications")).toBe("/w/maple/settings/notifications");
    expect(resolveDestination("maple", [account()], null, "settings/notifications")).toBe("/w/maple/settings/notifications");
  });

  it("ignores any other next page: the parameter can't send anyone elsewhere", () => {
    for (const next of ["//evil.example", "https://evil.example", "settings/billing", "../app", ""]) {
      expect(resolveDestination("maple", [account()], null, next)).toBe("/w/maple/inbox");
    }
  });

  it("keeps the Pro intent from the pricing page through sign-up to Home (UI-ISS-073)", () => {
    // Sign-up lands on /app?plan=pro, and /app sends the new owner to Home to be offered the trial.
    expect(new URL(PRO_SIGN_UP_PATH, "https://x.example").searchParams.get("redirect_url")).toBe("/app?plan=pro");
    expect(resolveDestination("maple", undefined, null, null, "pro")).toBe("/w/maple/home?plan=pro");
    expect(resolveDestination("maple", [account()], null, null, "pro")).toBe("/w/maple/home?plan=pro");
    // Any other plan value is ignored.
    expect(resolveDestination("maple", [account()], null, null, "max")).toBe("/w/maple/inbox");
    // A failed connect link still wins.
    expect(resolveDestination("maple", [], "state_invalid", null, "pro")).toBe("/w/maple/settings/connections?error=state_invalid");
  });

  it("opens the inbox once an account is connected", () => {
    expect(resolveDestination("maple", [account()], null)).toBe("/w/maple/inbox");
    expect(resolveDestination("maple", [account({ status: "needs_reconnect" })], null)).toBe("/w/maple/inbox");
  });

  it("opens Home while nothing is connected", () => {
    expect(resolveDestination("maple", [], null)).toBe("/w/maple/home");
    expect(resolveDestination("maple", [account({ status: "disconnected" })], null)).toBe("/w/maple/home");
  });

  it("waits for the accounts, except for an expired connect link", () => {
    expect(resolveDestination("maple", undefined, null)).toBeNull();
    expect(resolveDestination("maple", undefined, "state_invalid")).toBe(
      "/w/maple/settings/connections?error=state_invalid",
    );
  });
});
