import { describe, expect, it } from "vitest";

import { account } from "@/test/api";

import { resolveDestination } from "./resolve";

describe("/app resolver (F-01, F-02)", () => {
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
