import { describe, expect, it } from "vitest";

import { sendFailure } from "@/lib/copy";

import { PLATFORM_LABEL, platformContactUrl } from "./format";

describe("inbox helpers for a Facebook Page (GR-29)", () => {
  it("labels the platform", () => {
    expect(PLATFORM_LABEL.facebook).toBe("Facebook");
  });

  it("opens a Messenger person in the Page's inbox, since they have no public profile", () => {
    expect(platformContactUrl("facebook", { username: null, platform_user_id: "7001234567890123" })).toBe(
      "https://business.facebook.com/latest/inbox/messenger",
    );
    expect(platformContactUrl("instagram", { username: "priya", platform_user_id: "1" })).toBe("https://www.instagram.com/priya/");
  });

  it("the closed window says Facebook, with the 24 hours", () => {
    const failure = sendFailure({ code: "reply_window_closed" }, { platform: "facebook", handle: "maplebakery" });
    expect(failure.message).toBe("Facebook allows replies for 24 hours after the customer's last message.");
    expect(failure).toMatchObject({ retry: false });
    expect(sendFailure({ code: "reply_window_closed" }, { platform: "instagram" }).message).toBe(
      "Instagram allows replies for 24 hours after the customer's last message.",
    );
  });

  it("names the Page with an @ and Facebook in the other reasons", () => {
    expect(sendFailure({ code: "account_needs_reconnect" }, { platform: "facebook", handle: "maplebakery" }).message).toBe(
      "@maplebakery needs reconnecting before you can send from it.",
    );
    expect(sendFailure({ code: "platform_unavailable" }, { platform: "facebook" }).message).toBe("Facebook didn't respond.");
    expect(sendFailure({ code: "capability_unavailable" }, { platform: "facebook" }).message).toBe("Facebook doesn't support this.");
  });
});
