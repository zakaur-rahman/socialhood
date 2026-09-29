import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Route } from "next";
import { describe, expect, it, vi } from "vitest";

import type { Attachment, Message } from "@/lib/api/types";
import { sendFailure } from "@/lib/copy";
import { message } from "@/test/api";

import { MessageBubble } from "./MessageBubble";

const contact = { id: "p1", name: "Priya Nair", pictureUrl: null };

function renderBubble(overrides: Partial<Message> = {}, props: Partial<Parameters<typeof MessageBubble>[0]> = {}) {
  const m = message(overrides);
  const view = render(
    <MessageBubble message={m} platform="instagram" timeZone="Asia/Kolkata" contact={contact} groupEnd {...props} />,
  );
  return { ...view, row: view.container.querySelector(`[data-message-id="${m.id}"]`) as HTMLElement };
}

const out = { direction: "outbound", source: "human", status: "sent" } as const;

describe("MessageBubble variants (UX-INB-06)", () => {
  it("customer: left, neutral, avatar at the end of a group, time in the workspace zone", () => {
    const { row } = renderBubble({ text: "Is the Aria dress in stock?", occurred_at: "2026-09-28T12:42:00Z" });
    expect(row).toHaveAttribute("data-direction", "inbound");
    expect(row.querySelector('[data-variant="customer"]')).toHaveClass("bg-field", "rounded-bl-md");
    expect(screen.getByText("P")).toBeInTheDocument(); // avatar initial
    expect(screen.getByText("18:12")).toBeInTheDocument();
  });

  it("marks an edited message", () => {
    renderBubble({ text: "Is the rye sourdough available today?", edited_at: "2026-09-28T12:45:00Z" });
    expect(screen.getByText("Edited ·")).toBeInTheDocument();
  });

  it("shows an unsent message without its content", () => {
    renderBubble({ text: null, attachments: [], deleted_at: "2026-09-28T12:46:00Z", edited_at: "2026-09-28T12:45:00Z" });
    expect(screen.getByText("Message unsent")).toHaveClass("italic");
    expect(screen.queryByText("Edited ·")).not.toBeInTheDocument();
  });

  it("shows a heart sticker large, without a bubble", () => {
    const { row } = renderBubble({ ...out, kind: "sticker", text: "❤️", attachments: [] });
    expect(screen.getByRole("img", { name: "Heart sticker" })).toHaveClass("text-5xl");
    expect(row.querySelector('[data-variant="human"]')).not.toHaveClass("bg-brand-gradient");
  });

  it("hides the avatar inside a group", () => {
    render(<MessageBubble message={message()} platform="instagram" timeZone="UTC" contact={contact} groupEnd={false} />);
    expect(screen.queryByText("P")).not.toBeInTheDocument();
  });

  it("you: right, gradient, with the delivery status", () => {
    const { row } = renderBubble({ ...out, status: "delivered" });
    expect(row.querySelector('[data-variant="human"]')).toHaveClass("bg-brand-gradient", "rounded-br-md");
    expect(screen.getByRole("img", { name: "Delivered" })).toBeInTheDocument();
  });

  it.each([
    ["queued", "Queued"],
    ["sending", "Sending"],
    ["sent", "Sent"],
    ["read", "Read"],
  ] as const)("status %s is shown and announced", (status, label) => {
    renderBubble({ ...out, status });
    expect(screen.getByRole("img", { name: label })).toBeInTheDocument();
  });

  it("sending: the dimmed variant", () => {
    const { row } = renderBubble({ ...out, status: "sending" });
    expect(row.querySelector('[data-variant="sending"]')).toHaveClass("opacity-80");
  });

  it("AI auto reply: labelled Sent by AI", () => {
    const { row } = renderBubble({ ...out, source: "ai_auto" });
    expect(within(row).getByText("Sent by AI")).toBeInTheDocument();
  });

  it("automation: labelled with its name", () => {
    renderBubble({ ...out, source: "automation", automation: { id: "au1", name: "Price keyword" } });
    expect(screen.getByText("Automation · Price keyword")).toBeInTheDocument();
  });

  it("tap first's opening: its quick reply shows as a chip under the text, not a button (FR-AUT-21)", () => {
    const { row } = renderBubble({
      ...out,
      source: "automation",
      text: "Hi there! Tap below and I'll send it over 👇",
      quick_replies: [{ title: "Send me the link" }],
    });
    const chips = within(row).getByRole("list", { name: "Quick replies" });
    expect(within(chips).getByRole("listitem")).toHaveTextContent("Send me the link");
    expect(within(row).queryByRole("button", { name: "Send me the link" })).toBeNull();
    // Under the text, inside the bubble.
    const text = within(row).getByText("Hi there! Tap below and I'll send it over 👇");
    expect(text.compareDocumentPosition(chips) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(row.querySelector('[data-variant="automation"]')).toContainElement(chips);
  });

  it("shows no quick replies on a customer's message or when there are none", () => {
    const { row, unmount } = renderBubble({ text: "Send me the link", quick_replies: [{ title: "Ignored" }] });
    expect(within(row).queryByRole("list", { name: "Quick replies" })).toBeNull();
    unmount();
    const outbound = renderBubble({ ...out, quick_replies: [] });
    expect(within(outbound.row).queryByRole("list", { name: "Quick replies" })).toBeNull();
  });

  it("sent from the Instagram app: raised, labelled", () => {
    const { row } = renderBubble({ ...out, source: "native_app" });
    expect(screen.getByText("Sent from Instagram")).toBeInTheDocument();
    expect(row.querySelector('[data-variant="native_app"]')).toHaveClass("bg-raised");
  });

  it("failed: danger fill, the mapped reason, Retry and Copy text always visible", async () => {
    const onRetry = vi.fn();
    const failed = { ...out, status: "failed" as const, error: { code: "platform_unavailable", message: "timeout" }, text: "Hi!" };
    const { row } = renderBubble(failed, {
      failure: sendFailure(failed.error, { platform: "instagram", handle: "maple.bakery" }),
      onRetry,
    });
    expect(row.querySelector('[data-variant="failed"]')).toHaveClass("bg-danger-fill");
    expect(screen.getByRole("alert")).toHaveTextContent("Instagram didn't respond.");
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledOnce();
    expect(screen.getByRole("button", { name: "Copy text" })).toBeInTheDocument();
  });

  it("failed outside the window on WhatsApp: Choose template instead of Retry", async () => {
    const onChooseTemplate = vi.fn();
    const error = { code: "reply_window_closed", message: "" };
    render(
      <MessageBubble
        message={message({ ...out, status: "failed", error })}
        platform="whatsapp"
        timeZone="UTC"
        contact={contact}
        groupEnd
        failure={sendFailure(error, { platform: "whatsapp" })}
        onRetry={() => {}}
        onChooseTemplate={onChooseTemplate}
        reconnectHref={"/w/maple/settings/connections" as Route}
      />,
    );
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Choose template" }));
    expect(onChooseTemplate).toHaveBeenCalledOnce();
  });

  it("system note: centred text", () => {
    renderBubble({ direction: "system", source: "system", kind: "system", text: "AI paused until 16:40 because you replied" });
    expect(screen.getByText("AI paused until 16:40 because you replied")).toHaveClass("rounded-full");
  });

  it("reactions overlap the bubble in a pill", () => {
    renderBubble({ reactions: [{ emoji: "❤️", by: "customer", at: "2026-09-28T12:00:00Z" }] });
    expect(screen.getByLabelText("Reactions: ❤️")).toHaveClass("bg-raised");
  });

  it("unsupported: says so and links to Instagram", () => {
    renderBubble({ kind: "unsupported", text: null });
    expect(screen.getByText(/Unsupported message/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /View in Instagram/ })).toHaveAttribute("href", "https://www.instagram.com/direct/inbox/");
  });
});

