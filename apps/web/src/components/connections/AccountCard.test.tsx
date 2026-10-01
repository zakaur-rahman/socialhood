import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/errors";
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
  deleting: false,
  last_synced_at: null,
};

const idle = { saving: false, reconnecting: false, retrying: false, disconnecting: false, deleting: false };

function actions(): AccountActions {
  return {
    onChange: vi.fn(),
    onReconnect: vi.fn(),
    onRetrySubscribe: vi.fn(),
    onDisconnect: vi.fn(),
    onDelete: vi.fn().mockResolvedValue(undefined),
  };
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

  it("a disconnected card offers Reconnect and Remove (C-067)", () => {
    const { card } = renderCard({ status: "disconnected" });
    expect(within(card).getAllByRole("button").map((b) => b.textContent)).toEqual(["Reconnect", "Remove"]);
  });

  it("a connected card offers Disconnect and Disconnect and delete data; a sandbox, Remove", () => {
    const { card } = renderCard();
    expect(within(card).getAllByRole("button").map((b) => b.textContent)).toEqual([
      "Disconnect",
      "Disconnect and delete data",
    ]);
  });

  it("a connected sandbox can be removed straight away", () => {
    const { card } = renderCard({ sandbox: true });
    expect(within(card).getAllByRole("button").map((b) => b.textContent)).toEqual(["Disconnect", "Remove"]);
  });

  it("asks before disconnecting, and keeps the data (FR-CON-06)", async () => {
    const { card, handlers } = renderCard();
    await userEvent.click(within(card).getByRole("button", { name: "Disconnect" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByText("Disconnect @maple.bakery?")).toBeInTheDocument();
    expect(within(dialog).getByText(/stay here for reference/)).toBeInTheDocument();
    expect(within(dialog).queryByRole("checkbox")).toBeNull();
    await userEvent.click(within(dialog).getByRole("button", { name: "Disconnect" }));
    expect(handlers.onDisconnect).toHaveBeenCalledOnce();
    expect(handlers.onDelete).not.toHaveBeenCalled();
  });
});

describe("deleting an account's data (C-067)", () => {
  async function open(card: HTMLElement, trigger: string) {
    const user = userEvent.setup();
    await user.click(within(card).getByRole("button", { name: trigger }));
    const dialog = await screen.findByRole("alertdialog");
    return { user, dialog, input: within(dialog).getByLabelText(/to confirm/) };
  }

  it("Disconnect and delete data says what goes and what stays, and needs the handle typed", async () => {
    const { card, handlers } = renderCard();
    const { user, dialog, input } = await open(card, "Disconnect and delete data");
    expect(within(dialog).getByText("Disconnect @maple.bakery and delete its data?")).toBeInTheDocument();
    const deleted = within(dialog).getByRole("region", { name: "Deleted" });
    expect(within(deleted).getByText("Its conversations, messages and contacts")).toBeInTheDocument();
    const kept = within(dialog).getByRole("region", { name: "Kept" });
    expect(within(kept).getByText("Your knowledge base and AI settings")).toBeInTheDocument();
    expect(within(kept).getByText("Workspace settings, members and billing")).toBeInTheDocument();

    const confirm = within(dialog).getByRole("button", { name: "Disconnect and delete" });
    expect(confirm).toBeDisabled();
    await user.type(input, "maple");
    expect(confirm).toBeDisabled();
    await user.clear(input);
    await user.type(input, "MAPLE.bakery");
    expect(confirm).toBeEnabled();
    await user.click(confirm);
    expect(handlers.onDelete).toHaveBeenCalledWith("MAPLE.bakery", "disconnect");
    await vi.waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
  });

  it("Remove uses the same dialog; a WhatsApp number can be typed with any spacing", async () => {
    const { card, handlers } = renderCard({
      status: "disconnected",
      platform: "whatsapp",
      username: null,
      phone_number: "+91 98765 43210",
    });
    const { user, dialog, input } = await open(card, "Remove");
    expect(within(dialog).getByText("Remove Maple Bakery?")).toBeInTheDocument();
    expect(within(dialog).getByText("+91 98765 43210")).toBeInTheDocument();
    await user.type(input, "919876543210");
    await user.click(within(dialog).getByRole("button", { name: "Remove account" }));
    expect(handlers.onDelete).toHaveBeenCalledWith("919876543210", "remove");
  });

  it("shows the API's refusal of the typed handle under the field and stays open", async () => {
    const { card, handlers } = renderCard();
    vi.mocked(handlers.onDelete).mockRejectedValueOnce(
      new ApiError({
        type: "https://api.socialhood.com/errors/validation_error",
        title: "The request is not valid",
        status: 422,
        code: "validation_error",
        errors: [{ field: "confirm", message: "Type @maple.bakery exactly as shown to confirm." }],
      }),
    );
    const { user, dialog, input } = await open(card, "Disconnect and delete data");
    await user.type(input, "@maple.bakery");
    await user.click(within(dialog).getByRole("button", { name: "Disconnect and delete" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Type @maple.bakery exactly as shown to confirm.");
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
  });

  it("a deleting account says so and offers nothing", () => {
    const { card } = renderCard({ status: "disconnected", deleting: true });
    expect(card).toHaveAttribute("data-status", "deleting");
    expect(within(card).getByText("Deleting…")).toBeInTheDocument();
    expect(within(card).getByRole("status")).toHaveTextContent("It disappears from this list when done.");
    expect(within(card).queryAllByRole("button")).toEqual([]);
    expect(within(card).queryByRole("switch")).toBeNull();
  });
});
