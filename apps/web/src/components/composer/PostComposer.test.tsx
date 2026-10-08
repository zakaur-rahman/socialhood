import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Link from "next/link";
import type { ReactElement } from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { LEAVE_WARNING } from "@/components/settings/SaveBar";
import { ApiError } from "@/lib/api/errors";
import type { MediaAsset, SocialAccount } from "@/lib/api/types";
import type { Cropper } from "@/lib/publishing/crop";
import type { ScheduledPost, ScheduledPostDraft } from "@/lib/publishing/types";
import { applyRealtimeEvent } from "@/lib/realtime/events";
import { formatDayTime } from "@/lib/tz";
import {
  account,
  automation,
  billingState,
  json,
  planList,
  problem,
  renderWithApi,
  template,
  workspace,
  type Call,
} from "@/test/api";
import {
  hashtagGroup,
  mediaAsset,
  postAsset,
  READY_CHECKLIST,
  readyPost,
  scheduledPost,
  target,
} from "@/test/composer-fixtures";

import { PostComposer } from "./PostComposer";
import { ComposerRoute } from "./routes";
import type { Uploader } from "./use-media-uploads";

const nav = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn(), search: "" }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: nav.push, replace: nav.replace }),
  useParams: () => ({ slug: "maple", id: "sp1" }),
  useSearchParams: () => new URLSearchParams(nav.search),
  usePathname: () => "/w/maple/schedule/sp1",
}));

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

const TZ = workspace.timezone;
const maple = account({ id: "a1", username: "maple.bakery", capabilities: ["publish"] });
const studio = account({ id: "a2", username: "maple.studio", capabilities: ["publish"] });
const inTwoDays = () => new Date(Math.ceil((Date.now() + 2 * 86_400_000) / 3_600_000) * 3_600_000).toISOString();

function validation(errors: { field: string; message: string }[]): Response {
  return new Response(JSON.stringify({ type: "about:blank", title: "validation_error", status: 422, code: "validation_error", errors }), {
    status: 422,
    headers: { "Content-Type": "application/problem+json" },
  });
}

/** What the fake API stores for a PUT: the body applied to the post. */
function applyDraft(post: ScheduledPost, body: ScheduledPostDraft, known: Map<string, ScheduledPost["assets"][number]>): ScheduledPost {
  return {
    ...post,
    status: post.status === "failed" || post.status === "canceled" ? "draft" : post.status,
    caption: body.caption,
    first_comment: body.first_comment ?? null,
    publish_at: body.publish_at ?? null,
    targets: (body.targets ?? []).map((item) => target({ social_account_id: item.social_account_id, caption_override: item.caption_override ?? null })),
    assets: (body.asset_ids ?? []).map((id, position) => ({ ...(known.get(id) ?? postAsset({ id })), position })),
    asset_count: body.asset_ids?.length ?? 0,
  };
}

type Handler = (call: Call, params: Record<string, string>) => Response | Promise<Response>;

function renderComposer({
  initial = scheduledPost(),
  accounts = [maple],
  handlers = {},
  put,
  upload,
  cropper,
  assets = [],
  shell,
}: {
  initial?: ScheduledPost;
  accounts?: SocialAccount[];
  handlers?: Record<string, Handler>;
  put?: (call: Call, count: number) => Response | undefined;
  upload?: Uploader;
  cropper?: Cropper;
  /** Assets the fake API knows by id, as a PUT would return them. */
  assets?: ScheduledPost["assets"];
  /** Rendered beside the composer, as the app shell's sidebar is. */
  shell?: ReactElement;
} = {}) {
  const known = new Map([...initial.assets, ...assets].map((asset) => [asset.id, asset]));
  const state = { current: initial };
  const puts: Call[] = [];
  const composer = <PostComposer id={initial.id} upload={upload} cropper={cropper} />;
  const view = renderWithApi(shell ? <>{shell}{composer}</> : composer, {
    handlers: {
      "GET /v1/w/:wid/scheduled-posts/:id": () => json(state.current),
      "PUT /v1/w/:wid/scheduled-posts/:id": (call) => {
        puts.push(call);
        const custom = put?.(call, puts.length);
        if (custom) return custom;
        state.current = applyDraft(state.current, call.body as ScheduledPostDraft, known);
        return json(state.current);
      },
      "GET /v1/w/:wid/social-accounts": () => json({ items: accounts }),
      "GET /v1/w/:wid/hashtag-groups": () => json({ items: [hashtagGroup()] }),
      "GET /v1/w/:wid/posts": () => json({ items: [], next_cursor: null }),
      "GET /v1/w/:wid/billing": () => json(billingState({ plan: "free", status: "free" })),
      "GET /v1/billing/plans": () => json(planList()),
      ...handlers,
    },
    upgradeDialog: true,
  });
  return { ...view, puts, state };
}

/** The sidebar's Inbox link; jsdom can't navigate, so reaching its click is "leaving". */
function SidebarLink({ onNavigate }: { onNavigate: () => void }) {
  return (
    <Link
      href="/w/maple/inbox"
      onClick={(event) => {
        event.preventDefault();
        onNavigate();
      }}
    >
      Inbox
    </Link>
  );
}

const captionBox = () => screen.getByRole("textbox", { name: "Caption" }) as HTMLTextAreaElement;
const scheduleButton = (name: RegExp | string = "Schedule") => screen.getByRole("button", { name });
const checklist = () => screen.getByRole("list", { name: "Checks before scheduling" });

beforeAll(() => {
  // jsdom lacks what Radix Select calls on open (the preview's account switcher).
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});

beforeEach(() => {
  nav.push.mockReset();
  nav.replace.mockReset();
  nav.search = "";
  toast.success.mockReset();
  toast.error.mockReset();
});

