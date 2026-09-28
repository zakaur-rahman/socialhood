import { describe, expect, it } from "vitest";

import { CONNECT_ERRORS, connectResult, reconnectBanner } from "./copy";
import { relativeTime } from "./time";

function result(query: string, username?: string) {
  return connectResult(new URLSearchParams(query), username);
}

describe("connect results (F-03, §4.7)", () => {
  it("names the connected account", () => {
    expect(result("connected=instagram", "maple.bakery")).toEqual({
      kind: "success",
      message: "Instagram connected: @maple.bakery",
    });
    expect(result("connected=instagram")?.message).toBe("Instagram connected");
  });

  it.each([
    ["access_denied", "Connection cancelled", false],
    ["state_invalid", "That connection link expired.", true],
    [
      "ig_not_professional",
      "Only Instagram business and creator accounts can connect. Switch the account type in the Instagram app, then try again.",
      true,
    ],
    [
      "account_in_use",
      "This account is connected to another Social Hood workspace. Disconnect it there first.",
      false,
    ],
    ["connect_failed", "Instagram didn't respond. Try again.", true],
    ["quota_exceeded&limit=1", "Your plan includes 1 Instagram account.", false],
    ["quota_exceeded&limit=3", "Your plan includes 3 Instagram accounts.", false],
  ])("error=%s shows its copy", (query, message, retry) => {
    expect(result(`error=${query}`)).toEqual({ kind: "error", message, retry });
  });

  it("covers every code the callback sends", () => {
    for (const code of CONNECT_ERRORS) {
      const shown = result(`error=${code}`);
      expect(shown?.kind).toBe("error");
      expect(shown?.message).not.toBe("");
    }
  });

  it("treats an unknown code as a failed connect and no parameters as nothing", () => {
    expect(result("error=something_new")?.message).toBe("Instagram didn't respond. Try again.");
    expect(result("")).toBeNull();
  });
});

describe("reconnect banner (F-05)", () => {
  it("names the account", () => {
    expect(reconnectBanner("maple.bakery")).toBe("Reconnect @maple.bakery to keep receiving messages");
    expect(reconnectBanner(null)).toBe("Reconnect your Instagram account to keep receiving messages");
  });
});

describe("relativeTime", () => {
  const now = new Date("2026-09-28T12:00:00Z");
  it.each([
    ["2026-09-28T11:59:30Z", "now"],
    ["2026-09-28T11:55:00Z", "5m"],
    ["2026-09-28T09:00:00Z", "3h"],
    ["2026-09-26T12:00:00Z", "2d"],
  ])("%s → %s", (iso, expected) => {
    expect(relativeTime(iso, now)).toBe(expected);
  });
});
