import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { StoryMention } from "@/lib/api/types";
import { account, json, renderWithApi } from "@/test/api";

import { MentionsPage } from "./MentionsPage";

function mention(values: Partial<StoryMention> = {}): StoryMention {
  return {
    id: "m1",
    social_account_id: "a1",
    mentioned_at: "2026-10-24T09:00:00Z",
    contact: { id: "p1", display_name: "Priya Nair", username: "priya.styles", profile_picture_url: null },
    conversation_id: "c1",
    link_url: "https://lookaside.fbsbx.com/story?asset_id=1",
    link_expires_at: "2026-10-25T09:00:00Z",
    ...values,
  };
}

function setup(items: StoryMention[], total = items.length) {
  return renderWithApi(<MentionsPage />, {
    handlers: {
      "GET /v1/w/:wid/social-accounts": () => json({ items: [account()] }),
      "GET /v1/w/:wid/story-mentions": () => json({ items, next_cursor: null, total_7d: total }),
    },
  });
}

describe("Story mentions (GR-07)", () => {
  it("lists who mentioned the account, with a link while the story is live", async () => {
    setup([mention(), mention({ id: "m2", link_url: null, link_expires_at: null, contact: null })]);
    const rows = await screen.findAllByTestId("mention-row");
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByText("Priya Nair")).toBeInTheDocument();
    expect(within(rows[0]).getByRole("link", { name: /View story/ })).toHaveAttribute(
      "href",
      "https://lookaside.fbsbx.com/story?asset_id=1",
    );
    expect(within(rows[0]).getByRole("link", { name: "Open conversation" })).toHaveAttribute("href", expect.stringContaining("/inbox/c1"));
    expect(within(rows[1]).getByText("Someone")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Story expired")).toBeInTheDocument();
    expect(screen.getByTestId("mentions-total")).toHaveTextContent("2 mentions in the last 7 days.");
  });

  it("explains an empty list", async () => {
    setup([]);
    expect(await screen.findByText("No story mentions yet")).toBeInTheDocument();
  });
});
