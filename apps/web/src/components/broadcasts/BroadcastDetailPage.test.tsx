import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it, vi } from "vitest";

import type { Broadcast, BroadcastAvailability, BroadcastRecipient } from "@/lib/api/types";
import { json, renderWithApi } from "@/test/api";

import { BroadcastDetailPage } from "./BroadcastDetailPage";

const nav = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: nav.push, replace: vi.fn() }),
  useParams: () => ({ slug: "maple" }),
  usePathname: () => "/w/maple/broadcasts/b1",
  useSearchParams: () => new URLSearchParams(""),
}));

beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});

const availability: BroadcastAvailability = {
  enabled: true,
  plan_allowed: true,
  monthly_limit: 2500,
  used_this_period: 3,
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
    template: {
      name: "sale_offer",
      language: "en",
      category: "marketing",
      body: "Hi {{1}}, our sale is on until {{2}}. Reply STOP to opt out.",
    },
    variables: [
      { source: "field", field: "first_name", fallback: "there" },
      { source: "fixed", value: "31 October" },
    ],
    scheduled_at: null,
    started_at: "2026-10-24T10:00:00Z",
    completed_at: "2026-10-24T10:05:00Z",
    paused_code: null,
    paused_reason: null,
    audience_size: 3,
    cost: {
      currency: "INR",
      category: "marketing",
      per_message: "0.7846",
      total: "2.35",
      as_of: "2026-10-24",
      source: "typed in by hand",
      verified: false,
    },
    counts: { total: 4, queued: 0, sent: 0, delivered: 1, read: 1, failed: 1, skipped: 1, replied: 1, stopped: 1 },
    created_at: "2026-10-24T09:00:00Z",
    ...values,
  };
}

function person(values: Partial<BroadcastRecipient> = {}): BroadcastRecipient {
  return {
    id: "r1",
    contact_id: "c1",
    contact_name: "Asha Rao",
    username: null,
    status: "delivered",
    reason: null,
    replied: false,
    stopped: false,
    dispatched_at: "2026-10-24T10:01:00Z",
    conversation_id: "cv1",
    ...values,
  };
}

const people: BroadcastRecipient[] = [
  person(),
  person({ id: "r2", contact_id: "c2", contact_name: "Ben Cole", status: "read", replied: true, stopped: true, conversation_id: "cv2" }),
  person({ id: "r3", contact_id: "c3", contact_name: "Chitra Iyer", status: "failed", reason: "This person can't receive messages right now." }),
  person({ id: "r4", contact_id: "c4", contact_name: "Dev Nair", status: "skipped", reason: "Asked not to get marketing messages.", conversation_id: null }),
];

function setup(b: Broadcast, extra: Record<string, () => Response> = {}) {
  return renderWithApi(<BroadcastDetailPage id="b1" />, {
    handlers: {
      "GET /v1/w/:wid/broadcasts/availability": () => json(availability),
      "GET /v1/w/:wid/broadcasts/:id": () => json(b),
      "GET /v1/w/:wid/broadcasts/:id/recipients": () => json({ items: people, total: people.length }),
      ...extra,
    },
  });
}

