import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { youtubeCopy } from "@/lib/copy";
import { DEFAULT_YOUTUBE_OPTIONS, type YouTubeOptions as Options } from "@/lib/publishing/rules";
import { renderWithApi } from "@/test/api";
import { mediaAsset, target } from "@/test/composer-fixtures";

import type { Uploader } from "./use-media-uploads";
import { savedThumbnail, YouTubeOptions } from "./YouTubeOptions";

type Saved = Parameters<typeof YouTubeOptions>[0]["saved"];

function Harness({ upload, start = DEFAULT_YOUTUBE_OPTIONS, saved = null, onOptions = () => {} }: {
  upload?: Uploader;
  start?: Options;
  saved?: Saved;
  onOptions?: (options: Options) => void;
}) {
  const [options, setOptions] = useState(start);
  return (
    <YouTubeOptions
      options={options}
      route="direct"
      wid="w1"
      upload={upload}
      saved={saved}
      onChange={(patch) => {
        const next = { ...options, ...patch };
        setOptions(next);
        onOptions(next);
      }}
    />
  );
}

const thumb = () => screen.getByRole("group", { name: "Thumbnail (optional)" });
const file = (name: string, size = 1000, type = "image/jpeg") => {
  const f = new File(["x"], name, { type });
  Object.defineProperty(f, "size", { value: size });
  return f;
};

describe("the YouTube thumbnail (C-203)", () => {
  it("uploads a picked JPG, shows it at 16:9 and sets it on the options", async () => {
    const upload = vi.fn<Uploader>(async () => mediaAsset({ id: "th1", secure_url: "https://res.cloudinary.com/demo/image/upload/th1.jpg" }));
    const onOptions = vi.fn();
    renderWithApi(<Harness upload={upload} onOptions={onOptions} />);
    expect(within(thumb()).getByText(youtubeCopy.thumbnailNote)).toBeInTheDocument();
    expect(within(thumb()).queryByRole("img")).toBeNull();

    await userEvent.upload(within(thumb()).getByLabelText("Thumbnail image"), file("cover.jpg"));
    await waitFor(() => expect(onOptions).toHaveBeenLastCalledWith(expect.objectContaining({ thumbnail_media_id: "th1" })));
    expect(upload).toHaveBeenCalledOnce();
    expect(within(thumb()).getByRole("img", { name: "Thumbnail" })).toHaveAttribute("src", "https://res.cloudinary.com/demo/image/upload/th1.jpg");
    expect(within(thumb()).getByRole("button", { name: /Replace/ })).toBeInTheDocument();
    expect(within(thumb()).getByText(youtubeCopy.thumbnailRemove)).toBeInTheDocument();
  });

  it("refuses a wrong type or a file over 2 MB before uploading, with the API's words", async () => {
    const upload = vi.fn<Uploader>();
    const user = userEvent.setup({ applyAccept: false });
    renderWithApi(<Harness upload={upload} />);
    const input = within(thumb()).getByLabelText("Thumbnail image");
    await user.upload(input, file("cover.webp", 1000, "image/webp"));
    expect(within(thumb()).getByRole("alert")).toHaveTextContent("Use a JPG or PNG image for the thumbnail.");
    await user.upload(input, file("cover.png", 2 * 1024 * 1024 + 1, "image/png"));
    expect(within(thumb()).getByRole("alert")).toHaveTextContent("The thumbnail can be up to 2 MB.");
    expect(upload).not.toHaveBeenCalled();
  });

  it("removes the thumbnail from the options", async () => {
    const onOptions = vi.fn();
    const saved: Saved = { route: "direct", state: "scheduled", thumbnail_url: "https://cdn.test/th1.jpg", thumbnail_status: "set" };
    renderWithApi(<Harness start={{ ...DEFAULT_YOUTUBE_OPTIONS, thumbnail_media_id: "th1" }} saved={saved} onOptions={onOptions} />);
    expect(within(thumb()).getByRole("img", { name: "Thumbnail" })).toHaveAttribute("src", "https://cdn.test/th1.jpg");
    expect(within(thumb()).getByTestId("youtube-thumbnail-status")).toHaveTextContent("Set on YouTube.");
    await userEvent.click(within(thumb()).getByRole("button", { name: "Remove" }));
    expect(onOptions).toHaveBeenLastCalledWith(expect.objectContaining({ thumbnail_media_id: null }));
    expect(within(thumb()).queryByRole("img")).toBeNull();
    expect(within(thumb()).getByRole("button", { name: /Choose an image/ })).toBeInTheDocument();
  });

  it("shows YouTube's refusal as a warning", () => {
    const error = "YouTube didn't take the thumbnail: custom thumbnails need a verified channel. Verify at youtube.com/verify, then pick the thumbnail again.";
    const saved: Saved = { route: "direct", state: "scheduled", thumbnail_status: "failed", thumbnail_error: error };
    renderWithApi(<Harness start={{ ...DEFAULT_YOUTUBE_OPTIONS, thumbnail_media_id: "th1" }} saved={saved} />);
    expect(within(thumb()).getByRole("alert")).toHaveTextContent(error);
  });

  it("reads the saved state only for the same image", () => {
    const youtube = { route: "direct" as const, state: "scheduled" as const, thumbnail_status: "set" as const };
    const targets = [target({ social_account_id: "y1", options: { ...DEFAULT_YOUTUBE_OPTIONS, thumbnail_media_id: "th1" }, youtube } as never)];
    expect(savedThumbnail(targets, "th1")).toEqual(youtube);
    expect(savedThumbnail(targets, "th2")).toBeNull();
    expect(savedThumbnail(targets, null)).toBeNull();
  });
});
