import { describe, expect, it } from "vitest";

import { ApiError } from "./api/errors";
import {
  CONNECT_ERRORS,
  completeConnectResult,
  connectResult,
  reconnectBanner,
  sendFailure,
  whatsappConnected,
} from "./copy";
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

describe("finishing an Instagram connect (X-1)", () => {
  const problem = (status: number, code: string) =>
    new ApiError({ type: "about:blank", title: "x", status, code, detail: "from the API" });

  it.each([
    [404, "not_found", "That connection link expired.", true],
    [
      403,
      "forbidden",
      "This Instagram connection was started by someone else, so it wasn't added. To connect your own account, use Connect Instagram.",
      false,
    ],
    [
      422,
      "ig_not_professional",
      "Only Instagram business and creator accounts can connect. Switch the account type in the Instagram app, then try again.",
      true,
    ],
    [409, "account_in_use", "This account is connected to another Social Hood workspace. Disconnect it there first.", false],
    [502, "platform_error", "Instagram didn't respond. Try again.", true],
  ])("%s %s shows its copy", (status, code, message, retry) => {
    expect(completeConnectResult(problem(status, code))).toEqual({ kind: "error", message, retry });
  });

  it("leaves a plan limit to the upgrade dialog and treats anything else as a failed connect", () => {
    expect(completeConnectResult(problem(402, "quota_exceeded"))).toBeNull();
    expect(completeConnectResult(new Error("offline"))?.message).toBe("Instagram didn't respond. Try again.");
  });
});

describe("reconnect banner (F-05)", () => {
  it("names the account", () => {
    expect(reconnectBanner("maple.bakery")).toBe("Reconnect @maple.bakery to keep receiving messages");
    expect(reconnectBanner(null)).toBe("Reconnect your Instagram account to keep receiving messages");
  });
});

describe("send failures (§4.7 error codes)", () => {
  const ig = { platform: "instagram" as const, handle: "maple.bakery" };
  const wa = { platform: "whatsapp" as const, handle: "Maple Bakery" };

  it.each([
    ["reply_window_closed", ig, "Instagram allows replies for 24 hours after the customer's last message.", false],
    [
      "reply_window_closed",
      wa,
      "WhatsApp allows free-form replies for 24 hours after the customer's last message. Send an approved template instead.",
      false,
    ],
    ["account_needs_reconnect", ig, "@maple.bakery needs reconnecting before you can send from it.", false],
    ["recipient_unavailable", ig, "This person can't receive messages right now.", false],
    ["platform_rate_limited", ig, "Instagram is limiting messages from this account. Try again in a few minutes.", true],
    ["platform_unavailable", ig, "Instagram didn't respond.", true],
    ["delivery_unknown", ig, "We couldn't confirm this was delivered. Check the chat in Instagram before retrying.", true],
    ["network", ig, "You're offline. Reconnect to send messages.", true],
  ] as const)("%s shows its copy", (code, context, message, retry) => {
    const failure = sendFailure({ code }, context);
    expect(failure.message).toBe(message);
    expect(failure.retry).toBe(retry);
  });

  it("offers the template picker on WhatsApp and Reconnect for a broken account", () => {
    expect(sendFailure({ code: "reply_window_closed" }, wa).chooseTemplate).toBe(true);
    expect(sendFailure({ code: "account_needs_reconnect" }, ig).reconnect).toBe(true);
  });

  it("quotes the platform's reason and the request id", () => {
    expect(sendFailure({ code: "platform_rejected", message: "Message too long" }, ig).message).toBe(
      "Instagram rejected this: Message too long",
    );
    // The server's stored reason already has the sentence: not doubled.
    expect(sendFailure({ code: "platform_rejected", message: "Instagram rejected this: Upload failed" }, ig).message).toBe(
      "Instagram rejected this: Upload failed",
    );
    expect(sendFailure({ code: "internal", requestId: "01REQ" }, ig).message).toBe(
      "Something went wrong on our side. Try again. If it keeps happening, email support@socialhood.com with code 01REQ.",
    );
    expect(sendFailure({ code: "capability_unavailable", message: "Missing permission" }, ig).message).toBe(
      "@maple.bakery didn't give Social Hood permission for this. Reconnect to allow it.",
    );
    expect(sendFailure({ code: "capability_unavailable" }, wa).message).toBe("WhatsApp doesn't support this.");
  });

  it("falls back to the API's detail for limits and validation", () => {
    expect(sendFailure({ code: "quota_exceeded", message: "Your plan includes 1,000 messages." }, ig).message).toBe(
      "Your plan includes 1,000 messages.",
    );
  });
});

describe("WhatsApp connected toast (F-04)", () => {
  it("names the number", () => {
    expect(whatsappConnected("Maple Bakery", "+91 98765 43210")).toBe("WhatsApp connected: Maple Bakery (+91 98765 43210)");
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
