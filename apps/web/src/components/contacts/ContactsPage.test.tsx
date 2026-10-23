import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it, vi } from "vitest";

import type { ContactListItem, ContactSegment, ContactTag } from "@/lib/api/types";
import { json, problem, renderWithApi, workspace, type Call } from "@/test/api";

import { ContactsPage } from "./ContactsPage";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useParams: () => ({ slug: "maple" }),
  usePathname: () => "/w/maple/contacts",
  useSearchParams: () => new URLSearchParams(""),
}));

beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});

const leadMagnet: ContactTag = { id: "t1", name: "lead-magnet", color: 1, contact_count: 2 };
const vip: ContactTag = { id: "t2", name: "vip", color: 0, contact_count: 1 };

function contact(values: Partial<ContactListItem> = {}): ContactListItem {
  return {
    id: "p1",
    social_account_id: "a1",
    platform: "instagram",
    name: "Priya Nair",
    username: "priya.styles",
    profile_picture_url: null,
    email: "priya@example.com",
    phone: null,
    tags: [{ id: "t1", name: "lead-magnet", color: 1 }],
    lead_score: 72,
    lead_stage: "qualified",
    lead_stage_at: "2026-10-22T10:00:00Z",
    lead_stage_reason: "Lead score reached 72.",
    lead_cold: false,
    conversation_id: "c1",
    last_activity_at: new Date(Date.now() - 2 * 3_600_000).toISOString(),
    first_seen_at: "2026-09-27T09:00:00Z",
    ...values,
  };
}

const segment: ContactSegment = {
  id: "s1",
  name: "Warm leads",
  filter: { tag_ids: ["t1"], has_email: true },
  created_at: "2026-10-20T10:00:00Z",
};

type Options = {
  items?: ContactListItem[];
  total?: number;
  segments?: ContactSegment[];
  role?: "owner" | "agent";
  next?: string | null;
  tooBig?: boolean;
};

function setup(options: Options = {}) {
  const items = options.items ?? [contact(), contact({ id: "p2", name: "Rahul Kumar", username: "rahul.k", email: null, tags: [], lead_score: null })];
  return renderWithApi(<ContactsPage />, {
    ws: { ...workspace, role: options.role ?? "owner" },
    handlers: {
      "GET /v1/w/:wid/contacts": () => json({ items, next_cursor: options.next ?? null }),
      "GET /v1/w/:wid/contacts/count": () => json({ count: options.total ?? items.length }),
      "GET /v1/w/:wid/tags": () => json({ items: [leadMagnet, vip] }),
      "GET /v1/w/:wid/contact-fields": () =>
        json({ items: [{ id: "f1", key: "city", label: "City", type: "text", options: [], position: 0 }], limit: 5 }),
      "GET /v1/w/:wid/contact-segments": () => json({ items: options.segments ?? [] }),
      "POST /v1/w/:wid/contact-segments": (call: Call) =>
        json({ id: "s9", created_at: "2026-10-24T10:00:00Z", ...(call.body as object) }, 201),
      "POST /v1/w/:wid/contacts/bulk-tags": () =>
        options.tooBig
          ? new Response(
              JSON.stringify({
                type: "about:blank",
                title: "validation_error",
                status: 422,
                code: "validation_error",
                errors: [{ field: "filter", message: "That filter matches 7,200 contacts. Narrow it to 5,000 or fewer to tag them at once." }],
              }),
              { status: 422, headers: { "Content-Type": "application/problem+json" } },
            )
          : json({ updated: 2 }),
      "GET /v1/w/:wid/contacts/export.csv": () =>
        new Response("Name,Email\r\nPriya Nair,priya@example.com\r\n", { headers: { "Content-Type": "text/csv" } }),
      "GET /v1/w/:wid/contacts/:id": () => problem(404, "not_found"),
    },
  });
}

