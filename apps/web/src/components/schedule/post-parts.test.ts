import { describe, expect, it } from "vitest";

import type { SocialAccount } from "@/lib/api/types";
import { account } from "@/test/api";

import { viewLabelOf } from "./post-parts";

const accounts = new Map<string, SocialAccount>([
  ["ig", account({ id: "ig", platform: "instagram" })],
  ["fb", account({ id: "fb", platform: "facebook" })],
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
