import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentProps } from "react";
import { describe, expect, it, vi } from "vitest";

import { assetInfo } from "@/test/composer-fixtures";

import { MediaTray, moveItem, type TrayEntry } from "./MediaTray";
import type { UploadItem } from "./use-media-uploads";

function upload(overrides: Partial<UploadItem> = {}): UploadItem {
  return {
    id: "u1",
    file: new File(["x"], "look.jpg", { type: "image/jpeg" }),
    kind: "image",
    previewUrl: null,
    progress: 0.4,
    status: "uploading",
    error: null,
    replaces: null,
    ...overrides,
  };
}

function renderTray(props: Partial<ComponentProps<typeof MediaTray>> = {}) {
  const handlers = {
    onFiles: vi.fn(),
    onOpenLibrary: vi.fn(),
    onRemove: vi.fn(),
    onMove: vi.fn(),
    onCrop: vi.fn(),
    onRetryUpload: vi.fn(),
    onRemoveUpload: vi.fn(),
  };
  render(<MediaTray entries={[]} uploads={[]} format={null} notice={null} {...handlers} {...props} />);
  return handlers;
}

const entry = (overrides: Parameters<typeof assetInfo>[0] = {}, replacing: UploadItem | null = null): TrayEntry => ({
  asset: assetInfo(overrides),
  replacing,
});

