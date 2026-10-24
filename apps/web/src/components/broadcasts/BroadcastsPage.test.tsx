import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Broadcast, BroadcastAvailability } from "@/lib/api/types";
import { json, renderWithApi } from "@/test/api";

import { BroadcastsPage } from "./BroadcastsPage";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useParams: () => ({ slug: "maple" }),
  usePathname: () => "/w/maple/broadcasts",
  useSearchParams: () => new URLSearchParams(""),
}));

const availability: BroadcastAvailability = {
  enabled: true,
  plan_allowed: true,
  monthly_limit: 2500,
  used_this_period: 120,
  period_end: "2026-11-24T00:00:00Z",
  rate_card: null,
};

function broadcast(values: Partial<Broadcast> = {}): Broadcast {
  return {
    id: "b1",
    name: "Diwali sale",
    status: "completed",
    social_account_id: "wa1",
    account_label: "Maple Orders",
    segment_id: "s1",
    segment_name: "Everyone",
    template: { name: "sale_offer", language: "en", category: "marketing", body: "Hi {{1}}" },
    variables: [],
    scheduled_at: null,
    started_at: "2026-10-24T10:00:00Z",
    completed_at: "2026-10-24T10:05:00Z",
    paused_code: null,
    paused_reason: null,
    audience_size: 3,
    cost: null,
    counts: { total: 4, queued: 0, sent: 0, delivered: 1, read: 1, failed: 1, skipped: 1, replied: 1, stopped: 0 },
    created_at: "2026-10-24T09:00:00Z",
    ...values,
  };
}

function setup(a: Partial<BroadcastAvailability>, items: Broadcast[] = []) {
  return renderWithApi(<BroadcastsPage />, {
    handlers: {
      "GET /v1/w/:wid/broadcasts/availability": () => json({ ...availability, ...a }),
      "GET /v1/w/:wid/broadcasts": () => json({ items, total: items.length }),
    },
  });
}

describe("the broadcasts list (GR-23)", () => {
  it("shows nothing but a plain notice while the server setting is off", async () => {
    setup({ enabled: false });
    expect(await screen.findByText("Broadcasts aren't available yet")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /New/ })).not.toBeInTheDocument();
  });

  it("shows the same notice when the availability call fails", async () => {
    renderWithApi(<BroadcastsPage />, { handlers: {} });
    expect(await screen.findByText("Broadcasts aren't available yet")).toBeInTheDocument();
  });

  it("lists broadcasts with their counts, the paused reason and the month's quota", async () => {
    setup({}, [
      broadcast(),
      broadcast({
        id: "b2",
        name: "Winter sale",
        status: "paused",
        paused_reason: "WhatsApp rated this number's quality Low. Sending is paused to protect the number.",
      }),
    ]);
    const rows = await screen.findAllByTestId("broadcast-row");
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByRole("link", { name: "Diwali sale" })).toHaveAttribute("href", "/w/maple/broadcasts/b1");
    expect(within(rows[0]).getByText("Done")).toBeInTheDocument();
    expect(rows[0]).toHaveTextContent("3 people · 2 sent · 2 delivered · 1 read · 1 failed · 1 replied");
    expect(within(rows[1]).getByText("Paused")).toBeInTheDocument();
    expect(rows[1]).toHaveTextContent("Sending is paused to protect the number.");
    expect(screen.getByRole("meter")).toHaveAttribute("aria-valuetext", "120 of 2,500 people");
    expect(screen.getByText(/Meta charges your WhatsApp Business Account directly/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /New/ })).toHaveAttribute("href", "/w/maple/broadcasts/new");
  });

  it("says broadcasts are part of Pro on a plan without them, and offers no new broadcast", async () => {
    setup({ plan_allowed: false, monthly_limit: 0 });
    expect(await screen.findByText("Broadcasts are part of Pro")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /New/ })).not.toBeInTheDocument();
  });

  it("explains an empty list", async () => {
    setup({});
    expect(await screen.findByText("No broadcasts yet")).toBeInTheDocument();
  });
});