describe("PostComposer autosave (F-13)", () => {
  it("saves the whole draft 1 s after the last edit and says Saved once the API has it", async () => {
    const user = userEvent.setup();
    const { puts } = renderComposer({ initial: scheduledPost({ targets: [target()] }) });
    await user.type(await screen.findByRole("textbox", { name: "Caption" }), "Hello");
    expect(screen.getByTestId("save-status")).toHaveTextContent("Saving…");
    expect(puts).toHaveLength(0);
    await waitFor(() => expect(puts).toHaveLength(1), { timeout: 3000 });
    expect(puts[0].body).toEqual({
      targets: [{ social_account_id: "a1", caption_override: null }],
      asset_ids: [],
      caption: "Hello",
      first_comment: null,
      publish_at: null,
    });
    await waitFor(() => expect(screen.getByTestId("save-status")).toHaveTextContent("Saved"));
  });

  it("says Not saved when the save fails, and Retry sends it again", async () => {
    const user = userEvent.setup();
    const { puts } = renderComposer({ put: (_, count) => (count === 1 ? problem(500, "internal") : undefined) });
    await user.type(await screen.findByRole("textbox", { name: "Caption" }), "Hi");
    await waitFor(() => expect(screen.getByTestId("save-status")).toHaveTextContent("Not saved"), { timeout: 3000 });
    await user.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(screen.getByTestId("save-status")).toHaveTextContent("Saved"));
    expect(puts).toHaveLength(2);
  });
});