describe("MediaTray (UX-SCR-13, UX-CMP-02)", () => {
  it("empty: offers the device and the library", async () => {
    const user = userEvent.setup();
    const handlers = renderTray();
    expect(screen.queryByRole("list", { name: "Post media" })).not.toBeInTheDocument();
    expect(screen.queryByTestId("post-format")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Media library" }));
    expect(handlers.onOpenLibrary).toHaveBeenCalledOnce();
    const file = new File(["x"], "dress.jpg", { type: "image/jpeg" });
    await user.upload(screen.getByTestId("composer-media-input"), file);
    expect(handlers.onFiles).toHaveBeenCalledWith([file]);
  });

  it("image: one photo shows the Image format", () => {
    renderTray({ entries: [entry()], format: "image" });
    expect(screen.getByTestId("post-format")).toHaveTextContent("Image");
    expect(screen.getByRole("listitem", { name: "Photo 1" })).toBeInTheDocument();
  });

  it("carousel: counts the items; Reel: one video with its length", () => {
    const { unmount } = render(
      <MediaTray
        entries={[entry(), entry({ id: "as2", resource_type: "video", duration_s: 42, thumbnail_url: null })]}
        uploads={[]}
        format="carousel"
        notice={null}
        onFiles={vi.fn()}
        onOpenLibrary={vi.fn()}
        onRemove={vi.fn()}
        onMove={vi.fn()}
        onCrop={vi.fn()}
        onRetryUpload={vi.fn()}
        onRemoveUpload={vi.fn()}
      />,
    );
    expect(screen.getByTestId("post-format")).toHaveTextContent("Carousel · 2 items");
    expect(within(screen.getByRole("listitem", { name: "Video 2" })).getByText("0:42")).toBeInTheDocument();
    unmount();
    renderTray({ entries: [entry({ resource_type: "video", duration_s: 15 })], format: "reel" });
    expect(screen.getByTestId("post-format")).toHaveTextContent("Reel");
  });

  it("crop needed: a tall photo is marked and its button opens the crop", async () => {
    const user = userEvent.setup();
    const handlers = renderTray({ entries: [entry({ id: "tall", width: 1080, height: 1920 })], format: "image" });
    const tile = screen.getByRole("listitem", { name: "Photo 1" });
    expect(tile).toHaveAttribute("data-crop", "tall");
    await user.click(within(tile).getByRole("button", { name: /Crop needed/ }));
    expect(handlers.onCrop).toHaveBeenCalledWith("tall");
  });

  it("over limits: a video over 90 s is marked", () => {
    renderTray({ entries: [entry({ resource_type: "video", duration_s: 120 })], format: "reel" });
    expect(screen.getByText("Over 90 s")).toBeInTheDocument();
  });

  it("uploading: real progress, then Processing… once every byte is sent", () => {
    const { rerender } = render(
      <MediaTray entries={[]} uploads={[upload()]} format={null} notice={null} onFiles={vi.fn()} onOpenLibrary={vi.fn()} onRemove={vi.fn()} onMove={vi.fn()} onCrop={vi.fn()} onRetryUpload={vi.fn()} onRemoveUpload={vi.fn()} />,
    );
    const bar = screen.getByRole("progressbar", { name: "Uploading look.jpg" });
    expect(bar).toHaveAttribute("aria-valuenow", "40");
    expect(screen.getByText("40%")).toBeInTheDocument();
    rerender(
      <MediaTray
        entries={[]}
        uploads={[upload({ progress: 1, status: "processing" })]}
        format={null}
        notice={null}
        onFiles={vi.fn()}
        onOpenLibrary={vi.fn()}
        onRemove={vi.fn()}
        onMove={vi.fn()}
        onCrop={vi.fn()}
        onRetryUpload={vi.fn()}
        onRemoveUpload={vi.fn()}
      />,
    );
    expect(screen.getByText("Processing…")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuetext", "Processing");
  });

  it("upload failed: the reason, Retry and Remove", async () => {
    const user = userEvent.setup();
    const handlers = renderTray({ uploads: [upload({ status: "failed", error: "The upload didn't finish. Try again." })] });
    expect(screen.getByRole("listitem", { name: "look.jpg" })).toHaveAttribute("data-status", "failed");
    expect(screen.getByText("The upload didn't finish. Try again.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry uploading look.jpg" }));
    expect(handlers.onRetryUpload).toHaveBeenCalledWith("u1");
    await user.click(screen.getByRole("button", { name: "Remove look.jpg" }));
    expect(handlers.onRemoveUpload).toHaveBeenCalledWith("u1");
  });

  it("a crop uploading shows its progress on the photo it replaces", () => {
    renderTray({ entries: [entry({}, upload({ replaces: "as1", progress: 0.7 }))], format: "image" });
    expect(screen.getByRole("progressbar", { name: "Uploading the crop of Photo 1" })).toHaveAttribute("aria-valuenow", "70");
  });

  it("reorders with the arrow keys on the handle and announces it; removes", async () => {
    const user = userEvent.setup();
    const handlers = renderTray({ entries: [entry(), entry({ id: "as2" })], format: "carousel" });
    screen.getByRole("button", { name: "Move Photo 1" }).focus();
    await user.keyboard("{ArrowRight}");
    expect(handlers.onMove).toHaveBeenCalledWith(0, 1);
    expect(screen.getByRole("status")).toHaveTextContent("Moved Photo 1 to position 2 of 2.");
    await user.keyboard("{ArrowLeft}");
    expect(handlers.onMove).toHaveBeenCalledTimes(1); // already first
    await user.click(screen.getByRole("button", { name: "Remove Photo 2" }));
    expect(handlers.onRemove).toHaveBeenCalledWith("as2");
  });

  it("reorders by dragging the handle", () => {
    const handlers = renderTray({ entries: [entry(), entry({ id: "as2" }), entry({ id: "as3" })], format: "carousel" });
    const tiles = screen.getAllByTestId("media-tile");
    tiles.forEach((tile, index) => {
      tile.getBoundingClientRect = () =>
        ({ top: 0, bottom: 100, left: index * 110, right: index * 110 + 100, width: 100, height: 100, x: index * 110, y: 0 }) as DOMRect;
    });
    const handle = screen.getByRole("button", { name: "Move Photo 1" });
    fireEvent.pointerDown(handle, { pointerId: 1, button: 0, clientX: 10, clientY: 50 });
    fireEvent.pointerMove(handle, { pointerId: 1, clientX: 300, clientY: 50 });
    fireEvent.pointerUp(handle, { pointerId: 1, clientX: 300, clientY: 50 });
    expect(handlers.onMove).toHaveBeenCalledWith(0, 2);
  });

  it("stops adding at 10 items and says why", () => {
    const entries = Array.from({ length: 10 }, (_, index) => entry({ id: `as${index}` }));
    renderTray({ entries, format: "carousel" });
    expect(screen.getByRole("button", { name: "Add from device" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Media library" })).toBeDisabled();
    expect(screen.getByText("A post can have up to 10 photos and videos.")).toBeInTheDocument();
  });

  it("shows why picked files were refused", () => {
    renderTray({ notice: "menu.pdf: Instagram can't publish this file." });
    expect(screen.getByRole("alert")).toHaveTextContent("menu.pdf: Instagram can't publish this file.");
  });
});

describe("moveItem", () => {
  it("moves one item", () => {
    expect(moveItem(["a", "b", "c"], 0, 2)).toEqual(["b", "c", "a"]);
    expect(moveItem(["a", "b", "c"], 2, 0)).toEqual(["c", "a", "b"]);
  });
});
