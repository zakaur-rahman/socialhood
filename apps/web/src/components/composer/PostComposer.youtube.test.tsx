import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { SocialAccount } from "@/lib/api/types";
import { DEFAULT_YOUTUBE_OPTIONS, type YouTubeOptions } from "@/lib/publishing/rules";
import type { ScheduledPost, ScheduledPostDraft } from "@/lib/publishing/types";
import type { Uploader } from "@/lib/youtube/upload";
import { account, billingState, json, planList, problem, renderWithApi, workspace, type Call } from "@/test/api";
import { hashtagGroup, scheduledPost, target } from "@/test/composer-fixtures";

import { PostComposer } from "./PostComposer";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useParams: () => ({ slug: "maple", id: "sp1" }),
  useSearchParams: () => new URLSearchParams(""),
  usePathname: () => "/w/maple/schedule/sp1",
}));

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

const maple = account({ id: "a1", username: "maple.bakery", capabilities: ["publish"] });
const channel = account({ id: "y1", platform: "youtube", username: "maplebakery", display_name: "Maple Bakery", capabilities: ["publish"] });
const youtubeOn = { ...workspace, features: ["youtube" as const] };
const inTwoDays = () => new Date(Math.ceil((Date.now() + 2 * 86_400_000) / 3_600_000) * 3_600_000).toISOString();
const answered: YouTubeOptions = { ...DEFAULT_YOUTUBE_OPTIONS, title: "Sourdough at dawn", made_for_kids: false, synthetic_media: false };

function renderComposer({
  initial,
  accounts = [maple, channel],
  features = true,
  uploader,
  handlers = {},
}: {
  initial: ScheduledPost;
  accounts?: SocialAccount[];
  features?: boolean;
  uploader?: Uploader;
  handlers?: Record<string, (call: Call) => Response>;
}) {
  const state = { current: initial };
  const view = renderWithApi(<PostComposer id={initial.id} youtubeUploader={uploader} />, {
    ws: features ? youtubeOn : workspace,
    handlers: {
      "GET /v1/w/:wid/scheduled-posts/:id": () => json(state.current),
      "PUT /v1/w/:wid/scheduled-posts/:id": (call) => {
        const body = call.body as ScheduledPostDraft;
        state.current = {
          ...state.current,
          caption: body.caption,
          publish_at: body.publish_at ?? null,
          targets: (body.targets ?? []).map((item) =>
            target({ social_account_id: item.social_account_id, options: (item as { options?: YouTubeOptions | null }).options ?? null } as never),
          ),
        };
        return json(state.current);
      },
      "GET /v1/w/:wid/social-accounts": () => json({ items: accounts }),
      "GET /v1/w/:wid/hashtag-groups": () => json({ items: [hashtagGroup()] }),
      "GET /v1/w/:wid/posts": () => json({ items: [], next_cursor: null }),
      "GET /v1/w/:wid/billing": () => json(billingState({ plan: "free", status: "free" })),
      "GET /v1/billing/plans": () => json(planList()),
      ...handlers,
    },
  });
  return { ...view, state };
}

const youtubeDraft = (options: YouTubeOptions = DEFAULT_YOUTUBE_OPTIONS, overrides: Partial<ScheduledPost> = {}) =>
  scheduledPost({ publish_at: inTwoDays(), targets: [target({ social_account_id: "y1", options } as never)], ...overrides });

