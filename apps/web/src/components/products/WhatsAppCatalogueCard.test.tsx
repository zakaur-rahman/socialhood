import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { WaCatalogueStatus } from "@/lib/api/types";
import { account, json, noContent, problem, renderWithApi, type Call } from "@/test/api";

import { WhatsAppCatalogueCard } from "./WhatsAppCatalogueCard";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

function status(values: Partial<WaCatalogueStatus> = {}): WaCatalogueStatus {
  return {
    entitled: true,
    connected: false,
    syncing: false,
    items_synced: 0,
    items_pending: 0,
    items_error: 0,
    problems: [],
    ...values,
  } as WaCatalogueStatus;
}

const CONNECTED = status({
  connected: true,
  status: "active",
  catalog_id: "cat-1",
  catalog_name: "Maple shop",
  account_label: "Maple WhatsApp",
  items_synced: 4,
  synced_at: new Date(Date.now() - 5 * 60_000).toISOString(),
});

function setup(initial: WaCatalogueStatus, extra: Record<string, (call: Call) => Response> = {}) {
  let current = initial;
  return renderWithApi(<WhatsAppCatalogueCard wid="w1" />, {
    handlers: {
      "GET /v1/w/:wid/integrations/whatsapp-catalogue": () => json(current),
      "GET /v1/w/:wid/social-accounts": () =>
        json({ items: [account({ id: "wa1", platform: "whatsapp", display_name: "Maple WhatsApp" })] }),
      "PUT /v1/w/:wid/integrations/whatsapp-catalogue": () => {
        current = CONNECTED;
        return json(current);
      },
      "POST /v1/w/:wid/integrations/whatsapp-catalogue/sync": () => {
        current = { ...current, syncing: true };
        return json(current, 202);
      },
      "DELETE /v1/w/:wid/integrations/whatsapp-catalogue": () => {
        current = status();
        return noContent();
      },
      ...extra,
    },
  });
}

beforeEach(() => {
  toast.success.mockReset();
  toast.error.mockReset();
});

describe("WhatsApp catalogue card (GR-33)", () => {
  it("tells Free that product messages are part of Pro", async () => {
    setup(status({ entitled: false }));
    expect(await screen.findByText(/WhatsApp product messages are part of Pro/)).toBeInTheDocument();
  });

  it("connects a catalogue by its id", async () => {
    const user = userEvent.setup();
    let sent: unknown;
    setup(status(), {
      "PUT /v1/w/:wid/integrations/whatsapp-catalogue": (call) => {
        sent = call.body;
        return json(CONNECTED);
      },
    });
    await user.type(await screen.findByLabelText("Catalogue id"), "cat-1");
    await user.click(screen.getByRole("button", { name: "Connect catalogue" }));
    await waitFor(() => expect(toast.success).toHaveBeenCalled());
    expect(sent).toEqual({ social_account_id: "wa1", catalog_id: "cat-1" });
    expect(await screen.findByText(/Connected to Maple shop \(cat-1\) through Maple WhatsApp/)).toBeInTheDocument();
    expect(screen.getByText(/4 items in the catalogue/)).toBeInTheDocument();
  });

  it("shows Meta's reason when it won't show the catalogue", async () => {
    const user = userEvent.setup();
    setup(status(), {
      "PUT /v1/w/:wid/integrations/whatsapp-catalogue": () =>
        problem(409, "conflict", "Meta can't find that catalogue. Check the id in Commerce Manager."),
    });
    await user.type(await screen.findByLabelText("Catalogue id"), "nope");
    await user.click(screen.getByRole("button", { name: "Connect catalogue" }));
    expect(await screen.findByText(/Meta can.t find that catalogue/)).toBeInTheDocument();
  });

  it("lists the items Meta refused and offers Sync now", async () => {
    const user = userEvent.setup();
    setup({
      ...CONNECTED,
      items_error: 1,
      problems: [{ name: "Silk scarf", message: "Add a link to this product. Meta needs one for every catalogue item." }],
    });
    expect(await screen.findByText(/1 item can.t be sent/)).toBeInTheDocument();
    expect(screen.getByText(/Silk scarf: Add a link to this product/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Sync now/ }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Sending your products again."));
  });

  it("asks to connect again when Meta no longer lets the number use the catalogue", async () => {
    setup({ ...CONNECTED, status: "needs_reconnect", sync_error: "Meta no longer lets this number use the catalogue." });
    expect(await screen.findByText(/Meta no longer lets this number use the catalogue/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Connect again" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Sync now/ })).not.toBeInTheDocument();
  });
});
