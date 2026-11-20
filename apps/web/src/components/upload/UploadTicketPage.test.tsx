import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { McpUploadTicket } from "@/lib/api/types";
import { json, renderWithApi } from "@/test/api";

import { UploadTicketPage } from "./UploadTicketPage";

const storage = vi.hoisted(() => ({ sendToStorage: vi.fn() }));
vi.mock("@/lib/media/upload", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/media/upload")>()),
  sendToStorage: storage.sendToStorage,
}));

const waiting: McpUploadTicket = {
  id: "t1",
  kind: "video",
  status: "waiting",
  expires_at: "2026-11-01T12:00:00Z",
  reason: null,
  media_asset_id: null,
  limits: { formats: ["mp4", "mov"], max_mb: 100 },
  upload: {
    cloud_name: "demo",
    api_key: "k",
    timestamp: 1,
    folder: "ws/w/post",
    tags: "mcp_upload_t1",
    public_id: "t1",
    allowed_formats: "mp4",
    signature: "s",
    upload_url: "https://api.cloudinary.com/v1_1/demo/video/upload",
  },
};

function setup(ticket: McpUploadTicket, completed?: McpUploadTicket) {
  const view = renderWithApi(<UploadTicketPage ticketId="t1" />, {
    handlers: {
      "GET /v1/w/:wid/mcp-uploads/:id": () => json(ticket),
      "POST /v1/w/:wid/mcp-uploads/:id/complete": () => json(completed ?? { ...ticket, status: "uploaded", upload: null }),
    },
  });
  return view;
}

describe("UploadTicketPage", () => {
  beforeEach(() => storage.sendToStorage.mockReset());

  it("sends the file to storage with the ticket's signature and completes it", async () => {
    storage.sendToStorage.mockResolvedValue({ public_id: "ws/w/post/t1" });
    const view = setup(waiting);
    const input = await screen.findByLabelText("Choose a file");
    await userEvent.upload(input, new File(["x"], "reel.mp4", { type: "video/mp4" }));
    expect(await screen.findByText("The file is in your media library.")).toBeInTheDocument();
    expect(storage.sendToStorage).toHaveBeenCalledWith(waiting.upload, expect.any(File), expect.anything());
    // The API reads the file's name from the ticket: the page sends none.
    expect(view.calls.filter((c) => c.method === "POST")).toHaveLength(1);
  });

  it("refuses a file of the wrong kind before uploading", async () => {
    setup(waiting);
    const input = await screen.findByLabelText("Choose a file");
    await userEvent.upload(input, new File(["x"], "photo.jpg", { type: "image/jpeg" }), { applyAccept: false });
    expect(await screen.findByRole("alert")).toHaveTextContent("Use an MP4 or MOV file.");
    expect(storage.sendToStorage).not.toHaveBeenCalled();
  });

  it("says when the ticket was rejected or expired", async () => {
    setup({ ...waiting, status: "rejected", reason: "Videos can be up to 15 minutes.", upload: null });
    expect(await screen.findByText("The file was rejected.")).toBeInTheDocument();
    expect(screen.getByText(/Videos can be up to 15 minutes\./)).toBeInTheDocument();
  });

  it("shows the expired ticket", async () => {
    setup({ ...waiting, status: "expired", upload: null });
    await waitFor(() => expect(screen.getByText("This upload expired.")).toBeInTheDocument());
  });
});

describe("UploadTicketPage in YouTube mode (C-195)", () => {
  beforeEach(() => storage.sendToStorage.mockReset());
  const youtubeTicket = {
    ...waiting,
    kind: "youtube",
    limits: {},
    upload: null,
    youtube: { upload_url: "https://www.googleapis.com/upload/youtube/v3/videos?upload_id=t1", chunk_bytes: 8388608, title: "Sourdough at dawn", channel_name: "Maple Bakery" },
  } as unknown as McpUploadTicket;

  it("names the video and channel, sends the file to YouTube and completes with the video id", async () => {
    const uploader = vi.fn(async () => "vid42");
    const view = renderWithApi(<UploadTicketPage ticketId="t1" youtubeUploader={uploader} />, {
      handlers: {
        "GET /v1/w/:wid/mcp-uploads/:id": () => json(youtubeTicket),
        "POST /v1/w/:wid/mcp-uploads/:id/complete": () => json({ ...youtubeTicket, status: "uploaded", youtube: null }),
      },
    });
    expect(await screen.findByTestId("youtube-ticket-title")).toHaveTextContent("Upload to YouTube: Sourdough at dawn on Maple Bakery");
    await userEvent.upload(screen.getByLabelText("Choose a video for YouTube"), new File(["x"], "dawn.mp4", { type: "video/mp4" }));
    expect(await screen.findByText("The video is on YouTube.")).toBeInTheDocument();
    expect(uploader).toHaveBeenCalledWith(expect.objectContaining({ uploadUrl: youtubeTicket.youtube!.upload_url, chunkBytes: 8388608 }));
    const complete = view.calls.find((c) => c.method === "POST");
    expect(complete?.body).toEqual({ video_id: "vid42" });
    // Never through storage.
    expect(storage.sendToStorage).not.toHaveBeenCalled();
  });
});
