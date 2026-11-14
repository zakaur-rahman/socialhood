import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import type { YouTubeChannel } from "@/lib/api/types";
import { account, json, problem, renderWithApi } from "@/test/api";

import { YouTubeChannelsDialog } from "./YouTubeChannelsDialog";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});

beforeEach(() => {
  toast.success.mockReset();
  toast.error.mockReset();
});

function channel(overrides: Partial<YouTubeChannel> = {}): YouTubeChannel {
  return { channel_id: "UC1", title: "Maple Bakery", handle: "@maplebakery", avatar_url: null, connected: false, ...overrides };
}

const CHANNELS = [
  channel(),
  channel({ channel_id: "UC2", title: "Maple Cafe", handle: null }),
  channel({ channel_id: "UC3", title: "Old Channel", handle: "@old", connected: true }),
];

function renderDialog(list: () => Response, connect: () => Response = () => json({ items: [account({ platform: "youtube" })] })) {
  const onClose = vi.fn();
  const view = renderWithApi(<YouTubeChannelsDialog wid="w1" nonce="n0nce" onClose={onClose} />, {
    handlers: {
      "POST /v1/w/:wid/social-accounts/youtube/channels": list,
      "POST /v1/w/:wid/social-accounts/youtube/connect-channels": connect,
    },
  });
  return { ...view, onClose };
}

describe("the channels dialog", () => {
  it("lists the channels with the nonce; one already connected can't be picked", async () => {
    const { calls } = renderDialog(() => json({ items: CHANNELS }));
    expect(await screen.findByRole("heading", { name: "Choose your YouTube channel" })).toBeInTheDocument();
    expect(await screen.findByRole("radio", { name: /Maple Bakery/ })).toBeEnabled();
    expect(calls.find((c) => c.path.endsWith("/youtube/channels"))?.body).toEqual({ nonce: "n0nce" });
    expect(screen.getByText("@maplebakery")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Old Channel/ })).toBeDisabled();
    expect(screen.getByText("Connected")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Connect channel" })).toBeDisabled();
  });

  it("connects exactly the picked channel, names it and closes", async () => {
    const user = userEvent.setup();
    const { calls, onClose } = renderDialog(() => json({ items: CHANNELS }));
    await user.click(await screen.findByRole("radio", { name: /Maple Cafe/ }));
    await user.click(screen.getByRole("button", { name: "Connect channel" }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(calls.find((c) => c.path.endsWith("/youtube/connect-channels"))?.body).toEqual({
      nonce: "n0nce",
      channel_ids: ["UC2"],
    });
    expect(toast.success).toHaveBeenCalledWith("YouTube connected: Maple Cafe");
  });

  it("pre-picks the only channel left to connect", async () => {
    renderDialog(() => json({ items: [channel()] }));
    expect(await screen.findByRole("radio", { name: /Maple Bakery/ })).toBeChecked();
  });

  it("keeps the list open when the plan refuses", async () => {
    const user = userEvent.setup();
    const { onClose } = renderDialog(
      () => json({ items: [channel()] }),
      () => problem(402, "quota_exceeded", "Your plan includes 1 YouTube channel.", { entitlement: "youtube_accounts", limit: 1 }),
    );
    await screen.findByRole("radio", { name: /Maple Bakery/ });
    await user.click(screen.getByRole("button", { name: "Connect channel" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Connect channel" })).toBeEnabled());
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByRole("radiogroup", { name: "Your YouTube channels" })).toBeInTheDocument();
  });

  it.each([
    [problem(404, "not_found", "gone"), "That connection link expired. Close this and connect YouTube again."],
    [problem(502, "platform_error", "nope"), "YouTube didn't respond. Close this and connect YouTube again."],
  ])("explains a list that didn't load", async (response, message) => {
    renderDialog(() => response);
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
  });

  it("is closed without a nonce", () => {
    renderWithApi(<YouTubeChannelsDialog wid="w1" nonce={null} onClose={vi.fn()} />);
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
