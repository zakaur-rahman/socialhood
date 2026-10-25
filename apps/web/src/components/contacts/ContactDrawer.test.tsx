import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it, vi } from "vitest";

import type { ContactRecord, TimelineItem } from "@/lib/api/types";
import { json, problem, renderWithApi, workspace, type Call } from "@/test/api";

import { ContactDrawer } from "./ContactDrawer";

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

const record: ContactRecord = {
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
  last_activity_at: "2026-10-23T10:00:00Z",
  first_seen_at: "2026-09-27T09:00:00Z",
  fields: { city: "Pune" },
  name_source: "platform",
  platform_name: "Priya Nair",
  email_source: "flow",
  email_verified: false,
  phone_source: null,
  phone_verified: false,
  first_entry_source: "link",
  consents: [
    { channel: "instagram", purpose: "marketing", status: "granted", source: "platform_optin", occurred_at: "2026-10-01T10:00:00Z", note: null },
  ],
};

const timeline: TimelineItem[] = [
  { id: "i1", kind: "comment", occurred_at: "2026-10-23T10:00:00Z", title: "Commented", detail: "LINK please", conversation_id: null },
  { id: "i2", kind: "automation_run", occurred_at: "2026-10-23T10:01:00Z", title: "Automation: Send the link", detail: "Replied", conversation_id: "c1" },
  { id: "i3", kind: "conversation", occurred_at: "2026-10-01T09:00:00Z", title: "Conversation started", detail: "From an entry link", conversation_id: "c1" },
];

function setup(options: { role?: "owner" | "agent"; next?: string | null; cold?: boolean; saved?: Partial<ContactRecord>; patch?: (call: Call) => Response } = {}) {
  let served = 0;
  let stage = record.lead_stage;
  const onClose = vi.fn();
  const view = renderWithApi(<ContactDrawer contactId="p1" onClose={onClose} />, {
    ws: { ...workspace, role: options.role ?? "owner" },
    handlers: {
      "GET /v1/w/:wid/contacts/:id": () => json({ ...record, ...options.saved, lead_stage: stage, lead_cold: options.cold ?? false }),
      "GET /v1/w/:wid/contacts/:id/timeline": () => {
        served += 1;
        return json(served === 1 ? { items: timeline, next_cursor: options.next ?? null } : { items: [{ ...timeline[2], id: "i4", title: "Tagged vip", kind: "tag", detail: null }], next_cursor: null });
      },
      "GET /v1/w/:wid/tags": () =>
        json({ items: [{ id: "t1", name: "lead-magnet", color: 1, contact_count: 1 }, { id: "t2", name: "vip", color: 0, contact_count: 0 }] }),
      "GET /v1/w/:wid/contact-fields": () =>
        json({
          items: [
            { id: "f1", key: "city", label: "City", type: "text", options: [], position: 0 },
            { id: "f2", key: "size", label: "Size", type: "choice", options: ["S", "M"], position: 1 },
          ],
          limit: 5,
        }),
      "PATCH /v1/w/:wid/contacts/:id": options.patch ?? ((call) => json({ ...record, ...(call.body as object) })),
      "POST /v1/w/:wid/contacts/:id/tags": () => json({ ...record, tags: [...record.tags, { id: "t2", name: "vip", color: 0 }] }),
      "POST /v1/w/:wid/contacts/:id/consents": () => json(record),
      "POST /v1/w/:wid/contacts/:id/lead-stage": (call) => {
        stage = (call.body as { stage: ContactRecord["lead_stage"] }).stage;
        return json({ ...record, lead_stage: stage });
      },
    },
  });
  return { ...view, onClose };
}

