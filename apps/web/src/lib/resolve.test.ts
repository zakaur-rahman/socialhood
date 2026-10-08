import { describe, expect, it } from "vitest";

import { account } from "@/test/api";

import { appLink, resolveDestination } from "./resolve";

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
