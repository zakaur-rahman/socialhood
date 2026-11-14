import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

describe("a published post shows its collaborators' invites (FR-PUB-07, C-134)", () => {
  const published = (collaborators: { username: string; status: "pending" | "accepted" }[], checked: string | null = null) =>
    scheduledPost({
      id: "sp9",
      status: "published",
      published_at: "2026-09-29T10:00:00Z",
      targets: [
        target({
          status: "published",
          permalink: "https://www.instagram.com/p/abc/",
          published_at: "2026-09-29T10:00:00Z",
          collaborators,
          collaborators_checked_at: checked,
        }),
      ],
    });

  function render(post: ReturnType<typeof published>, handlers = {}) {
    return renderWithApi(
      <StatusBanner
        post={post}
        accounts={[account({ id: "a1", username: "maple" })]}
        timeZone="UTC"
        now={NOW}
        onEditAndRetry={() => {}}
        retrying={false}
        wid="w1"
      />,
      { handlers },
    );
  }

  it("lists each collaborator as Pending or Accepted and says they cannot be changed", () => {
    render(
      published(
        [
          { username: "maple.studio", status: "accepted" },
          { username: "bread.fan", status: "pending" },
        ],
        "2026-09-29T11:00:00Z",
      ),
    );
    expect(screen.getByTestId("collaborator-maple.studio")).toHaveTextContent("@maple.studio Accepted");
    expect(screen.getByTestId("collaborator-bread.fan")).toHaveTextContent("@bread.fan Pending");
    const line = screen.getByTestId("collaborator-status");
    expect(line).toHaveTextContent("Checked");
    expect(line).toHaveTextContent("They can't be changed after publishing.");
  });

  it("says when the invites have not been read yet", () => {
    render(published([{ username: "bread.fan", status: "pending" }]));
    expect(screen.getByTestId("collaborator-status")).toHaveTextContent("Not checked yet.");
  });

  it("shows nothing for a post without collaborators", () => {
    render(published([]));
    expect(screen.queryByTestId("collaborator-status")).toBeNull();
  });

  it("Refresh reads the invites now", async () => {
    const user = userEvent.setup();
    const fresh = published([{ username: "bread.fan", status: "accepted" }], "2026-09-29T12:00:00Z");
    const view = render(published([{ username: "bread.fan", status: "pending" }]), {
      "POST /v1/w/:wid/scheduled-posts/:id/collaborators/refresh": () => json(fresh),
    });
    await user.click(screen.getByRole("button", { name: "Refresh" }));
    await waitFor(() => expect(view.calls.some((call) => call.method === "POST" && /collaborators\/refresh$/.test(call.path))).toBe(true));
  });
});

describe("YouTube states (C-195)", () => {
  const channel = account({ id: "y1", platform: "youtube", username: "maplebakery", display_name: "Maple Bakery" });
  type State = "waiting_for_file" | "uploading" | "processing" | "scheduled" | "published" | "failed";
  const youtube = (state: State, url: string | null = null) => ({ route: "direct", state, video_id: "vid1", upload_expires_at: null, url });

  function show(post: Parameters<typeof StatusBanner>[0]["post"], progress: number | null = null) {
    return renderWithApi(
      <StatusBanner post={post} accounts={[channel]} timeZone="UTC" now={NOW} onEditAndRetry={() => {}} retrying={false} youtubeProgress={progress} />,
    );
  }

  it.each([
    ["waiting_for_file", "Waiting for the file"],
    ["processing", "Processing on YouTube"],
    ["scheduled", "Scheduled on YouTube"],
  ] as const)("says %s", (state, label) => {
    show(scheduledPost({ status: "scheduled", publish_at: "2026-10-01T10:00:00Z", targets: [target({ social_account_id: "y1", youtube: youtube(state) } as never)] }));
    expect(screen.getByTestId("youtube-banner")).toHaveTextContent(label);
  });

  it("shows this tab's upload progress", () => {
    show(scheduledPost({ targets: [target({ social_account_id: "y1" })] }), 42);
    expect(screen.getByTestId("youtube-banner")).toHaveTextContent("Uploading 42%");
  });

  it("links a published video to YouTube", () => {
    show(
      scheduledPost({
        status: "published",
        published_at: "2026-09-29T10:00:00Z",
        targets: [target({ social_account_id: "y1", status: "published", youtube: youtube("published", "https://www.youtube.com/watch?v=vid1") } as never)],
      }),
    );
    expect(screen.getByRole("link", { name: /View on YouTube/ })).toHaveAttribute("href", "https://www.youtube.com/watch?v=vid1");
  });

  it("shows nothing for a draft without YouTube", () => {
    show(scheduledPost({ targets: [target()] }));
    expect(screen.queryByTestId("youtube-banner")).not.toBeInTheDocument();
  });
});