describe("the broadcast page (GR-23)", () => {
  it("shows a finished broadcast's counts at each stage", async () => {
    setup(broadcast());
    expect(await screen.findByRole("heading", { name: "Diwali sale" })).toBeInTheDocument();
    expect(screen.getByText("Done")).toBeInTheDocument();
    const counts = screen.getByTestId("counts");
    const stat = (label: string) => within(counts).getByText(label).closest("div") as HTMLElement;
    expect(stat("Sent")).toHaveTextContent("2");
    expect(stat("Sent")).toHaveTextContent("67%");
    expect(stat("Delivered")).toHaveTextContent("2");
    expect(stat("Read")).toHaveTextContent("1");
    expect(stat("Replied")).toHaveTextContent("1 said STOP");
    expect(stat("Failed")).toHaveTextContent("1");
    expect(stat("Skipped")).toHaveTextContent("1");
    expect(screen.getByText(/About/)).toHaveTextContent("₹2.35");
    expect(screen.getByText(/typed in by hand, not yet checked against Meta/)).toBeInTheDocument();
  });

  it("lists each person with their status, the reason it failed or was skipped, and links to the chat", async () => {
    setup(broadcast());
    const rows = await screen.findAllByTestId("recipient-row");
    expect(rows).toHaveLength(4);
    expect(within(rows[0]).getByRole("link", { name: "Asha Rao" })).toHaveAttribute("href", "/w/maple/inbox/cv1");
    expect(within(rows[0]).getByText("Delivered")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Read")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Said STOP")).toBeInTheDocument();
    expect(within(rows[2]).getByText("Failed")).toBeInTheDocument();
    expect(within(rows[2]).getByText("This person can't receive messages right now.")).toBeInTheDocument();
    expect(within(rows[3]).getByText("Skipped")).toBeInTheDocument();
    expect(within(rows[3]).getByText("Asked not to get marketing messages.")).toBeInTheDocument();
    expect(within(rows[3]).queryByRole("link")).not.toBeInTheDocument();
  });

  it("asks for one status when a filter is chosen", async () => {
    const user = userEvent.setup();
    const { calls } = setup(broadcast());
    await screen.findAllByTestId("recipient-row");
    await user.click(screen.getByRole("radio", { name: "Failed" }));
    await waitFor(() =>
      expect(calls.some((c) => c.path.endsWith("/recipients") && c.url.searchParams.get("status") === "failed")).toBe(true),
    );
    expect(calls.find((c) => c.path.endsWith("/recipients"))?.url.searchParams.get("limit")).toBe("25");
  });

  it("says why a broadcast paused and resumes it", async () => {
    const user = userEvent.setup();
    const reason = "WhatsApp rated this number's quality Low. Sending is paused to protect the number. Resume it once the rating recovers.";
    const { calls } = setup(broadcast({ status: "paused", paused_code: "quality", paused_reason: reason, completed_at: null }), {
      "POST /v1/w/:wid/broadcasts/:id/resume": () => json(broadcast({ status: "sending", completed_at: null })),
    });
    expect(await screen.findByTestId("paused-reason")).toHaveTextContent(reason);
    expect(screen.getByText("Paused")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Resume" }));
    await waitFor(() => expect(calls.some((c) => c.path.endsWith("/resume"))).toBe(true));
  });

  it("pauses a sending broadcast, and asks before cancelling", async () => {
    const user = userEvent.setup();
    const { calls } = setup(broadcast({ status: "sending", completed_at: null }), {
      "POST /v1/w/:wid/broadcasts/:id/pause": () => json(broadcast({ status: "paused", completed_at: null })),
      "POST /v1/w/:wid/broadcasts/:id/cancel": () => json(broadcast({ status: "cancelled" })),
    });
    await user.click(await screen.findByRole("button", { name: "Pause" }));
    await waitFor(() => expect(calls.some((c) => c.path.endsWith("/pause"))).toBe(true));

    await user.click(screen.getByRole("button", { name: "Cancel" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(dialog).toHaveTextContent("Everyone who hasn't been sent to yet is skipped");
    expect(calls.some((c) => c.path.endsWith("/cancel"))).toBe(false);
    await user.click(within(dialog).getByRole("button", { name: "Cancel broadcast" }));
    await waitFor(() => expect(calls.some((c) => c.path.endsWith("/cancel"))).toBe(true));
  });

  it("sends a draft after a confirmation and deletes one after another", async () => {
    const user = userEvent.setup();
    nav.push.mockClear();
    const { calls } = setup(broadcast({ status: "draft", counts: { ...broadcast().counts, total: 0, delivered: 0, read: 0, failed: 0, skipped: 0, replied: 0, stopped: 0 }, started_at: null, completed_at: null, audience_size: 0, cost: null }), {
      "POST /v1/w/:wid/broadcasts/:id/start": () => json(broadcast({ status: "sending" })),
      "DELETE /v1/w/:wid/broadcasts/:id": () => new Response(null, { status: 204 }),
    });
    expect(await screen.findByText("Draft")).toBeInTheDocument();
    expect(screen.queryByTestId("counts")).not.toBeInTheDocument(); // nothing has been sent
    expect(screen.getByText("The people and the cost are worked out when it starts.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Send now" }));
    await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Send" }));
    await waitFor(() => expect(calls.some((c) => c.path.endsWith("/start"))).toBe(true));
    expect(calls.find((c) => c.path.endsWith("/start"))?.body).toEqual({ scheduled_at: null });

    await user.click(screen.getByRole("button", { name: "Delete" }));
    await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/w/maple/broadcasts"));
  });

  it("shows nothing but a notice while broadcasts are switched off", async () => {
    renderWithApi(<BroadcastDetailPage id="b1" />, {
      handlers: { "GET /v1/w/:wid/broadcasts/availability": () => json({ enabled: false }) },
    });
    expect(await screen.findByText("Broadcasts aren't available yet")).toBeInTheDocument();
    expect(screen.queryByTestId("counts")).not.toBeInTheDocument();
  });
});