describe("PostComposer checklist gating (FR-PUB-10, T7.5 done-when)", () => {
  it("a failing item disables Schedule, says why, and links to the field; fixing it schedules", async () => {
    const user = userEvent.setup();
    const publishAt = inTwoDays();
    const calls: string[] = [];
    renderComposer({
      initial: readyPost({ caption: "a".repeat(2201), publish_at: publishAt }),
      handlers: {
        "POST /v1/w/:wid/scheduled-posts/:id/schedule": (call) => {
          calls.push(`schedule ${(call.body as { publish_at: string }).publish_at}`);
          return json(readyPost({ status: "scheduled", caption: "Hi", publish_at: publishAt }));
        },
      },
      put: (call) => {
        calls.push("put");
        return json(readyPost({ caption: (call.body as ScheduledPostDraft).caption, publish_at: publishAt }));
      },
    });
    await screen.findByRole("textbox", { name: "Caption" });

    expect(scheduleButton()).toBeDisabled();
    expect(screen.getByTestId("schedule-reason")).toHaveTextContent("Schedule: Fix the item in the checklist to schedule.");
    expect(scheduleButton()).toHaveAccessibleDescription(/Fix the item in the checklist to schedule/);
    const item = within(checklist()).getByRole("link", { name: /The caption is 2,201 characters. Instagram allows 2,200./ });
    expect(item).toHaveAttribute("href", "#composer-caption");
    await user.click(item);
    await waitFor(() => expect(captionBox()).toHaveFocus());

    await user.clear(captionBox());
    await user.type(captionBox(), "Hi");
    expect(scheduleButton()).toBeEnabled();
    await user.click(scheduleButton());
    await waitFor(() => expect(calls).toEqual(["put", `schedule ${publishAt}`]));
    await waitFor(() => expect(screen.getByTestId("status-pill")).toHaveTextContent("Scheduled"));
    expect(toast.success).toHaveBeenCalledWith(`Scheduled for ${formatDayTime(publishAt, TZ)}.`);
  });

  it("links a missing account to the Accounts section, and choosing one fixes it", async () => {
    const user = userEvent.setup();
    const { puts } = renderComposer({ initial: readyPost({ targets: [], publish_at: inTwoDays() }) });
    await screen.findByRole("textbox", { name: "Caption" });
    const item = await within(checklist()).findByRole("link", { name: /Choose at least one account./ });
    await user.click(item);
    await waitFor(() => expect(document.getElementById("composer-accounts")).toHaveFocus());
    const chip = screen.getByRole("button", { name: "@maple.bakery" });
    expect(chip).toHaveAttribute("aria-pressed", "false");
    await user.click(chip);
    expect(chip).toHaveAttribute("aria-pressed", "true");
    expect(within(checklist()).queryByRole("link", { name: /Choose at least one account/ })).not.toBeInTheDocument();
    await waitFor(() => expect(puts).toHaveLength(1), { timeout: 3000 });
    expect((puts[0].body as ScheduledPostDraft).targets).toEqual([{ social_account_id: "a1", caption_override: null }]);
  });

  it("disables an account that can't publish, with the reason, and flags one already chosen", async () => {
    const stale = account({ id: "a2", username: "maple.studio", status: "needs_reconnect", capabilities: ["publish"] });
    const other = account({ id: "a3", username: "old.shop", status: "needs_reconnect", capabilities: ["publish"] });
    renderComposer({
      initial: readyPost({ targets: [target(), target({ social_account_id: "a2" })], publish_at: inTwoDays() }),
      accounts: [maple, stale, other],
    });
    const unchosen = await screen.findByRole("button", { name: "@old.shop" });
    expect(unchosen).toBeDisabled();
    expect(unchosen).toHaveAccessibleDescription(/Needs reconnecting/);
    expect(screen.getByRole("button", { name: "@maple.studio" })).toBeEnabled(); // can be taken off
    expect(within(checklist()).getByRole("link", { name: /@maple.studio needs reconnecting before you can publish from it./ })).toHaveAttribute(
      "href",
      "#composer-account-a2",
    );
    expect(scheduleButton()).toBeDisabled();
  });

  it("shows the API's own checks, such as the publishing limit", async () => {
    renderComposer({
      initial: readyPost({
        publish_at: inTwoDays(),
        checklist: [
          ...READY_CHECKLIST.filter((item) => item.key !== "publishing_limit"),
          { key: "publishing_limit", ok: false, message: "@maple.bakery has used today's 100 posts.", field: "targets.0" },
        ],
        ready: false,
      }),
    });
    await screen.findByRole("textbox", { name: "Caption" });
    const item = await within(checklist()).findByRole("link", { name: /used today's 100 posts/ });
    expect(item).toHaveAttribute("href", "#composer-account-a1");
    expect(scheduleButton()).toBeDisabled();
    expect(screen.getByRole("button", { name: /Publish now/ })).toBeDisabled();
  });

  it("asks for a time, and refuses one less than 5 minutes away", async () => {
    const user = userEvent.setup();
    renderComposer({ initial: readyPost() });
    await screen.findByRole("textbox", { name: "Caption" });
    expect(scheduleButton()).toBeDisabled();
    expect(screen.getByTestId("schedule-reason")).toHaveTextContent("Pick a date and time, or add the post to the queue.");
    expect(screen.getByRole("button", { name: /Publish now/ })).toBeEnabled();

    const soon = new Date(Date.now() + 60_000);
    const [date, time] = [soon.toLocaleDateString("en-CA", { timeZone: TZ }), soon.toLocaleTimeString("en-GB", { timeZone: TZ, hour: "2-digit", minute: "2-digit" })];
    await user.type(screen.getByLabelText("Date"), date);
    await user.type(screen.getByLabelText("Time"), time);
    expect(await within(checklist()).findByRole("link", { name: /Pick a time at least 5 minutes from now./ })).toHaveAttribute("href", "#composer-when-date");
    expect(scheduleButton()).toBeDisabled();
  });

  it("shows each field of a refused Schedule (422) in the checklist", async () => {
    const user = userEvent.setup();
    renderComposer({
      initial: readyPost({ publish_at: inTwoDays() }),
      handlers: {
        "POST /v1/w/:wid/scheduled-posts/:id/schedule": () =>
          validation([{ field: "targets.0", message: "@maple.bakery has used today's 100 posts." }]),
      },
    });
    await user.click(await screen.findByRole("button", { name: "Schedule" }));
    expect(await within(checklist()).findByRole("link", { name: /used today's 100 posts/ })).toBeInTheDocument();
    expect(toast.error).toHaveBeenCalledWith("One thing to fix in the checklist.");
    expect(scheduleButton()).toBeDisabled();
  });

  it("over the plan's scheduled posts (402): the upgrade dialog names the limit, and nothing else does", async () => {
    const user = userEvent.setup();
    renderComposer({
      initial: readyPost({ publish_at: inTwoDays() }),
      handlers: {
        "POST /v1/w/:wid/scheduled-posts/:id/schedule": () =>
          problem(402, "quota_exceeded", "Your plan includes 10 scheduled posts a month.", {
            entitlement: "scheduled_posts_monthly",
            limit: 10,
          }),
      },
    });
    await user.click(await screen.findByRole("button", { name: "Schedule" }));
    const upgrade = await screen.findByRole("dialog", { name: "Scheduled post limit reached" });
    expect(upgrade).toHaveTextContent("Free includes 10 scheduled posts a month.");
    expect(toast.error).not.toHaveBeenCalled();
    expect(toast.success).not.toHaveBeenCalledWith(expect.stringMatching(/^Scheduled/));
  });
});

describe("PostComposer media (FR-PUB-13, TR-MED-02)", () => {
  function controlledUpload() {
    const control = {
      progress: (() => {}) as (fraction: number) => void,
      finish: (() => {}) as (asset: MediaAsset) => void,
      fail: (() => {}) as (error: Error) => void,
      files: [] as File[],
    };
    const upload: Uploader = (file, options) => {
      control.files.push(file);
      control.progress = options.onProgress;
      return new Promise((resolve, reject) => {
        control.finish = resolve;
        control.fail = reject;
      });
    };
    return { upload, control };
  }

  it("uploading: real progress, Schedule waits, then the photo joins the post", async () => {
    const user = userEvent.setup();
    const { upload, control } = controlledUpload();
    const { puts } = renderComposer({ initial: readyPost({ publish_at: inTwoDays() }), upload });
    await screen.findByRole("textbox", { name: "Caption" });
    expect(scheduleButton()).toBeEnabled();

    await user.upload(screen.getByTestId("composer-media-input"), new File(["x"], "dress.jpg", { type: "image/jpeg" }));
    act(() => control.progress(0.5));
    expect(screen.getByRole("progressbar", { name: "Uploading dress.jpg" })).toHaveAttribute("aria-valuenow", "50");
    expect(scheduleButton()).toBeDisabled();
    expect(screen.getByTestId("schedule-reason")).toHaveTextContent("Wait for the uploads to finish.");
    // Both buttons wait for the same reason: it is said once, and describes both (UI-032).
    expect(screen.getByTestId("schedule-reason")).toHaveTextContent("Schedule and Publish now: Wait for the uploads to finish.");
    expect(screen.getByRole("button", { name: "Publish now" })).toHaveAccessibleDescription(
      "Schedule and Publish now: Wait for the uploads to finish.",
    );
    act(() => control.progress(1));
    expect(screen.getByText("Processing…")).toBeInTheDocument();

    act(() => control.finish(mediaAsset({ id: "ma1", width: 1080, height: 1080 })));
    expect(await screen.findByRole("listitem", { name: "Photo 2" })).toBeInTheDocument();
    expect(screen.getByTestId("post-format")).toHaveTextContent("Carousel · 2 items");
    await waitFor(() => expect(puts.length).toBeGreaterThan(0), { timeout: 3000 });
    expect((puts.at(-1)?.body as ScheduledPostDraft).asset_ids).toEqual(["as1", "ma1"]);
  });

  it("upload failed: shows the reason, and Retry uploads again", async () => {
    const user = userEvent.setup();
    const { upload, control } = controlledUpload();
    renderComposer({ initial: readyPost(), upload });
    await screen.findByRole("textbox", { name: "Caption" });
    await user.upload(screen.getByTestId("composer-media-input"), new File(["x"], "dress.jpg", { type: "image/jpeg" }));
    act(() => control.fail(new Error("offline")));
    const tile = await screen.findByRole("listitem", { name: "dress.jpg" });
    expect(tile).toHaveAttribute("data-status", "failed");
    await user.click(within(tile).getByRole("button", { name: "Retry uploading dress.jpg" }));
    expect(control.files).toHaveLength(2);
    expect(screen.getByRole("listitem", { name: "dress.jpg" })).toHaveAttribute("data-status", "uploading");
  });

  it("an unsupported upload shows Instagram's rule", async () => {
    const user = userEvent.setup();
    const { upload, control } = controlledUpload();
    renderComposer({ initial: readyPost(), upload });
    await screen.findByRole("textbox", { name: "Caption" });
    await user.upload(screen.getByTestId("composer-media-input"), new File(["x"], "clip.mp4", { type: "video/mp4" }));
    act(() => control.fail(new ApiError({ type: "about:blank", title: "unsupported_media", status: 415, code: "unsupported_media" })));
    const tile = await screen.findByRole("listitem", { name: "clip.mp4" });
    expect(tile).toHaveAttribute("data-status", "failed");
    expect(tile).toHaveTextContent("Instagram can't publish this file. Use JPEG or PNG images, or MP4 video up to 90 seconds.");
  });

  it("refuses files Instagram can't publish before uploading", async () => {
    const user = userEvent.setup({ applyAccept: false });
    const upload = vi.fn<Uploader>();
    renderComposer({ initial: readyPost(), upload });
    await screen.findByRole("textbox", { name: "Caption" });
    await user.upload(screen.getByTestId("composer-media-input"), new File(["x"], "menu.pdf", { type: "application/pdf" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "menu.pdf: Instagram can't publish this file. Use JPEG or PNG images, or MP4 video up to 90 seconds.",
    );
    expect(upload).not.toHaveBeenCalled();
  });

  it("crop needed: the checklist links to the crop; the cropped copy replaces the photo", async () => {
    const user = userEvent.setup();
    const { upload, control } = controlledUpload();
    const cropped = new File(["c"], "tall-4x5.jpg", { type: "image/jpeg" });
    const cropper = vi.fn<Cropper>().mockResolvedValue(cropped);
    const tall = postAsset({ id: "tall", width: 1080, height: 1920 });
    const { puts } = renderComposer({
      initial: readyPost({ assets: [tall], publish_at: inTwoDays() }),
      upload,
      cropper,
      assets: [postAsset({ id: "cropped", width: 1080, height: 1350 })],
    });
    await screen.findByRole("textbox", { name: "Caption" });

    const item = await within(checklist()).findByRole("link", { name: /Photo 1 is taller than 4:5. Crop it to 1:1, 4:5 or 1.91:1./ });
    expect(scheduleButton()).toBeDisabled();
    await user.click(item);
    const fix = screen.getByRole("button", { name: /Crop needed/ });
    await waitFor(() => expect(fix).toHaveFocus());
    await user.click(fix);

    const dialog = await screen.findByRole("dialog", { name: "Crop Photo 1" });
    expect(within(dialog).getByRole("radio", { name: "Portrait 4:5" })).toHaveAttribute("aria-checked", "true");
    expect(within(dialog).getByTestId("crop-frame")).toHaveAttribute("data-rect", "0,285,1080,1350");
    await user.click(within(dialog).getByRole("button", { name: "Crop and upload" }));
    expect(cropper).toHaveBeenCalledWith(
      { file: null, url: tall.url, name: "photo.jpg" },
      { x: 0, y: 285, width: 1080, height: 1350 },
      expect.objectContaining({ key: "4:5" }),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(control.files).toEqual([cropped]);
    act(() => control.progress(0.3));
    expect(screen.getByRole("progressbar", { name: "Uploading the crop of Photo 1" })).toHaveAttribute("aria-valuenow", "30");

    act(() => control.finish(mediaAsset({ id: "cropped", width: 1080, height: 1350 })));
    await waitFor(() => expect(puts.length).toBeGreaterThan(0), { timeout: 3000 });
    expect((puts.at(-1)?.body as ScheduledPostDraft).asset_ids).toEqual(["cropped"]);
    await waitFor(() => expect(scheduleButton()).toBeEnabled());
  });

  it("moves the crop frame with the arrow keys", async () => {
    const user = userEvent.setup();
    renderComposer({ initial: readyPost({ assets: [postAsset({ id: "tall", width: 1080, height: 1920 })] }) });
    await user.click(await screen.findByRole("button", { name: /Crop needed/ }));
    const frame = await screen.findByTestId("crop-frame");
    frame.focus();
    await user.keyboard("{ArrowUp}{ArrowUp}");
    const [, y] = (frame.getAttribute("data-rect") ?? "").split(",").map(Number);
    expect(y).toBeGreaterThan(285 - 0.05 * 1920);
    expect(y).toBeLessThan(285 - 0.03 * 1920);
    await user.click(screen.getByRole("radio", { name: "Square 1:1" }));
    expect(screen.getByTestId("crop-frame").getAttribute("data-rect")).toMatch(/^0,\d+,1080,1080$/);
  });

  it("adds uploads from the media library", async () => {
    const user = userEvent.setup();
    const libraryCalls: Call[] = [];
    const { puts } = renderComposer({
      initial: readyPost(),
      handlers: {
        "GET /v1/w/:wid/media-assets": (call) => {
          libraryCalls.push(call);
          return json({
            items: [
              mediaAsset({ id: "as1", original_filename: "first.jpg" }),
              mediaAsset({ id: "ma2", original_filename: "second.jpg" }),
            ],
            next_cursor: null,
          });
        },
      },
    });
    await user.click(await screen.findByRole("button", { name: "Media library" }));
    const dialog = await screen.findByRole("dialog", { name: "Media library" });
    expect(await within(dialog).findByRole("button", { name: "first.jpg, already in this post" })).toBeDisabled();
    await user.click(within(dialog).getByRole("radio", { name: "Videos" }));
    await waitFor(() => expect(libraryCalls.at(-1)?.url.searchParams.get("type")).toBe("video"));
    await user.click(await within(dialog).findByRole("button", { name: "second.jpg" }));
    await user.click(within(dialog).getByRole("button", { name: "Add 1" }));
    await waitFor(() => expect(puts.length).toBeGreaterThan(0), { timeout: 3000 });
    expect((puts.at(-1)?.body as ScheduledPostDraft).asset_ids).toEqual(["as1", "ma2"]);
  });

  it("reorders with the keyboard and saves the new order", async () => {
    const user = userEvent.setup();
    const { puts } = renderComposer({ initial: readyPost({ assets: [postAsset(), postAsset({ id: "as2", position: 1 })] }) });
    (await screen.findByRole("button", { name: "Move Photo 1" })).focus();
    await user.keyboard("{ArrowRight}");
    await waitFor(() => expect(puts.length).toBeGreaterThan(0), { timeout: 3000 });
    expect((puts.at(-1)?.body as ScheduledPostDraft).asset_ids).toEqual(["as2", "as1"]);
  });
});

describe("PostComposer captions", () => {
  it("per-account captions: each account gets its own, and the preview can switch", async () => {
    const user = userEvent.setup();
    const { puts } = renderComposer({
      initial: readyPost({ caption: "Hello", targets: [target(), target({ social_account_id: "a2" })] }),
      accounts: [maple, studio],
    });
    await user.click(await screen.findByRole("switch", { name: "Different caption per account" }));
    const second = screen.getByRole("textbox", { name: "Caption for @maple.studio" });
    await user.clear(second);
    await user.type(second, "Studio hello");
    await waitFor(() => expect(puts.length).toBeGreaterThan(0), { timeout: 3000 });
    await waitFor(() =>
      expect((puts.at(-1)?.body as ScheduledPostDraft).targets).toEqual([
        { social_account_id: "a1", caption_override: "Hello" },
        { social_account_id: "a2", caption_override: "Studio hello" },
      ]),
    );
    await user.click(screen.getByRole("combobox", { name: "Account" }));
    await user.click(await screen.findByRole("option", { name: "@maple.studio" }));
    expect(screen.getByTestId("preview-caption")).toHaveTextContent("maple.studio Studio hello");
  });

  it("the first comment has its own counter and is saved", async () => {
    const user = userEvent.setup();
    const { puts } = renderComposer({ initial: readyPost() });
    await user.type(await screen.findByRole("textbox", { name: "Comment" }), "#summer #ootd");
    expect(screen.getByTestId("composer-first-comment-counts")).toHaveTextContent("2 / 30 hashtags");
    await waitFor(() => expect(puts.length).toBeGreaterThan(0), { timeout: 3000 });
    expect((puts.at(-1)?.body as ScheduledPostDraft).first_comment).toBe("#summer #ootd");
  });
});

describe("PostComposer When (FR-PUB-04, FR-PUB-09)", () => {
  it("Add to queue shows the time it will take, then queues the post", async () => {
    const user = userEvent.setup();
    const free = "2027-03-03T12:30:00Z";
    const calls: string[] = [];
    renderComposer({
      initial: readyPost(),
      handlers: {
        "GET /v1/w/:wid/social-accounts/:id/posting-slots": () =>
          json({ social_account_id: "a1", timezone: TZ, slots: [{ weekday: 2, local_time: "18:00:00" }], next_free_at: [free] }),
        "POST /v1/w/:wid/scheduled-posts/:id/queue": () => {
          calls.push("queue");
          return json(readyPost({ status: "scheduled", publish_at: free }));
        },
      },
    });
    await user.click(await screen.findByRole("radio", { name: "Add to queue" }));
    expect(await screen.findByTestId("queue-preview")).toHaveTextContent(`It will publish ${formatDayTime(free, TZ)}, the next free posting time.`);
    await user.click(scheduleButton("Add to queue"));
    await waitFor(() => expect(calls).toEqual(["queue"]));
    expect(toast.success).toHaveBeenCalledWith(`Added to the queue for ${formatDayTime(free, TZ)}.`);
    await waitFor(() => expect(screen.getByTestId("status-pill")).toHaveTextContent("Scheduled"));
  });

  it("opens on Add to queue from the Schedule page's ?when=queue", async () => {
    nav.search = "when=queue";
    renderWithApi(<ComposerRoute />, {
      handlers: {
        "GET /v1/w/:wid/scheduled-posts/:id": () => json(readyPost()),
        "GET /v1/w/:wid/social-accounts": () => json({ items: [maple] }),
        "GET /v1/w/:wid/hashtag-groups": () => json({ items: [] }),
        "GET /v1/w/:wid/posts": () => json({ items: [], next_cursor: null }),
        "GET /v1/w/:wid/social-accounts/:id/posting-slots": () =>
          json({ social_account_id: "a1", timezone: TZ, slots: [{ weekday: 2, local_time: "18:00:00" }], next_free_at: ["2027-03-03T12:30:00Z"] }),
      },
    });
    expect(await screen.findByRole("radio", { name: "Add to queue" })).toHaveAttribute("aria-checked", "true");
    expect(await screen.findByRole("button", { name: "Add to queue" })).toBeEnabled();
  });

  it("an account without posting times can't be queued", async () => {
    const user = userEvent.setup();
    renderComposer({
      initial: readyPost(),
      handlers: {
        "GET /v1/w/:wid/social-accounts/:id/posting-slots": () =>
          json({ social_account_id: "a1", timezone: TZ, slots: [], next_free_at: [] }),
      },
    });
    await user.click(await screen.findByRole("radio", { name: "Add to queue" }));
    expect(await screen.findByText(/@maple.bakery has no posting times./)).toBeInTheDocument();
    expect(scheduleButton("Add to queue")).toBeDisabled();
  });
});

describe("PostComposer scheduled posts (FR-PUB-04)", () => {
  it("doesn't autosave; Update schedule waits for a change, then saves it", async () => {
    const user = userEvent.setup();
    const publishAt = inTwoDays();
    const { puts } = renderComposer({ initial: readyPost({ status: "scheduled", publish_at: publishAt }) });
    expect(await screen.findByText(`Scheduled for ${formatDayTime(publishAt, TZ)}`)).toBeInTheDocument();
    expect(scheduleButton("Update schedule")).toBeDisabled();
    expect(screen.getByTestId("schedule-reason")).toHaveTextContent("Change something to update the schedule.");

    await user.type(captionBox(), "!");
    expect(screen.getByTestId("save-status")).toHaveTextContent("Unsaved changes");
    await new Promise((resolve) => setTimeout(resolve, 1200));
    expect(puts).toHaveLength(0);

    await user.click(scheduleButton("Update schedule"));
    await waitFor(() => expect(puts).toHaveLength(1));
    expect((puts[0].body as ScheduledPostDraft).caption).toBe("New linen dresses are here #linen!");
    expect(toast.success).toHaveBeenCalledWith(`Schedule updated. It publishes ${formatDayTime(publishAt, TZ)}.`);
    await waitFor(() => expect(screen.getByTestId("save-status")).toHaveTextContent("Saved"));
  });

  it("has no Save as draft: Update schedule is the save, and Unschedule is in More", async () => {
    const user = userEvent.setup();
    renderComposer({ initial: readyPost({ status: "scheduled", publish_at: inTwoDays() }) });
    const actions = await screen.findByRole("region", { name: "Post actions" });
    expect(within(actions).getByRole("button", { name: "Update schedule" })).toBeInTheDocument();
    expect(within(actions).queryByRole("button", { name: /draft/i })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "More actions" }));
    expect(await screen.findByRole("menuitem", { name: "Unschedule" })).toBeInTheDocument();
  });

  it("a draft keeps Save draft, and has no Unschedule", async () => {
    const user = userEvent.setup();
    renderComposer({ initial: readyPost() });
    const actions = await screen.findByRole("region", { name: "Post actions" });
    expect(within(actions).getByRole("button", { name: "Save draft" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "More actions" }));
    await screen.findByRole("menuitem", { name: "Duplicate" });
    expect(screen.queryByRole("menuitem", { name: "Unschedule" })).not.toBeInTheDocument();
  });

  it("Unschedule asks first: Cancel changes nothing; confirming makes it a draft with its edits", async () => {
    const user = userEvent.setup();
    const calls: string[] = [];
    const stored: { state?: { current: ScheduledPost } } = {};
    const view = renderComposer({
      initial: readyPost({ status: "scheduled", publish_at: inTwoDays() }),
      handlers: {
        "POST /v1/w/:wid/scheduled-posts/:id/unschedule": () => {
          calls.push("unschedule");
          const state = stored.state as { current: ScheduledPost };
          state.current = { ...state.current, status: "draft" };
          return json(state.current);
        },
      },
      put: () => {
        calls.push("put");
        return undefined;
      },
    });
    stored.state = view.state;
    await user.type(await screen.findByRole("textbox", { name: "Caption" }), "!");

    await user.click(screen.getByRole("button", { name: "More actions" }));
    await user.click(await screen.findByRole("menuitem", { name: "Unschedule" }));
    const confirm = await screen.findByRole("alertdialog", { name: "Unschedule this post?" });
    expect(confirm).toHaveTextContent("It won't publish until you schedule it again.");
    await user.click(within(confirm).getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
    expect(calls).toEqual([]);
    expect(screen.getByTestId("status-pill")).toHaveTextContent("Scheduled");

    await user.click(screen.getByRole("button", { name: "More actions" }));
    await user.click(await screen.findByRole("menuitem", { name: "Unschedule" }));
    await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Unschedule" }));
    await waitFor(() => expect(calls).toEqual(["unschedule", "put"]));
    expect(view.state.current.caption).toBe("New linen dresses are here #linen!");
    expect(toast.success).toHaveBeenCalledWith("Moved to drafts. It won't publish until you schedule it again.");
    await waitFor(() => expect(screen.getByTestId("status-pill")).toHaveTextContent("Draft"));
    expect(screen.getByRole("button", { name: "Save draft" })).toBeInTheDocument();
  });

  it("Publish now asks first, then the composer turns read-only", async () => {
    const user = userEvent.setup();
    renderComposer({
      initial: readyPost(),
      handlers: {
        "POST /v1/w/:wid/scheduled-posts/:id/publish-now": () => json(readyPost({ status: "publishing", publish_at: new Date().toISOString() }), 202),
      },
    });
    await user.click(await screen.findByRole("button", { name: /Publish now/ }));
    const confirm = await screen.findByRole("alertdialog", { name: "Publish now?" });
    expect(confirm).toHaveTextContent("It goes live on @maple.bakery straight away.");
    await user.click(within(confirm).getByRole("button", { name: "Publish now" }));
    expect(await screen.findByText("Publishing started. The post can't be changed now.")).toBeInTheDocument();
    expect(captionBox()).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Schedule" })).not.toBeInTheDocument();
    expect(toast.success).toHaveBeenCalledWith("Publishing started.");
  });
});

describe("PostComposer leaving with unsaved edits (C-044)", () => {
  afterEach(() => vi.restoreAllMocks());

  it("a scheduled post with edits asks before a sidebar link leaves; staying keeps the edits", async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const navigated = vi.fn();
    renderComposer({
      initial: readyPost({ status: "scheduled", publish_at: inTwoDays() }),
      shell: <SidebarLink onNavigate={navigated} />,
    });
    await user.type(await screen.findByRole("textbox", { name: "Caption" }), "!");
    expect(screen.getByTestId("save-status")).toHaveTextContent("Unsaved changes");

    await user.click(screen.getByRole("link", { name: "Inbox" }));
    expect(confirm).toHaveBeenCalledWith(LEAVE_WARNING);
    expect(navigated).not.toHaveBeenCalled();
    expect(captionBox().value).toBe("New linen dresses are here #linen!");

    confirm.mockReturnValue(true);
    await user.click(screen.getByRole("link", { name: "Inbox" }));
    expect(navigated).toHaveBeenCalledOnce();
  });

  it("Duplicate on a scheduled post with edits asks first, like a link out does (UI-032)", async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const duplicates: string[] = [];
    renderComposer({
      initial: readyPost({ status: "scheduled", publish_at: inTwoDays() }),
      handlers: {
        "POST /v1/w/:wid/scheduled-posts/:id/duplicate": () => {
          duplicates.push("duplicate");
          return json(readyPost({ id: "sp2" }), 201);
        },
      },
    });
    await user.type(await screen.findByRole("textbox", { name: "Caption" }), "!");

    await user.click(screen.getByRole("button", { name: "More actions" }));
    await user.click(await screen.findByRole("menuitem", { name: "Duplicate" }));
    expect(confirm).toHaveBeenCalledWith(LEAVE_WARNING);
    expect(duplicates).toEqual([]);
    expect(nav.push).not.toHaveBeenCalled();
    expect(captionBox().value).toBe("New linen dresses are here #linen!");

    confirm.mockReturnValue(true);
    await user.click(screen.getByRole("button", { name: "More actions" }));
    await user.click(await screen.findByRole("menuitem", { name: "Duplicate" }));
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/w/maple/schedule/sp2"));
    expect(duplicates).toEqual(["duplicate"]);
  });

  it("undoing a scheduled post's edits leaves nothing unsaved (UI-032)", async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const navigated = vi.fn();
    renderComposer({
      initial: readyPost({ status: "scheduled", publish_at: inTwoDays() }),
      shell: <SidebarLink onNavigate={navigated} />,
      handlers: { "POST /v1/w/:wid/ai/caption": () => json({ caption: "Linen season is here #linen" }) },
    });
    await screen.findByRole("textbox", { name: "Caption" });

    // Write with AI, then the toast's Undo: the caption is the stored one again.
    await user.click(screen.getByRole("button", { name: "Write with AI" }));
    await user.type(screen.getByRole("textbox", { name: "What's the post about?" }), "linen dresses");
    await user.click(screen.getByRole("button", { name: "Write caption" }));
    await waitFor(() => expect(captionBox().value).toBe("Linen season is here #linen"));
    expect(screen.getByTestId("save-status")).toHaveTextContent("Unsaved changes");
    const [, options] = toast.success.mock.calls.at(-1) as [string, { action: { onClick: () => void } }];
    act(() => options.action.onClick());
    expect(captionBox().value).toBe("New linen dresses are here #linen");
    expect(screen.getByTestId("save-status")).toHaveTextContent("Saved");

    // Typing and deleting a character does the same.
    await user.type(captionBox(), "!");
    expect(screen.getByTestId("save-status")).toHaveTextContent("Unsaved changes");
    expect(scheduleButton("Update schedule")).toBeEnabled();
    await user.type(captionBox(), "{Backspace}");
    expect(screen.getByTestId("save-status")).toHaveTextContent("Saved");
    expect(scheduleButton("Update schedule")).toBeDisabled();
    expect(screen.getByTestId("schedule-reason")).toHaveTextContent("Change something to update the schedule.");
    await user.click(screen.getByRole("link", { name: "Inbox" }));
    expect(confirm).not.toHaveBeenCalled();
    expect(navigated).toHaveBeenCalledOnce();
  });

  it("a scheduled post without edits, or once Update schedule saved them, leaves without asking", async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const navigated = vi.fn();
    renderComposer({
      initial: readyPost({ status: "scheduled", publish_at: inTwoDays() }),
      shell: <SidebarLink onNavigate={navigated} />,
    });
    await screen.findByRole("textbox", { name: "Caption" });
    await user.click(screen.getByRole("link", { name: "Inbox" }));
    expect(navigated).toHaveBeenCalledOnce();

    await user.type(captionBox(), "!");
    await user.click(scheduleButton("Update schedule"));
    await waitFor(() => expect(screen.getByTestId("save-status")).toHaveTextContent("Saved"));
    await user.click(screen.getByRole("link", { name: "Inbox" }));
    expect(navigated).toHaveBeenCalledTimes(2);
    expect(confirm).not.toHaveBeenCalled();
  });

  it("a draft autosaves instead: leaving doesn't ask, and the edit is sent on the way out", async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const navigated = vi.fn();
    const { puts, unmount } = renderComposer({
      initial: scheduledPost({ targets: [target()] }),
      shell: <SidebarLink onNavigate={navigated} />,
    });
    await user.type(await screen.findByRole("textbox", { name: "Caption" }), "Hi");
    expect(screen.getByTestId("save-status")).toHaveTextContent("Saving…");
    await user.click(screen.getByRole("link", { name: "Inbox" }));
    expect(confirm).not.toHaveBeenCalled();
    expect(navigated).toHaveBeenCalledOnce();

    unmount(); // the route changes
    await waitFor(() => expect(puts).toHaveLength(1));
    expect((puts[0].body as ScheduledPostDraft).caption).toBe("Hi");
  });
});

describe("PostComposer after publishing (UX-SCR-13, FR-PUB-06, FR-PUB-11)", () => {
  it("publishing: read-only with a status banner, and it follows scheduled_post.updated", async () => {
    const initial = readyPost({ status: "publishing", targets: [target({ status: "publishing" })] });
    const { queryClient } = renderComposer({ initial });
    expect(await screen.findByText("Publishing started. The post can't be changed now.")).toBeInTheDocument();
    expect(captionBox()).toBeDisabled();
    expect(await screen.findByRole("button", { name: "@maple.bakery" })).toBeDisabled();
    expect(screen.queryByRole("region", { name: "Post actions" })).not.toBeInTheDocument();

    act(() =>
      applyRealtimeEvent(queryClient, workspace.id, {
        id: "1-0",
        event: "scheduled_post.updated",
        data: JSON.stringify({
          scheduled_post: {
            ...initial,
            status: "published",
            published_at: "2026-09-29T12:00:00Z",
            targets: [target({ status: "published", permalink: "https://www.instagram.com/p/abc/", published_at: "2026-09-29T12:00:00Z" })],
          },
        }),
      }),
    );
    expect(await screen.findByRole("link", { name: /View on Instagram/ })).toHaveAttribute("href", "https://www.instagram.com/p/abc/");
    expect(screen.getByTestId("status-pill")).toHaveTextContent("Published");
  });

  it("published: View on Instagram per account and the first-comment result", async () => {
    renderComposer({
      initial: readyPost({
        status: "partially_published",
        first_comment: "#summer",
        published_at: "2026-09-29T12:00:00Z",
        targets: [
          target({ status: "published", permalink: "https://www.instagram.com/p/abc/", first_comment: { status: "posted", platform_comment_id: "c1", error: null } }),
          target({
            social_account_id: "a2",
            status: "published",
            permalink: "https://www.instagram.com/p/def/",
            first_comment: { status: "failed", platform_comment_id: null, error: "Comments are turned off for this post." },
          }),
        ],
      }),
      accounts: [maple, studio],
    });
    const banner = await screen.findByTestId("status-banner");
    expect(banner).toHaveTextContent("Partly published");
    expect(screen.getAllByRole("link", { name: /View on Instagram/ })).toHaveLength(2);
    expect(screen.getByText("First comment posted")).toBeInTheDocument();
    expect(screen.getByText("First comment didn't post: Comments are turned off for this post.")).toBeInTheDocument();
  });

  it("failed: the reason, and Edit and retry makes it a draft again", async () => {
    const user = userEvent.setup();
    const { puts } = renderComposer({
      initial: readyPost({
        status: "failed",
        targets: [target({ status: "failed", error: { code: "platform_rejected", message: "Instagram rejected this: The media is too large." } })],
      }),
    });
    const banner = await screen.findByRole("alert");
    expect(banner).toHaveTextContent("This post didn't publish.");
    expect(banner).toHaveTextContent("Failed: Instagram rejected this: The media is too large.");
    expect(captionBox()).toBeDisabled();
    await user.click(within(banner).getByRole("button", { name: "Edit and retry" }));
    await waitFor(() => expect(puts).toHaveLength(1));
    await waitFor(() => expect(screen.getByRole("textbox", { name: "Caption" })).toBeEnabled());
    expect(screen.getByTestId("status-pill")).toHaveTextContent("Draft");
  });
});

describe("PostComposer comment automation (FR-AUT-18)", () => {
  it("shows linked automations with a summary", async () => {
    renderComposer({
      initial: readyPost({ automations: [{ id: "au1", name: "Comment LINK, DM the link", status: "active", trigger: "comment_keyword" }] }),
      handlers: { "GET /v1/w/:wid/automations/:id": () => json(automation({ status: "active", keywords: ["link", "price"] })) },
    });
    const list = await screen.findByRole("list", { name: "Automations for this post" });
    expect(within(list).getByRole("link", { name: "Comment LINK, DM the link" })).toHaveAttribute("href", "/w/maple/automations/au1");
    expect(await within(list).findByText("Comment keyword: LINK, PRICE → DM")).toBeInTheDocument();
    expect(within(list).getByText("Active")).toBeInTheDocument();
  });

  it("Add comment automation creates one from a template for this post and opens it", async () => {
    const user = userEvent.setup();
    const created: Call[] = [];
    const saved: Call[] = [];
    const draftAutomation = automation({ id: "au9", status: "draft", post_scope: "all", posts: [] });
    renderComposer({
      initial: readyPost(),
      handlers: {
        "GET /v1/w/:wid/automation-templates": () =>
          json({ items: [template(), template({ key: "dm_price", name: "Price by DM", trigger: "dm_keyword" })] }),
        "POST /v1/w/:wid/automations": (call) => {
          created.push(call);
          return json(draftAutomation, 201);
        },
        "PUT /v1/w/:wid/automations/:id": (call) => {
          saved.push(call);
          return json({ ...draftAutomation, post_scope: "selected" });
        },
      },
    });
    await user.click(await screen.findByRole("button", { name: "Add comment automation" }));
    const dialog = await screen.findByRole("dialog", { name: "Add comment automation" });
    expect(within(dialog).queryByRole("button", { name: "Use template: Price by DM" })).not.toBeInTheDocument();
    await user.click(await within(dialog).findByRole("button", { name: "Use template: Send a link to commenters" }));
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/w/maple/automations/au9?focus=first"));
    expect(created[0].body).toEqual({ template_key: "link_to_commenters", social_account_id: "a1" });
    expect(saved[0].body).toMatchObject({ post_scope: "selected", scheduled_post_ids: ["sp1"], media_item_ids: [], trigger: "comment_keyword" });
  });

  it("asks for an account first when there is none", async () => {
    renderComposer({ initial: readyPost({ targets: [] }) });
    const button = await screen.findByRole("button", { name: "Add comment automation" });
    expect(button).toBeDisabled();
    expect(button).toHaveAccessibleDescription("Choose an account first.");
  });
});

describe("PostComposer loading and access", () => {
  it("says when the post doesn't exist", async () => {
    renderWithApi(<PostComposer id="gone" />, {
      handlers: { "GET /v1/w/:wid/scheduled-posts/:id": () => problem(404, "not_found", "Not found") },
    });
    expect(await screen.findByText("Post not found")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to Schedule" })).toHaveAttribute("href", "/w/maple/schedule");
  });

  it("tells an agent that scheduling is for owners and admins", () => {
    renderWithApi(<ComposerRoute />, { ws: { ...workspace, role: "agent" } });
    expect(screen.getByText("Scheduling is for owners and admins")).toBeInTheDocument();
  });

  it("duplicates and deletes from the More menu", async () => {
    const user = userEvent.setup();
    renderComposer({
      initial: readyPost(),
      handlers: {
        "POST /v1/w/:wid/scheduled-posts/:id/duplicate": () => json(readyPost({ id: "sp2" }), 201),
        "DELETE /v1/w/:wid/scheduled-posts/:id": () => new Response(null, { status: 204 }),
      },
    });
    await user.click(await screen.findByRole("button", { name: "More actions" }));
    await user.click(await screen.findByRole("menuitem", { name: "Duplicate" }));
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/w/maple/schedule/sp2"));
    await user.click(screen.getByRole("button", { name: "More actions" }));
    await user.click(await screen.findByRole("menuitem", { name: "Delete" }));
    await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/w/maple/schedule"));
  });
});
