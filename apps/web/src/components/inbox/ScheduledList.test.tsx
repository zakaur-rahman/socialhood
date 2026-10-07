import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ScheduledMessage } from "@/lib/api/types";
import { json, noContent, renderWithApi, type Call } from "@/test/api";

import { ScheduledList } from "./ScheduledList";

const now = new Date("2026-09-28T12:00:00Z");

const pending: ScheduledMessage = {
  id: "s1",
  conversation_id: "c1",
  text: "Following up on the Aria dress",
  attachment_asset_ids: [],
  send_at: "2026-09-28T13:00:00Z", // 18:30 in Kolkata
  status: "scheduled",
  error: null,
  contact: { display_name: "Priya Nair", username: "priya.styles", profile_picture_url: null },
  platform: "instagram",
};
const expired: ScheduledMessage = {
  ...pending,
  id: "s2",
  status: "expired",
  error: { code: "reply_window_closed", message: "The reply window closed before it was sent." },
};

function renderList(items: ScheduledMessage[], extra: Record<string, (call: Call) => Response> = {}) {
  const onOpen = vi.fn();
  const view = renderWithApi(<ScheduledList onOpen={onOpen} now={now} />, {
    handlers: { "GET /v1/w/:wid/scheduled-messages": () => json({ items, next_cursor: null }), ...extra },
  });
  return { ...view, onOpen };
}

describe("Scheduled tab (UX-INB-10, FR-SMS-02)", () => {
  it("lists scheduled messages with time and status; a card opens its conversation", async () => {
    const user = userEvent.setup();
    const { onOpen } = renderList([pending, expired]);
    const [card] = await screen.findAllByRole("article", { name: "Scheduled message to Priya Nair" });
    expect(within(card).getByText("Today 18:30")).toBeInTheDocument();
    expect(within(card).getByText("Scheduled")).toBeInTheDocument();
    expect(screen.getByText("Expired")).toBeInTheDocument();
    expect(screen.getByText("The reply window closed before it was sent.")).toBeInTheDocument();
    await user.click(within(card).getByRole("link"));
    expect(onOpen).toHaveBeenCalledWith("c1");
  });

  it("only pending ones can be edited or canceled; Cancel confirms first", async () => {
    const user = userEvent.setup();
    const { calls } = renderList([pending, expired], {
      "DELETE /v1/w/:wid/scheduled-messages/:id": () => noContent(),
    });
    await screen.findByText("Expired");
    expect(screen.getAllByRole("button", { name: "Edit" })).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    await user.click(await screen.findByRole("button", { name: "Cancel message" }));
    await waitFor(() => expect(calls.some((c) => c.method === "DELETE" && c.path === "/v1/w/w1/scheduled-messages/s1")).toBe(true));
    await waitFor(() => expect(screen.queryByText("Scheduled")).not.toBeInTheDocument());
  });

  // UI-031 (UI-ISS-105): the cancel confirmation is an AlertDialog; keeping the message returns focus.
  it("Cancel asks in an alert dialog, and Keep it returns focus to Cancel", async () => {
    const user = userEvent.setup();
    const { calls } = renderList([pending]);
    const trigger = await screen.findByRole("button", { name: "Cancel" });
    await user.click(trigger);
    const dialog = await screen.findByRole("alertdialog", { name: "Cancel this scheduled message?" });
    await user.click(within(dialog).getByRole("button", { name: "Keep it" }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
    expect(trigger).toHaveFocus();
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
  });

  it("edits the text and the time", async () => {
    const user = userEvent.setup();
    const { calls } = renderList([pending], {
      "PATCH /v1/w/:wid/scheduled-messages/:id": (call) => json({ ...pending, ...(call.body as object) }),
    });
    await user.click(await screen.findByRole("button", { name: "Edit" }));
    const dialog = await screen.findByRole("dialog");
    const text = within(dialog).getByLabelText("Message");
    await user.clear(text);
    await user.type(text, "See you soon");
    await user.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(calls.some((c) => c.method === "PATCH")).toBe(true));
    expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({ text: "See you soon", send_at: "2026-09-28T13:00:00.000Z" });
  });

  it("Esc puts focus back on Edit, and the next opening starts from the message as it is (UX-A11Y-02)", async () => {
    const user = userEvent.setup();
    renderList([pending]);
    const edit = await screen.findByRole("button", { name: "Edit" });
    edit.focus();
    await user.keyboard("{Enter}");
    const dialog = await screen.findByRole("dialog", { name: "Edit scheduled message" });
    await user.type(within(dialog).getByLabelText("Message"), " later");
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(edit).toHaveFocus());

    await user.keyboard("{Enter}");
    const again = await screen.findByRole("dialog", { name: "Edit scheduled message" });
    expect(within(again).getByLabelText("Message")).toHaveValue("Following up on the Aria dress");
  });

  it("shows the empty state", async () => {
    renderList([]);
    expect(await screen.findByText("No scheduled messages")).toBeInTheDocument();
    expect(screen.getByText("Schedule a reply from any conversation's composer.")).toBeInTheDocument();
  });
});