function attachment(type: Attachment["type"], extra: Partial<Attachment> = {}): Attachment {
  return { id: `att-${type}`, type, url: `https://res.cloudinary.com/demo/${type}`, ...extra };
}

describe("AttachmentView (FR-INB-02)", () => {
  it("image: opens a lightbox", async () => {
    renderBubble({ kind: "image", text: null, attachments: [attachment("image")] });
    await userEvent.click(screen.getByRole("button", { name: "Open photo" }));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });

  it("video and audio: players with controls", () => {
    const { container } = renderBubble({ kind: "video", attachments: [attachment("video"), attachment("audio")] });
    expect(container.querySelector("video")).toHaveAttribute("controls");
    expect(container.querySelector("audio")).toHaveAttribute("controls");
  });

  it("file: name, size and download", () => {
    renderBubble({ kind: "file", attachments: [attachment("file", { filename: "invoice.pdf", size_bytes: 245_760 })] });
    expect(screen.getByText("invoice.pdf")).toBeInTheDocument();
    expect(screen.getByText("240 KB")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Download invoice.pdf" })).toBeInTheDocument();
  });

  it("sticker: the image alone", () => {
    renderBubble({ kind: "sticker", text: null, attachments: [attachment("sticker")] });
    expect(screen.getByRole("img", { name: "Sticker" })).toBeInTheDocument();
  });

  it("story mention, and expired stories", () => {
    const { unmount } = renderBubble({ kind: "story_mention", text: null, attachments: [attachment("story")] });
    expect(screen.getByText("Mentioned you in their story")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Story" })).toBeInTheDocument();
    unmount();
    renderBubble({ kind: "story_reply", text: "Love it", attachments: [attachment("story", { expired: true })] });
    expect(screen.getByText("Replied to your story")).toBeInTheDocument();
    expect(screen.getByText("Story expired")).toBeInTheDocument();
  });

  it("shared post: a card with View post", () => {
    renderBubble({
      kind: "share",
      text: null,
      attachments: [attachment("share", { permalink: "https://www.instagram.com/p/abc/", thumbnail_url: "https://x/y.jpg" })],
    });
    expect(screen.getByRole("link", { name: /View post/ })).toHaveAttribute("href", "https://www.instagram.com/p/abc/");
  });
});