describe("ContactDrawer (GR-17)", () => {
  it("shows the contact's tags, details, consent and timeline", async () => {
    setup();
    const drawer = await screen.findByRole("dialog");
    expect(await within(drawer).findByText("Priya Nair")).toBeInTheDocument();
    expect(within(drawer).getByRole("list", { name: "Tags on this contact" })).toHaveTextContent("lead-magnet");
    expect(await within(drawer).findByLabelText("Email")).toHaveValue("priya@example.com");
    expect(await within(drawer).findByLabelText("City")).toHaveValue("Pune");
    expect(within(drawer).getByTestId("consent-row")).toHaveTextContent("Instagram: Agreed");
    const items = await within(drawer).findAllByTestId("timeline-item");
    expect(items.map((i) => i.getAttribute("data-kind"))).toEqual(["comment", "automation_run", "conversation"]);
    expect(within(drawer).getByText("LINK please")).toBeInTheDocument();
    expect(within(drawer).getAllByRole("link", { name: "Open conversation" }).length).toBeGreaterThan(0);
  });

  it("saves a renamed contact as the team's name (C-135)", async () => {
    const user = userEvent.setup();
    let body: Record<string, unknown> = {};
    setup({ patch: (call) => ((body = call.body as Record<string, unknown>), json({ ...record, name: "Priya (wholesale)", name_source: "team" })) });
    const drawer = await screen.findByRole("dialog");
    const name = await within(drawer).findByLabelText("Name");
    await user.clear(name);
    await user.type(name, "Priya (wholesale)");
    await user.click(within(drawer).getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(body.name).toBe("Priya (wholesale)"));
  });

  it("shows the platform's name beside a team name and goes back to it (C-135)", async () => {
    const user = userEvent.setup();
    let body: Record<string, unknown> = {};
    setup({
      saved: { name: "Priya (wholesale)", name_source: "team", platform_name: "Priya N." },
      patch: (call) => ((body = call.body as Record<string, unknown>), json({ ...record, name: "Priya N.", name_source: "platform", platform_name: "Priya N." })),
    });
    const drawer = await screen.findByRole("dialog");
    expect(await within(drawer).findByText(/Instagram name: Priya N\./)).toBeInTheDocument();
    await user.click(within(drawer).getByRole("button", { name: "Use this name" }));
    await waitFor(() => expect(body.use_platform_name).toBe(true));
  });

  it("shows the lead stage and why it is there", async () => {
    setup();
    const drawer = await screen.findByRole("dialog");
    expect(await within(drawer).findByTestId("lead-stage")).toHaveTextContent("Qualified");
    expect(within(drawer).getByText("Lead score reached 72.")).toBeInTheDocument();
    expect(within(drawer).getByRole("combobox", { name: "Lead stage" })).toHaveTextContent("Qualified");
    expect(within(drawer).queryByText("Gone cold")).not.toBeInTheDocument();
  });

  it("flags a lead that has gone cold", async () => {
    setup({ cold: true });
    const drawer = await screen.findByRole("dialog");
    expect(await within(drawer).findByText("Gone cold")).toBeInTheDocument();
  });

  it("moves the lead to another stage with a note, for any member", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ role: "agent" });
    const drawer = await screen.findByRole("dialog");
    await user.type(await within(drawer).findByLabelText("Why? (optional)"), "Paid in full");
    await user.click(within(drawer).getByRole("combobox", { name: "Lead stage" }));
    await user.click(await screen.findByRole("option", { name: "Won" }));
    await waitFor(() => {
      const post = calls.find((c) => c.method === "POST" && c.path.endsWith("/lead-stage"));
      expect(post?.body).toEqual({ stage: "won", note: "Paid in full" });
    });
    await waitFor(() => expect(within(drawer).getByTestId("lead-stage")).toHaveTextContent("Won"));
    expect(within(drawer).getByLabelText("Why? (optional)")).toHaveValue("");
  });

  it("saves only what changed, and removes an emptied field", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    const drawer = await screen.findByRole("dialog");
    const save = await within(drawer).findByRole("button", { name: "Save changes" });
    expect(save).toBeDisabled();
    const city = await within(drawer).findByLabelText("City");
    await user.clear(city);
    await user.clear(within(drawer).getByLabelText("Email"));
    await user.type(within(drawer).getByLabelText("Phone"), "98765 43210");
    await user.click(save);
    await waitFor(() => {
      const patch = calls.find((c) => c.method === "PATCH");
      expect(patch?.body).toEqual({ clear_email: true, clear_phone: false, phone: "98765 43210", fields: { city: null } });
    });
  });

  it("puts the API's message beside the value it refuses", async () => {
    const user = userEvent.setup();
    setup({
      patch: () =>
        new Response(
          JSON.stringify({
            type: "about:blank",
            title: "validation_error",
            status: 422,
            code: "validation_error",
            errors: [{ field: "email", message: "Enter an email address like name@example.com." }],
          }),
          { status: 422, headers: { "Content-Type": "application/problem+json" } },
        ),
    });
    const drawer = await screen.findByRole("dialog");
    const email = await within(drawer).findByLabelText("Email");
    await user.clear(email);
    await user.type(email, "nope");
    await user.click(within(drawer).getByRole("button", { name: "Save changes" }));
    expect(await within(drawer).findByText("Enter an email address like name@example.com.")).toBeInTheDocument();
  });

  it("adds a tag from the list and removes one", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    const drawer = await screen.findByRole("dialog");
    await user.click(await within(drawer).findByRole("button", { name: "Remove lead-magnet" }));
    await waitFor(() => {
      const post = calls.find((c) => c.method === "POST" && c.path.endsWith("/contacts/p1/tags"));
      expect(post?.body).toEqual({ add: [], remove: ["t1"] });
    });
    await user.click(await within(drawer).findByRole("combobox", { name: "Add a tag" }));
    await user.click(await screen.findByRole("option", { name: "vip" }));
    await waitFor(() => {
      const posts = calls.filter((c) => c.method === "POST" && c.path.endsWith("/contacts/p1/tags"));
      expect(posts.at(-1)?.body).toEqual({ add: ["t2"], remove: [] });
    });
  });

  it("pages the timeline", async () => {
    const user = userEvent.setup();
    setup({ next: "page-2" });
    const drawer = await screen.findByRole("dialog");
    await user.click(await within(drawer).findByRole("button", { name: "Show older" }));
    await waitFor(() => expect(within(drawer).getAllByTestId("timeline-item")).toHaveLength(4));
    expect(within(drawer).getByText("Tagged vip")).toBeInTheDocument();
  });

  it("lets admins record consent and not agents", async () => {
    const user = userEvent.setup();
    const { calls, unmount } = setup();
    const drawer = await screen.findByRole("dialog");
    await user.click(await within(drawer).findByRole("button", { name: "Record consent" }));
    await user.type(await screen.findByLabelText("Note"), "Said yes on the shop form");
    await user.click(screen.getByRole("button", { name: "Record" }));
    await waitFor(() => {
      const post = calls.find((c) => c.method === "POST" && c.path.endsWith("/consents"));
      expect(post?.body).toEqual({ channel: "instagram", status: "granted", note: "Said yes on the shop form" });
    });
    unmount();

    setup({ role: "agent" });
    const agentDrawer = await screen.findByRole("dialog");
    await within(agentDrawer).findByText("Priya Nair");
    expect(within(agentDrawer).queryByRole("button", { name: "Record consent" })).not.toBeInTheDocument();
    expect(within(agentDrawer).queryByLabelText("New tag name")).not.toBeInTheDocument();
  });

  it("says when the contact did not load", async () => {
    renderWithApi(<ContactDrawer contactId="gone" onClose={() => {}} />, {
      handlers: { "GET /v1/w/:wid/contacts/:id": () => problem(404, "not_found") },
    });
    expect(await screen.findByText(/did not load/)).toBeInTheDocument();
  });
});