const listCalls = (calls: Call[]) => calls.filter((c) => c.method === "GET" && c.path === "/v1/w/w1/contacts");
const bulkCall = (calls: Call[]) => calls.find((c) => c.method === "POST" && c.path.endsWith("/contacts/bulk-tags"));

async function chooseTag(user: ReturnType<typeof userEvent.setup>, name: string) {
  await user.click(screen.getByRole("button", { name: "Tag" }));
  await user.click(await screen.findByRole("combobox", { name: "Tag" }));
  await user.click(await screen.findByRole("option", { name }));
}

describe("ContactsPage (GR-17)", () => {
  it("lists contacts with their tags, email and lead score, and counts them", async () => {
    setup();
    const rows = await screen.findAllByTestId("contact-row");
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByText("Priya Nair")).toBeInTheDocument();
    expect(within(rows[0]).getByText("@priya.styles")).toBeInTheDocument();
    expect(within(rows[0]).getByText("lead-magnet")).toBeInTheDocument();
    expect(within(rows[0]).getByText("priya@example.com")).toBeInTheDocument();
    expect(within(rows[1]).getByText("No email or phone")).toBeInTheDocument();
    expect(await screen.findByTestId("contact-count")).toHaveTextContent("2 contacts");
  });

  it("shows each contact's lead stage", async () => {
    setup({ items: [contact(), contact({ id: "p2", name: "Rahul Kumar", lead_stage: "won" })] });
    const rows = await screen.findAllByTestId("contact-row");
    expect(within(rows[0]).getByTestId("contact-stage")).toHaveTextContent("Qualified");
    expect(within(rows[1]).getByTestId("contact-stage")).toHaveTextContent("Won");
  });

  it("filters by lead stage on the server, for the list and the count", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    await screen.findAllByTestId("contact-row");
    await user.click(screen.getByRole("button", { name: "Filters" }));
    await user.click(await screen.findByRole("checkbox", { name: "Stage Qualified" }));
    await user.click(screen.getByRole("checkbox", { name: "Stage Follow up" }));
    await waitFor(() => expect(listCalls(calls).at(-1)?.url.searchParams.getAll("stage")).toEqual(["qualified", "follow_up"]));
    const count = calls.filter((c) => c.path === "/v1/w/w1/contacts/count").at(-1);
    expect(count?.url.searchParams.getAll("stage")).toEqual(["qualified", "follow_up"]);
  });

  it("explains an empty list", async () => {
    setup({ items: [] });
    expect(await screen.findByText("No contacts yet")).toBeInTheDocument();
  });

  it("filters on the server by tag and has email, for the list and the count", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    await screen.findAllByTestId("contact-row");
    await user.click(screen.getByRole("button", { name: "Filters" }));
    await user.click(await screen.findByRole("checkbox", { name: "Tag lead-magnet" }));
    await user.click(screen.getByRole("combobox", { name: "Email" }));
    await user.click(await screen.findByRole("option", { name: "Has an email" }));
    await waitFor(() => {
      const last = listCalls(calls).at(-1);
      expect(last?.url.searchParams.getAll("tag_id")).toEqual(["t1"]);
      expect(last?.url.searchParams.get("has_email")).toBe("true");
    });
    const count = calls.filter((c) => c.path === "/v1/w/w1/contacts/count").at(-1);
    expect(count?.url.searchParams.getAll("tag_id")).toEqual(["t1"]);
    expect(count?.url.searchParams.get("has_email")).toBe("true");
  });

  it("searches after a pause", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    await screen.findAllByTestId("contact-row");
    await user.type(screen.getByRole("searchbox", { name: "Search contacts" }), "priya");
    await waitFor(() => expect(listCalls(calls).at(-1)?.url.searchParams.get("q")).toBe("priya"));
  });

  it("tags the ticked contacts in bulk", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    await screen.findAllByTestId("contact-row");
    await user.click(screen.getByRole("checkbox", { name: "Select Priya Nair" }));
    expect(screen.getByTestId("selection")).toHaveTextContent("1 selected");
    await chooseTag(user, "vip");
    await user.click(screen.getByRole("button", { name: "Add tag" }));
    await waitFor(() => expect(bulkCall(calls)?.body).toEqual({ contact_ids: ["p1"], add: ["t2"], remove: [] }));
  });

  it("tags everyone the filter matches when all of them are chosen", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ total: 120, next: "cursor-2" });
    await screen.findAllByTestId("contact-row");
    await user.type(screen.getByRole("searchbox", { name: "Search contacts" }), "a");
    await waitFor(() => expect(listCalls(calls).at(-1)?.url.searchParams.get("q")).toBe("a"));
    await user.click(screen.getByRole("checkbox", { name: "Select all on this page" }));
    await user.click(await screen.findByRole("button", { name: "Select all 120 that match" }));
    expect(screen.getByTestId("selection")).toHaveTextContent("All 120 selected");
    await chooseTag(user, "lead-magnet");
    await user.click(screen.getByRole("button", { name: "Remove tag" }));
    await waitFor(() => expect(bulkCall(calls)?.body).toEqual({ filter: { q: "a" }, add: [], remove: ["t1"] }));
  });

  it("shows the cap's message when a filter matches too many to tag at once", async () => {
    const user = userEvent.setup();
    setup({ total: 7200, next: "cursor-2", tooBig: true });
    await screen.findAllByTestId("contact-row");
    await user.click(screen.getByRole("checkbox", { name: "Select all on this page" }));
    await user.click(await screen.findByRole("button", { name: "Select all 7,200 contacts" }));
    await chooseTag(user, "vip");
    await user.click(screen.getByRole("button", { name: "Add tag" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith(expect.stringMatching(/matches 7,200 contacts/)));
  });

  it("applies a saved segment's filters, and saves the current ones as a segment", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ segments: [segment] });
    await screen.findAllByTestId("contact-row");
    await user.click(await screen.findByRole("button", { name: "Warm leads" }));
    await waitFor(() => expect(listCalls(calls).at(-1)?.url.searchParams.getAll("tag_id")).toEqual(["t1"]));
    expect(screen.getByRole("button", { name: "Warm leads" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("button", { name: "Save as segment" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Clear" }));
    await user.type(screen.getByRole("searchbox", { name: "Search contacts" }), "priya");
    await user.click(await screen.findByRole("button", { name: "Save as segment" }));
    await user.type(await screen.findByLabelText("Name"), "Priya fans");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => {
      const post = calls.find((c) => c.method === "POST" && c.path.endsWith("/contact-segments"));
      expect(post?.body).toEqual({ name: "Priya fans", filter: { q: "priya" } });
    });
  });

  it("exports the filtered rows for admins", async () => {
    const user = userEvent.setup();
    const create = vi.fn(() => "blob:csv");
    Object.assign(URL, { createObjectURL: create, revokeObjectURL: vi.fn() });
    const { calls } = setup();
    await screen.findAllByTestId("contact-row");
    await user.click(screen.getByRole("button", { name: "Export CSV" }));
    await waitFor(() => expect(create).toHaveBeenCalled());
    expect(calls.some((c) => c.path.endsWith("/contacts/export.csv"))).toBe(true);
  });

  it("hides export and deleting segments from agents", async () => {
    setup({ role: "agent", segments: [segment] });
    await screen.findAllByTestId("contact-row");
    expect(screen.queryByRole("button", { name: "Export CSV" })).not.toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Warm leads" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete the Warm leads segment" })).not.toBeInTheDocument();
  });

  it("opens the contact drawer from a row", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    const rows = await screen.findAllByTestId("contact-row");
    await user.click(within(rows[0]).getByRole("button", { name: "Open Priya Nair" }));
    await waitFor(() => expect(calls.some((c) => c.path === "/v1/w/w1/contacts/p1")).toBe(true));
  });
});