describe("PostComposer with YouTube (C-195)", () => {
  // jsdom can't make object URLs for the test's File; the preview only needs a string.
  beforeEach(() => {
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:preview");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
  });

  it("offers no YouTube channel while the workspace's switch is off", async () => {
    renderComposer({ initial: scheduledPost(), features: false });
    expect(await screen.findByRole("button", { name: /@maple\.bakery/ })).toBeInTheDocument();
    expect(screen.queryByTestId("youtube-tag")).not.toBeInTheDocument();
  });

  it("shows the channel with a YouTube tag, and choosing it alone opens the YouTube box and Description", async () => {
    const user = userEvent.setup();
    const { calls } = renderComposer({ initial: scheduledPost() });
    expect(await screen.findByTestId("youtube-tag")).toHaveTextContent("YouTube");
    await user.click(screen.getByRole("button", { name: /@maplebakery/ }));
    expect(await screen.findByRole("region", { name: "YouTube" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Description" })).toBeInTheDocument();
    expect(screen.getByTestId("youtube-dropzone")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Add from device/ })).not.toBeInTheDocument();
    expect(screen.getByTestId("youtube-route")).toHaveTextContent("straight from your computer to YouTube");
    // Until the title and both answers are in, the channel saves without options (the API needs them complete).
    await waitFor(() => expect(calls.some((call) => call.method === "PUT")).toBe(true));
    const put = calls.filter((call) => call.method === "PUT").at(-1)!.body as { targets: { options: YouTubeOptions | null }[] };
    expect(put.targets[0]).toMatchObject({ social_account_id: "y1", options: null });
  });

  it("saves the options once the title and both answers are in", async () => {
    const user = userEvent.setup();
    const { calls } = renderComposer({ initial: youtubeDraft() });
    const section = await screen.findByRole("region", { name: "YouTube" });
    // Public and notify subscribers are on by default; made for kids has no default.
    expect(within(section).getByRole("radio", { name: "Public" })).toHaveAttribute("aria-checked", "true");
    await user.type(within(section).getByRole("textbox", { name: "Title" }), "Sourdough at dawn");
    await user.click(within(within(section).getByRole("group", { name: "Is this video made for kids?" })).getByRole("radio", { name: "No" }));
    await user.click(within(within(section).getByRole("group", { name: /realistic AI-made/ })).getByRole("radio", { name: "No" }));
    await waitFor(
      () => {
        const put = calls.filter((call) => call.method === "PUT").at(-1)?.body as { targets: { options: YouTubeOptions | null }[] } | undefined;
        expect(put?.targets[0].options).toMatchObject({
          title: "Sourdough at dawn",
          privacy: "public",
          made_for_kids: false,
          synthetic_media: false,
          notify_subscribers: true,
        });
      },
      { timeout: 3000 },
    );
  });

  it("uses the media tray when the post goes to Instagram too", async () => {
    renderComposer({
      initial: scheduledPost({ targets: [target({ social_account_id: "a1" }), target({ social_account_id: "y1", options: answered } as never)] }),
    });
    expect(await screen.findByTestId("youtube-route")).toHaveTextContent("the video is stored once and sent to each");
    expect(screen.queryByTestId("youtube-dropzone")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Add from device/ })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Caption" })).toBeInTheDocument();
  });

  it("blocks scheduling until the title, made for kids and the AI question are answered", async () => {
    renderComposer({ initial: youtubeDraft() });
    expect(await screen.findByText("Add a title for YouTube.")).toBeInTheDocument();
    expect(screen.getByText("Say whether the video is made for kids.")).toBeInTheDocument();
    expect(screen.getByText("Say whether the video has realistic AI-made or altered content.")).toBeInTheDocument();
    expect(screen.getByText("Add the video for YouTube.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Schedule" })).toBeDisabled();
  });

  it("saves, opens the upload, sends the file to YouTube and confirms it", async () => {
    const user = userEvent.setup();
    const uploader = vi.fn<Uploader>(async ({ onProgress }) => {
      onProgress?.(10, 10);
      return "vid123";
    });
    const scheduled = youtubeDraft(answered, {
      status: "scheduled",
      targets: [
        target({
          social_account_id: "y1",
          options: answered,
          youtube: { route: "direct", state: "scheduled", video_id: "vid123", upload_expires_at: null, url: null },
        } as never),
      ],
    });
    const { calls } = renderComposer({
      initial: youtubeDraft(answered),
      uploader,
      handlers: {
        "POST /v1/w/:wid/scheduled-posts/:id/youtube-upload": () =>
          json({ target_id: "y1", upload_url: "https://www.googleapis.com/upload/youtube/v3/videos?upload_id=x", chunk_bytes: 8388608, expires_at: inTwoDays() }),
        "POST /v1/w/:wid/scheduled-posts/:id/youtube-upload/complete": () => json(scheduled),
      },
    });
    await user.upload(await screen.findByLabelText("Choose a video for YouTube"), new File(["0123456789"], "dawn.mp4", { type: "video/mp4" }));
    expect(screen.getByTestId("youtube-file-name")).toHaveTextContent("dawn.mp4");
    await user.click(screen.getByRole("button", { name: "Schedule" }));

    await waitFor(() => expect(toast.success).toHaveBeenCalledWith(expect.stringContaining("Scheduled on YouTube")));
    expect(uploader).toHaveBeenCalledWith(
      expect.objectContaining({ uploadUrl: "https://www.googleapis.com/upload/youtube/v3/videos?upload_id=x", chunkBytes: 8388608 }),
    );
    const start = calls.find((call) => call.method === "POST" && call.path.endsWith("/youtube-upload"));
    expect(start?.body).toMatchObject({ target_id: "y1", file_size: 10, content_type: "video/mp4", file_name: "dawn.mp4" });
    const complete = calls.find((call) => call.path.endsWith("/youtube-upload/complete"));
    expect(complete?.body).toEqual({ target_id: "y1", video_id: "vid123" });
    expect(await screen.findByTestId("youtube-banner")).toHaveTextContent("Scheduled on YouTube");
  });

  it("shows YouTube's daily limit in the YouTube box", async () => {
    const user = userEvent.setup();
    const uploader = vi.fn<Uploader>(async () => "never");
    renderComposer({
      initial: youtubeDraft(answered),
      uploader,
      handlers: {
        "POST /v1/w/:wid/scheduled-posts/:id/youtube-upload": () =>
          problem(429, "rate_limited", "YouTube's daily upload limit is reached, try after 1:30 PM IST."),
      },
    });
    await user.upload(await screen.findByLabelText("Choose a video for YouTube"), new File(["01"], "dawn.mp4", { type: "video/mp4" }));
    await user.click(screen.getByRole("button", { name: "Schedule" }));
    expect(await screen.findByText("YouTube's daily upload limit is reached, try after 1:30 PM IST.")).toBeInTheDocument();
    expect(uploader).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /Try again/ })).toBeInTheDocument();
  });
});
