import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentProps } from "react";
import { beforeAll, describe, expect, it } from "vitest";

import { account, json, post, renderWithApi, type Call } from "@/test/api";
import { assetInfo } from "@/test/composer-fixtures";

import { PostPreview } from "./PostPreview";

beforeAll(() => {
  // jsdom lacks what Radix Select calls on open (the account switcher).
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});

const maple = account({ id: "a1", username: "maple.bakery", profile_picture_url: "https://img.test/maple.jpg" });
const studio = account({ id: "a2", username: "maple.studio" });

function renderPreview(props: Partial<ComponentProps<typeof PostPreview>> = {}, posts = [post()]) {
  const calls: Call[] = [];
  const view = renderWithApi(
    <PostPreview
      wid="w1"
      accounts={[maple]}
      captionFor={() => "Fresh #linen for @priya"}
      captionsDiffer={false}
      assets={[assetInfo()]}
      format="image"
      firstComment={null}
      {...props}
    />,
    {
      handlers: {
        "GET /v1/w/:wid/posts": (call) => {
          calls.push(call);
          return json({ items: posts, next_cursor: null });
        },
      },
    },
  );
  return { ...view, calls };
}

describe("PostPreview (FR-PUB-03, UX-CMP-02)", () => {
  it("image: the feed post with the real account name, caption and first comment", () => {
    renderPreview({ firstComment: "#summer #ootd" });
    const feed = screen.getByRole("article", { name: "Feed preview" });
    expect(within(feed).getAllByText("maple.bakery").length).toBeGreaterThan(0);
    expect(within(feed).getByTestId("preview-caption")).toHaveTextContent("maple.bakery Fresh #linen for @priya");
    expect(within(feed).getByText("#linen")).toHaveClass("text-brand-fg");
    expect(within(feed).getByTestId("preview-first-comment")).toHaveTextContent("#summer #ootd");
  });

  it("carousel: steps through the items", async () => {
    const user = userEvent.setup();
    renderPreview({ assets: [assetInfo(), assetInfo({ id: "as2" }), assetInfo({ id: "as3" })], format: "carousel" });
    expect(screen.getByTestId("carousel-counter")).toHaveTextContent("1/3");
    expect(screen.queryByRole("button", { name: "Previous item" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Next item" }));
    await user.click(screen.getByRole("button", { name: "Next item" }));
    expect(screen.getByTestId("carousel-counter")).toHaveTextContent("3/3");
    expect(screen.queryByRole("button", { name: "Next item" })).not.toBeInTheDocument();
  });

  it("Reel: opens on the Reel tab for a single video", () => {
    renderPreview({ assets: [assetInfo({ resource_type: "video", width: 1080, height: 1920, thumbnail_url: null })], format: "reel" });
    expect(screen.getByRole("tab", { name: "Reel" })).toHaveAttribute("aria-selected", "true");
    const reel = screen.getByRole("article", { name: "Reel preview" });
    expect(within(reel).getByTestId("reel-caption")).toHaveTextContent("Fresh #linen for @priya");
    expect(within(reel).getByLabelText("Video")).toBeInTheDocument();
  });

  it("Story: a 9:16 phone with the account, no caption and no tabs (GR-39)", () => {
    renderPreview({ assets: [assetInfo({ width: 1080, height: 1920 })], format: "story" });
    const story = screen.getByRole("article", { name: "Story preview" });
    expect(within(story).getByText("maple.bakery")).toBeInTheDocument();
    expect(story).not.toHaveTextContent("Fresh #linen");
    expect(screen.queryByRole("tab", { name: "Feed" })).not.toBeInTheDocument();
    expect(screen.getByText("Disappears 24 hours after it is published.")).toBeInTheDocument();
  });

  it("a Facebook Page shows its text and photos in a Facebook post (GR-30)", () => {
    const page = account({ id: "p1", platform: "facebook", username: "maple.page", display_name: "Maple Page" });
    renderPreview({ accounts: [page], format: "carousel", assets: [assetInfo(), assetInfo({ id: "as2" })], captionFor: () => "Open late #tonight" });
    const post = screen.getByRole("article", { name: "Facebook preview" });
    expect(within(post).getByTestId("fb-caption")).toHaveTextContent("Open late #tonight");
    expect(within(post).getByRole("list", { name: "Photos" }).children).toHaveLength(2);
    expect(screen.queryByRole("tab", { name: "Feed" })).not.toBeInTheDocument();
  });

  it("a text post for a Page says where its text will show", () => {
    const page = account({ id: "p1", platform: "facebook", username: "maple.page", display_name: "Maple Page" });
    renderPreview({ accounts: [page], format: "text", assets: [], captionFor: () => "" });
    expect(screen.getByText(/Maple Page.s post text shows here/)).toBeInTheDocument();
  });

  it("switches between an Instagram account and a Page when the post goes to both", () => {
    const page = account({ id: "p1", platform: "facebook", username: "maple.page" });
    renderPreview({ accounts: [maple, page] });
    expect(screen.getByRole("combobox", { name: "Account" })).toBeInTheDocument();
  });

  it("Story without media says what to add", () => {
    renderPreview({ assets: [], format: null });
    expect(screen.getByRole("tab", { name: "Feed" })).toBeInTheDocument();
    renderPreview({ assets: [], format: "story" });
    expect(screen.getByText("Add one photo or video to see the Story.")).toBeInTheDocument();
  });

  it("explains the Reel tab when the post isn't a single video", async () => {
    const user = userEvent.setup();
    renderPreview();
    await user.click(screen.getByRole("tab", { name: "Reel" }));
    expect(screen.getByText("A Reel preview shows when the post is a single video.")).toBeInTheDocument();
  });

  it("grid: this post before the account's last 8 posts", async () => {
    const user = userEvent.setup();
    const recent = Array.from({ length: 10 }, (_, index) => post({ id: `po${index}` }));
    const { calls } = renderPreview({}, recent);
    await user.click(screen.getByRole("tab", { name: "Grid" }));
    const grid = await screen.findByRole("list", { name: "Profile grid" });
    await within(grid).findAllByRole("listitem");
    const items = within(grid).getAllByRole("listitem");
    expect(items).toHaveLength(9);
    expect(items[0]).toHaveAccessibleName("This post");
    expect(within(items[0]).getByText("New")).toBeInTheDocument();
    expect(calls[0].url.searchParams.get("account_id")).toBe("a1");
  });

  it("without media or caption: says what will show", () => {
    renderPreview({ assets: [], format: null, captionFor: () => "" });
    expect(screen.getByText("Add a photo or video to see the preview.")).toBeInTheDocument();
    expect(screen.getByText("Your caption shows here.")).toBeInTheDocument();
  });

  it("switches accounts when captions differ", async () => {
    const user = userEvent.setup();
    renderPreview({
      accounts: [maple, studio],
      captionsDiffer: true,
      captionFor: (id) => (id === "a2" ? "Studio caption" : "Bakery caption"),
    });
    expect(screen.getByTestId("preview-caption")).toHaveTextContent("maple.bakery Bakery caption");
    await user.click(screen.getByRole("combobox", { name: "Account" }));
    await user.click(await screen.findByRole("option", { name: "@maple.studio" }));
    expect(screen.getByTestId("preview-caption")).toHaveTextContent("maple.studio Studio caption");
  });

  it("has no account switcher when every account shares the caption", () => {
    renderPreview({ accounts: [maple, studio] });
    expect(screen.queryByRole("combobox", { name: "Account" })).not.toBeInTheDocument();
  });
});
