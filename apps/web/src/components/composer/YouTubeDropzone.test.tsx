import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { YouTubeUploadError, type Uploader, type UploadToYouTubeOptions } from "@/lib/youtube/upload";

import { formatBytes, useYouTubeUpload, YouTubeDropzone } from "./YouTubeDropzone";

/** The dropzone as the AI-app page uses it: picking a file starts the upload. */
function Harness({ uploader, onDone }: { uploader: Uploader; onDone?: (id: string) => void }) {
  const upload = useYouTubeUpload(uploader);
  const send = (file: File) =>
    upload.run("https://www.googleapis.com/upload/x", 4, file).then(
      (id) => onDone?.(id),
      () => {},
    );
  return <YouTubeDropzone upload={upload} channelName="Maple Bakery" onPicked={send} onRetry={() => upload.file && void send(upload.file)} />;
}

const video = (size = 10) => new File([new Uint8Array(size)], "dawn.mp4", { type: "video/mp4" });

describe("YouTubeDropzone", () => {
  it("shows the file, its progress, then the channel it reached", async () => {
    const held: { options?: UploadToYouTubeOptions; finish?: (id: string) => void } = {};
    const uploader = vi.fn<Uploader>(
      (given) =>
        new Promise<string>((resolve) => {
          held.options = given;
          held.finish = resolve;
        }),
    );
    const onDone = vi.fn();
    render(<Harness uploader={uploader} onDone={onDone} />);
    await userEvent.upload(screen.getByLabelText("Choose a video for YouTube"), video());
    expect(screen.getByTestId("youtube-file-name")).toHaveTextContent("dawn.mp4");
    expect(uploader).toHaveBeenCalledWith(expect.objectContaining({ uploadUrl: "https://www.googleapis.com/upload/x", chunkBytes: 4 }));

    act(() => held.options?.onProgress?.(4, 10));
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "40");
    expect(screen.getByText(/Uploading to YouTube: 40%/)).toBeInTheDocument();

    // Closing the tab mid-upload asks first.
    const event = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);

    await act(async () => held.finish?.("vid9"));
    expect(await screen.findByText(/Uploaded to Maple Bakery\./)).toBeInTheDocument();
    expect(onDone).toHaveBeenCalledWith("vid9");
    const after = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(after);
    expect(after.defaultPrevented).toBe(false);
  });

  it("says why an upload failed and tries again", async () => {
    const uploader = vi
      .fn<Uploader>()
      .mockRejectedValueOnce(new YouTubeUploadError("The connection to YouTube keeps dropping. Try again.", 503))
      .mockResolvedValueOnce("vid2");
    const onDone = vi.fn();
    render(<Harness uploader={uploader} onDone={onDone} />);
    await userEvent.upload(screen.getByLabelText("Choose a video for YouTube"), video());
    expect(await screen.findByRole("alert")).toHaveTextContent("keeps dropping");
    await userEvent.click(screen.getByRole("button", { name: /Try again/ }));
    await waitFor(() => expect(onDone).toHaveBeenCalledWith("vid2"));
    expect(uploader).toHaveBeenCalledTimes(2);
  });

  it("refuses a file that isn't a video before uploading", async () => {
    const uploader = vi.fn<Uploader>();
    render(<Harness uploader={uploader} />);
    await userEvent.upload(screen.getByLabelText("Choose a video for YouTube"), new File(["x"], "menu.pdf", { type: "application/pdf" }), {
      applyAccept: false,
    });
    expect(screen.getByRole("alert")).toHaveTextContent("YouTube takes video files");
    expect(uploader).not.toHaveBeenCalled();
  });

  it("formats sizes", () => {
    expect(formatBytes(2048)).toBe("2 KB");
    expect(formatBytes(5 * 1024 * 1024)).toBe("5.0 MB");
    expect(formatBytes(3 * 1024 * 1024 * 1024)).toBe("3.0 GB");
  });
});
