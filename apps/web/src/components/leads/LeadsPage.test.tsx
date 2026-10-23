import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it, vi } from "vitest";

import type { ContactListItem, LeadStage, LeadSummary } from "@/lib/api/types";
import { json, renderWithApi, workspace, type Call } from "@/test/api";

import { LeadsPage } from "./LeadsPage";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useParams: () => ({ slug: "maple" }),
  usePathname: () => "/w/maple/leads",
  useSearchParams: () => new URLSearchParams(""),
}));

beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});

function lead(stage: LeadStage, values: Partial<ContactListItem> = {}): ContactListItem {
  return {
    id: `p-${stage}`,
    social_account_id: "a1",
    platform: "instagram",
    name: `Lead ${stage}`,
    username: null,
    profile_picture_url: null,
    email: null,
    phone: null,
    tags: [],
    lead_score: 72,
    lead_stage: stage,
    lead_stage_at: "2026-10-22T10:00:00Z",
    lead_stage_reason: null,
    lead_cold: false,
    conversation_id: `c-${stage}`,
    last_activity_at: new Date(Date.now() - 2 * 3_600_000).toISOString(),
    first_seen_at: "2026-09-27T09:00:00Z",
    ...values,
  };
}

const summary: LeadSummary = {
  stages: [
    { stage: "new", count: 4 },
    { stage: "qualified", count: 2 },
    { stage: "follow_up", count: 1 },
    { stage: "won", count: 3 },
    { stage: "lost", count: 0 },
  ],
  cold: 0,
  weeks: [],
  cold_after_days: 7,
};

type Options = {
  byStage?: Partial<Record<LeadStage, ContactListItem[]>>;
  summary?: Partial<LeadSummary>;
  role?: "owner" | "agent";
};

function setup(options: Options = {}) {
  const byStage: Partial<Record<LeadStage, ContactListItem[]>> = options.byStage ?? {
    new: [lead("new")],
    qualified: [lead("qualified", { lead_stage_reason: "Lead score reached 72." }), lead("qualified", { id: "p-q2", name: "Second qualified" })],
    follow_up: [lead("follow_up", { lead_cold: true })],
    won: [lead("won")],
  };
  return renderWithApi(<LeadsPage />, {
    ws: { ...workspace, role: options.role ?? "owner" },
    handlers: {
      "GET /v1/w/:wid/contacts": (call: Call) => {
        const stage = call.url.searchParams.get("stage") as LeadStage;
        return json({ items: byStage[stage] ?? [], next_cursor: null });
      },
      "GET /v1/w/:wid/leads/summary": () => json({ ...summary, ...options.summary }),
      "GET /v1/w/:wid/leads/settings": () => json({ cold_after_days: 7 }),
      "PATCH /v1/w/:wid/leads/settings": (call: Call) =>
        json({ cold_after_days: (call.body as { cold_after_days: number }).cold_after_days }),
      "POST /v1/w/:wid/contacts/:id/lead-stage": (call: Call) =>
        json({ id: "p-new", lead_stage: (call.body as { stage: string }).stage }),
      "GET /v1/w/:wid/tags": () => json({ items: [] }),
      "GET /v1/w/:wid/contact-fields": () => json({ items: [], limit: 5 }),
    },
  });
}

const listCalls = (calls: Call[]) => calls.filter((c) => c.method === "GET" && c.path === "/v1/w/w1/contacts");

