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
    items_synced: 0,
    items_pending: 0,
    items_error: 0,
    problems: [],
    ...values,
  };
}

const FEED = "https://api.example/v1/feeds/whatsapp-catalogue/tok-1.csv";
const CONNECTED = status({
  connected: true,
  catalog_id: "123456789",
  account_label: "Maple WhatsApp",
  feed_url: FEED,
  feed_fetched_at: null,
  items_pending: 4,
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
      "POST /v1/w/:wid/integrations/whatsapp-catalogue/feed-link": () => {
        current = { ...current, feed_url: "https://api.example/v1/feeds/whatsapp-catalogue/tok-2.csv" };
        return json(current);
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

describe("WhatsApp catalogue card (GR-33, C-215)", () => {
  it("tells Free that product messages are part of Creator and Business", async () => {
    setup(status({ entitled: false }));
    expect(await screen.findByText(/WhatsApp product messages are part of Creator and Business/)).toBeInTheDocument();
  });

  it("connects a catalogue by its id, then shows the feed link and how to add it", async () => {
    const user = userEvent.setup();
    let sent: unknown;
    setup(status(), {
      "PUT /v1/w/:wid/integrations/whatsapp-catalogue": (call) => {
        sent = call.body;
        return json(CONNECTED);
      },
    });
    expect(await screen.findByText(/business portfolio that owns your WhatsApp number/)).toBeInTheDocument();
    await user.type(await screen.findByLabelText("Catalogue id"), "123456789");
    await user.click(screen.getByRole("button", { name: "Connect catalogue" }));
    await waitFor(() => expect(toast.success).toHaveBeenCalled());
    expect(sent).toEqual({ social_account_id: "wa1", catalog_id: "123456789" });
    expect(await screen.findByText(/Connected to catalogue 123456789 through Maple WhatsApp/)).toBeInTheDocument();
    expect(screen.getByText(/Meta hasn't fetched your products yet/)).toBeInTheDocument();
    expect(screen.getByLabelText("Feed link")).toHaveValue(FEED);
    expect(screen.getByText(/Upload via URL or Google Sheets/)).toBeInTheDocument();
    expect(screen.getByText("Waiting for Meta's next fetch").nextSibling).toHaveTextContent("4");
    expect(screen.queryByRole("button", { name: /Sync/ })).not.toBeInTheDocument();
  });

  it("shows the reason when the id is refused", async () => {
    const user = userEvent.setup();
    setup(status(), {
      "PUT /v1/w/:wid/integrations/whatsapp-catalogue": () =>
        problem(422, "validation_error", "The catalogue id is the number in Commerce Manager."),
    });
    await user.type(await screen.findByLabelText("Catalogue id"), "nope");
    await user.click(screen.getByRole("button", { name: "Connect catalogue" }));
    expect(await screen.findByText(/The catalogue id is the number in Commerce Manager/)).toBeInTheDocument();
  });

  it("copies the feed link", async () => {
    const user = userEvent.setup();
    const writeText = vi.spyOn(navigator.clipboard, "writeText");
    setup(CONNECTED);
    await user.click(await screen.findByRole("button", { name: "Copy" }));
    expect(writeText).toHaveBeenCalledWith(FEED);
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Feed link copied"));
  });

  it("makes a new link after a warning that the old one stops working", async () => {
    const user = userEvent.setup();
    setup(CONNECTED);
    await user.click(await screen.findByRole("button", { name: "New link" }));
    expect(await screen.findByText(/The old link stops working at once/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Make new link" }));
    await waitFor(() =>
      expect(screen.getByLabelText("Feed link")).toHaveValue("https://api.example/v1/feeds/whatsapp-catalogue/tok-2.csv"),
    );
  });

  it("says when Meta last fetched, with the counts and the products that can't be in the catalogue", async () => {
    setup({
      ...CONNECTED,
      feed_fetched_at: new Date(Date.now() - 5 * 60_000).toISOString(),
      items_synced: 3,
      items_pending: 0,
      items_error: 1,
      problems: [{ name: "Silk scarf", message: "Add a picture to this product." }],
    });
    expect(await screen.findByText(/Meta last fetched your products 5m ago/)).toBeInTheDocument();
    expect(screen.getByText("In the catalogue").nextSibling).toHaveTextContent("3");
    expect(screen.getByText(/1 product can.t be in the catalogue/)).toBeInTheDocument();
    expect(screen.getByText(/Silk scarf: Add a picture to this product/)).toBeInTheDocument();
  });

  it("shows the last error as a warning", async () => {
    setup({ ...CONNECTED, last_error: "Your plan no longer includes the catalogue." });
    expect(await screen.findByText("Your plan no longer includes the catalogue.")).toBeInTheDocument();
    expect(screen.getByText("Needs attention")).toBeInTheDocument();
  });

  it("shows members the summary and counts, without the link or the buttons", async () => {
    setup({ ...CONNECTED, feed_url: null });
    expect(await screen.findByText(/Connected to catalogue 123456789/)).toBeInTheDocument();
    expect(screen.getByText("In the catalogue")).toBeInTheDocument();
    expect(screen.queryByLabelText("Feed link")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "New link" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Disconnect/ })).not.toBeInTheDocument();
  });
});
