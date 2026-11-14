import { describe, expect, it } from "vitest";

import type { SocialAccount } from "@/lib/api/types";
import { account } from "@/test/api";

import { permalinkOf, viewLabelOf } from "./post-parts";

const accounts = new Map<string, SocialAccount>([
  ["ig", account({ id: "ig", platform: "instagram" })],
  ["fb", account({ id: "fb", platform: "facebook" })],
  ["yt", account({ id: "yt", platform: "youtube" })],
]);
const post = (id: string) => ({ targets: [{ social_account_id: id, status: "published" as const, permalink: "https://example.com/p" }] });

describe("the published-post link label (C-135)", () => {
  it("follows the platform of the account the link is from", () => {
    expect(viewLabelOf(post("fb"), accounts)).toBe("View on Facebook");
    expect(viewLabelOf(post("ig"), accounts)).toBe("View on Instagram");
  });

  it("says Instagram when the account is not known", () => {
    expect(viewLabelOf(post("gone"), accounts)).toBe("View on Instagram");
  });
});

describe("a YouTube video's link (C-195)", () => {
  it("comes from the video's state and says YouTube", () => {
    const video = {
      targets: [
        {
          social_account_id: "yt",
          status: "published" as const,
          youtube: { route: "direct" as const, state: "published" as const, video_id: "v1", upload_expires_at: null, url: "https://www.youtube.com/watch?v=v1" },
        },
      ],
    };
    expect(permalinkOf(video)).toBe("https://www.youtube.com/watch?v=v1");
    expect(viewLabelOf(video, accounts)).toBe("View on YouTube");
  });
});