describe("LeadsPage (GR-18)", () => {
  it("has a column per stage, each the contacts in that stage", async () => {
    const { calls } = setup();
    const qualified = await screen.findByRole("region", { name: "Qualified leads" });
    const cards = await within(qualified).findAllByTestId("lead-card");
    expect(cards.map((c) => within(c).getByRole("button", { name: /^Open / }).textContent)).toEqual(["Lead qualified", "Second qualified"]);
    expect(within(qualified).getByText("Lead score reached 72.")).toBeInTheDocument();
    for (const name of ["New", "Follow up", "Won", "Lost"]) {
      expect(screen.getByRole("region", { name: `${name} leads` })).toBeInTheDocument();
    }
    await waitFor(() => {
      const stages = listCalls(calls).map((c) => c.url.searchParams.getAll("stage").join(","));
      expect(stages.sort()).toEqual(["follow_up", "lost", "new", "qualified", "won"]);
    });
    expect(await within(screen.getByRole("region", { name: "Lost leads" })).findByText("No leads here")).toBeInTheDocument();
  });

  it("shows the count of each stage, and how many have gone cold", async () => {
    setup({ summary: { cold: 2 } });
    const won = await screen.findByRole("region", { name: "Won leads" });
    await waitFor(() => expect(within(won).getByRole("heading", { name: /Won/ })).toHaveTextContent("3"));
    expect(await screen.findByTestId("cold-note")).toHaveTextContent("2 leads have gone cold: no reply for 7 days or more.");
  });

  it("marks a lead that has gone cold, and links to its conversation", async () => {
    setup();
    const followUp = await screen.findByRole("region", { name: "Follow up leads" });
    const card = await within(followUp).findByTestId("lead-card");
    expect(within(card).getByTestId("cold-chip")).toHaveTextContent("Gone cold");
    expect(within(card).getByRole("link", { name: "Open the conversation with Lead follow_up" })).toHaveAttribute(
      "href",
      "/w/maple/inbox/c-follow_up",
    );
  });

  it("moves a lead from its card", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    const column = await screen.findByRole("region", { name: "New leads" });
    const card = await within(column).findByTestId("lead-card");
    await user.click(within(card).getByRole("combobox", { name: "Stage for Lead new" }));
    await user.click(await screen.findByRole("option", { name: "Qualified" }));
    await waitFor(() => {
      const post = calls.find((c) => c.method === "POST" && c.path.endsWith("/lead-stage"));
      expect(post?.path).toBe("/v1/w/w1/contacts/p-new/lead-stage");
      expect(post?.body).toEqual({ stage: "qualified" });
    });
  });

  it("uses the contacts filters: search reaches every column, and the stage filter is left out", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    await screen.findByRole("region", { name: "Qualified leads" });
    await user.type(screen.getByRole("searchbox", { name: "Search leads" }), "priya");
    await waitFor(() => {
      const latest = listCalls(calls).slice(-5);
      expect(latest.map((c) => c.url.searchParams.get("q"))).toEqual(Array(5).fill("priya"));
    });
    await user.click(screen.getByRole("button", { name: "Filters" }));
    expect(screen.queryByRole("checkbox", { name: "Stage Won" })).not.toBeInTheDocument();
  });

  it("shows one stage at a time below the wide layout, chosen with the stage buttons", async () => {
    const user = userEvent.setup();
    setup();
    await screen.findByRole("region", { name: "Qualified leads" });
    const buttons = screen.getByRole("group", { name: "Show a stage" });
    expect(within(buttons).getByRole("button", { name: /New/ })).toHaveAttribute("aria-pressed", "true");
    await user.click(within(buttons).getByRole("button", { name: /Won/ }));
    expect(within(buttons).getByRole("button", { name: /Won/ })).toHaveAttribute("aria-pressed", "true");
    expect(within(buttons).getByRole("button", { name: /New/ })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("region", { name: "Won leads" })).toHaveClass("block");
    expect(screen.getByRole("region", { name: "New leads" })).toHaveClass("hidden");
  });

  it("lets an admin choose when a lead goes cold, and not an agent", async () => {
    const user = userEvent.setup();
    const { calls, unmount } = setup();
    await user.click(await screen.findByRole("combobox", { name: "Gone cold after" }));
    await user.click(await screen.findByRole("option", { name: "Gone cold after 14 days" }));
    await waitFor(() => expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({ cold_after_days: 14 }));
    unmount();

    setup({ role: "agent" });
    await screen.findByRole("region", { name: "Qualified leads" });
    expect(screen.queryByRole("combobox", { name: "Gone cold after" })).not.toBeInTheDocument();
  });
});
