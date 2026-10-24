import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { account, json, performance, renderWithApi } from "@/test/api";
import { scheduledPost, target } from "@/test/composer-fixtures";

import { StatusBanner } from "./StatusBanner";

const NOW = new Date("2026-09-29T12:00:00Z");

function banner(figures: ReturnType<typeof performance>, expiresAt: string | null = "2026-09-30T10:00:00Z") {
  return renderWithApi(
    <StatusBanner
      post={scheduledPost({
        status: "published",
        format: "story",
        published_at: "2026-09-29T10:00:00Z",
        targets: [
          target({
            status: "published",
            post_id: "mi1",
            permalink: "https://www.instagram.com/stories/maple/1/",
            published_at: "2026-09-29T10:00:00Z",
            expires_at: expiresAt,
          }),
        ],
      })}
      accounts={[account({ id: "a1", username: "maple" })]}
      timeZone="UTC"
      now={NOW}
      onEditAndRetry={() => {}}
      retrying={false}
      wid="w1"
    />,
    { handlers: { "GET /v1/w/:wid/analytics/posts/:id/performance": () => json(figures) } },
  );
}

describe("a published Story shows its insights (C-131)", () => {
  it("lists reach, views, replies and shares with the age they were read at", async () => {
    banner(
      performance({
        media_type: "story",
        age: "6h",
        metrics: { reach: 900, views: 1100, likes: null, comments: null, shares: 7, saves: null, engagement_rate: null },
        extra_metrics: { replies: 5, taps_forward: 700, taps_back: 80, swipes_forward: 40, exits: 60, clicks: null },
      }),
    );
    const line = await screen.findByTestId("story-insights");
    expect(line).toHaveTextContent("Reach 900 · Views 1,100 · Shares 7 · Replies 5 · at 6 h");
  });

  it("says when nothing has been read yet", async () => {
    banner(performance({ media_type: "story", age: "1h", captured_at: null, metrics: {} as never }));
    expect(await screen.findByTestId("story-insights")).toHaveTextContent("Figures are read 1 h after it goes up");
  });

  it("asks to reconnect when insights were not granted", async () => {
    banner(
      performance({
        media_type: "story",
        age: "1h",
        insights_granted: false,
        metrics: { reach: null, views: null, likes: null, comments: null, shares: null, saves: null, engagement_rate: null },
      }),
    );
    expect(await screen.findByTestId("story-insights")).toHaveTextContent("Reconnect to read Story insights");
  });

  it("says a Page Story has no figures, without asking for any", async () => {
    let asked = 0;
    renderWithApi(
      <StatusBanner
        post={scheduledPost({
          status: "published",
          format: "story",
          published_at: "2026-09-29T10:00:00Z",
          targets: [target({ status: "published", post_id: "mi1", published_at: "2026-09-29T10:00:00Z", expires_at: "2026-09-30T10:00:00Z" })],
        })}
        accounts={[account({ id: "a1", username: "maple.page", platform: "facebook" })]}
        timeZone="UTC"
        now={NOW}
        onEditAndRetry={() => {}}
        retrying={false}
        wid="w1"
      />,
      {
        handlers: {
          "GET /v1/w/:wid/analytics/posts/:id/performance": () => {
            asked += 1;
            return json(performance());
          },
        },
      },
    );
    expect(await screen.findByTestId("story-insights")).toHaveTextContent("Facebook doesn't share figures for Page Stories");
    expect(asked).toBe(0);
  });

  it("shows nothing for a post that is not a Story", async () => {
    banner(performance(), null);
    expect(await screen.findByTestId("status-banner")).toBeInTheDocument();
    expect(screen.queryByTestId("story-insights")).toBeNull();
  });
});
