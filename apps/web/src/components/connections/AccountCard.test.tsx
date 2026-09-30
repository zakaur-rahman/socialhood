import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { SocialAccount } from "@/lib/api/types";

import { AccountCard, type AccountActions } from "./AccountCard";

const base: SocialAccount = {
  id: "a1",
  platform: "instagram",
  display_name: "Maple Bakery",
  username: "maple.bakery",
  profile_picture_url: null,
  phone_number: null,
  status: "active",
  last_error: null,
  ai_mode: "suggest",
  ai_analysis_enabled: true,
  auto_hide_spam: false,
  connected_at: "2026-09-28T10:00:00Z",
  token_expires_at: "2026-11-27T10:00:00Z",
  capabilities: ["dm_send"],
  sandbox: false,
  last_synced_at: null,
};

const idle = { saving: false, reconnecting: false, retrying: false, disconnecting: false };

function actions(): AccountActions {
  return { onChange: vi.fn(), onReconnect: vi.fn(), onRetrySubscribe: vi.fn(), onDisconnect: vi.fn() };
}

function renderCard(account: Partial<SocialAccount> = {}, props: { canManage?: boolean; plan?: "free" | "pro" } = {}) {
  const handlers = actions();
  render(
    <AccountCard
      account={{ ...base, ...account }}
      plan={props.plan ?? "free"}
      canManage={props.canManage ?? true}
      busy={idle}
      actions={handlers}
    />,
  );
  return { handlers, card: screen.getByRole("article", { name: "Maple Bakery" }) };
}

describe("AccountCard (UX-SCR-07)", () => {
  it("shows the account, its status and its settings", () => {
    const { card } = renderCard();
    expect(within(card).getByText("@maple.bakery")).toBeInTheDocument();
    expect(within(card).getByText("Connected")).toBeInTheDocument();
    expect(within(card).getByRole("switch", { name: /AI analysis/ })).toBeChecked();
    expect(within(card).getByRole("switch", { name: /Hide spam comments/ })).not.toBeChecked();
    expect(within(card).queryByRole("button", { name: "Reconnect" })).not.toBeInTheDocument();
  });

  it("sends a switch change as a patch", async () => {
    const { card, handlers } = renderCard();
    await userEvent.click(within(card).getByRole("switch", { name: /Hide spam comments/ }));
    expect(handlers.onChange).toHaveBeenCalledWith({ auto_hide_spam: true });
  });

  it("offers Reconnect with the reason when the token stopped working", async () => {
    const { card, handlers } = renderCard({
      status: "needs_reconnect",
      last_error: "Instagram stopped accepting this connection.",
    });
    expect(within(card).getByText("Needs reconnecting")).toBeInTheDocument();
    expect(within(card).getByRole("status")).toHaveTextContent("Instagram stopped accepting this connection.");
    await userEvent.click(within(card).getByRole("button", { name: "Reconnect" }));
    expect(handlers.onReconnect).toHaveBeenCalledOnce();
  });

  it("offers Retry when the webhook subscription failed", async () => {
    const { card, handlers } = renderCard({ status: "error", last_error: "Couldn't subscribe to messages. Try again." });
    await userEvent.click(within(card).getByRole("button", { name: "Retry" }));
    expect(handlers.onRetrySubscribe).toHaveBeenCalledOnce();
  });

  it("hides settings and Disconnect once disconnected", () => {
    const { card } = renderCard({ status: "disconnected" });
    expect(within(card).getByText("Disconnected")).toBeInTheDocument();
    expect(within(card).queryByRole("switch")).not.toBeInTheDocument();
    expect(within(card).queryByRole("button", { name: "Disconnect" })).not.toBeInTheDocument();
    expect(within(card).getByRole("button", { name: "Reconnect" })).toBeInTheDocument();
  });

  it("is read-only for agents", () => {
    const { card } = renderCard({}, { canManage: false });
    expect(within(card).getByRole("switch", { name: /AI analysis/ })).toBeDisabled();
    expect(within(card).queryByRole("button", { name: "Disconnect" })).not.toBeInTheDocument();
  });

  it("marks sandbox accounts", () => {
    const { card } = renderCard({ sandbox: true });
    expect(within(card).getByText("Sandbox")).toBeInTheDocument();
  });

  it("names the API it uses and when it last synced, when it has (C-066)", () => {
    const threeHoursAgo = new Date(Date.now() - 3 * 3_600_000 - 60_000).toISOString();
    const { card } = renderCard({ last_synced_at: threeHoursAgo });
    expect(within(card).getByText("Instagram API")).toBeInTheDocument();
    expect(within(card).getByText("Last synced 3h ago")).toBeInTheDocument();
    expect(within(card).getByRole("img", { name: "Instagram" })).toBeInTheDocument();
  });

  it("says nothing about syncing before the first sync; WhatsApp is the Cloud API", () => {
    const { card } = renderCard({ platform: "whatsapp", last_synced_at: null });
    expect(within(card).getByText("WhatsApp Cloud API")).toBeInTheDocument();
    expect(within(card).queryByText(/Last synced/)).toBeNull();
    // No spam switch: WhatsApp has no comments.
    expect(within(card).queryByRole("switch", { name: /Hide spam comments/ })).toBeNull();
  });

  it("a disconnected card keeps only Reconnect", () => {
    const { card } = renderCard({ status: "disconnected" });
    expect(within(card).getAllByRole("button").map((b) => b.textContent)).toEqual(["Reconnect"]);
  });

  it("asks before disconnecting and passes the delete-data choice (FR-CON-06)", async () => {
    const { card, handlers } = renderCard();
    await userEvent.click(within(card).getByRole("button", { name: "Disconnect" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByText("Disconnect @maple.bakery?")).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("checkbox"));
    await userEvent.click(within(dialog).getByRole("button", { name: "Disconnect and delete" }));
    expect(handlers.onDisconnect).toHaveBeenCalledWith(true);
  });

  it("keeps data by default", async () => {
    const { card, handlers } = renderCard();
    await userEvent.click(within(card).getByRole("button", { name: "Disconnect" }));
    const dialog = await screen.findByRole("alertdialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Disconnect" }));
    expect(handlers.onDisconnect).toHaveBeenCalledWith(false);
  });
});
