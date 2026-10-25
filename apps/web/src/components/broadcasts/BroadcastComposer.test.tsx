import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it, vi } from "vitest";

import type { Broadcast, BroadcastAvailability, BroadcastPreview } from "@/lib/api/types";
import { pickDate } from "@/test/datepicker";
import { account, json, problem, renderWithApi, type Call } from "@/test/api";

import { BroadcastComposer, toSpecs, variablesReady } from "./BroadcastComposer";

const nav = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: nav.push, replace: vi.fn() }),
  useParams: () => ({ slug: "maple" }),
  usePathname: () => "/w/maple/broadcasts/new",
  useSearchParams: () => new URLSearchParams(""),
}));

// Radix Select's pointer APIs, which jsdom lacks (as in components/ui/select.test.tsx).
beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});

const availability: BroadcastAvailability = {
  enabled: true,
  plan_allowed: true,
  monthly_limit: 2500,
  used_this_period: 100,
  period_end: "2026-11-24T00:00:00Z",
  rate_card: {
    currency: "INR",
    country: "India",
    as_of: "2026-10-24",
    source: "typed in by hand",
    verified: false,
    rates: { marketing: "0.7846", utility: "0.1150", authentication: "0.1150" },
  },
};

const preview: BroadcastPreview = {
  audience: { matching: 5, eligible: 3, opted_out: 1, no_consent: 1, missing_value: 0 },
  cost: {
    currency: "INR",
    category: "marketing",
    per_message: "0.7846",
    total: "2.35",
    as_of: "2026-10-24",
    source: "typed in by hand",
    verified: false,
  },
  quota: { limit: 2500, used: 100, remaining: 2400, period_end: "2026-11-24T00:00:00Z", fits: true },
  number: { quality_rating: "green", daily_limit: 1000, limit_known: true, days_to_send: 1 },
  sample: { contact_name: "Asha Rao", text: "Hi Asha, our sale is on until 31 October. Reply STOP to opt out." },
  problems: [],
};

const saved = { id: "b1", name: "Diwali sale", status: "draft" } as unknown as Broadcast;

function setup(overrides: Record<string, () => Response> = {}) {
  return renderWithApi(<BroadcastComposer />, {
    handlers: {
      "GET /v1/w/:wid/broadcasts/availability": () => json(availability),
      "GET /v1/w/:wid/social-accounts": () =>
        json({ items: [account({ id: "wa1", platform: "whatsapp", display_name: "Maple Orders", username: null })] }),
      "GET /v1/w/:wid/contact-segments": () =>
        json({ items: [{ id: "s1", name: "Everyone", filter: {}, created_at: "2026-10-01T00:00:00Z" }] }),
      "GET /v1/w/:wid/contact-fields": () => json({ items: [{ id: "f1", key: "city", label: "City", type: "text", options: [], position: 0 }], limit: 5 }),
      "GET /v1/w/:wid/social-accounts/:id/templates": () =>
        json({
          items: [
            { name: "sale_offer", language: "en", category: "marketing", status: "approved", body: "Hi {{1}}, our sale is on until {{2}}. Reply STOP to opt out.", param_count: 2 },
            { name: "login_code", language: "en", category: "authentication", status: "approved", body: "{{1}} is your code", param_count: 1 },
          ],
        }),
      "POST /v1/w/:wid/broadcasts/preview": () => json(preview),
      "POST /v1/w/:wid/broadcasts": () => json(saved, 201),
      "POST /v1/w/:wid/broadcasts/:id/start": () => json({ ...saved, status: "sending" }),
      ...overrides,
    },
  });
}

async function fill(user: ReturnType<typeof userEvent.setup>) {
  await user.type(await screen.findByLabelText("Name"), "Diwali sale");
  await user.click(await screen.findByRole("combobox", { name: "Segment" }));
  await user.click(await screen.findByRole("option", { name: "Everyone" }));
  await user.click(await screen.findByRole("combobox", { name: "Template" }));
  await user.click(await screen.findByRole("option", { name: /sale_offer/ }));
  // Variable 2 starts as a contact field; this one is the same text for everyone.
  await user.click(within(screen.getByRole("radiogroup", { name: "Variable 2 comes from" })).getByRole("radio", { name: "The same text" }));
  await user.type(screen.getByLabelText("Variable 2 text"), "31 October");
}

describe("the broadcast composer (GR-23)", () => {
  it("shows only a notice while broadcasts are switched off", async () => {
    renderWithApi(<BroadcastComposer />, {
      handlers: { "GET /v1/w/:wid/broadcasts/availability": () => json({ enabled: false }) },
    });
    expect(await screen.findByText("Broadcasts aren't available yet")).toBeInTheDocument();
    expect(screen.queryByLabelText("Name")).not.toBeInTheDocument();
  });

  it("explains a plan without broadcasts", async () => {
    renderWithApi(<BroadcastComposer />, {
      handlers: { "GET /v1/w/:wid/broadcasts/availability": () => json({ ...availability, plan_allowed: false, monthly_limit: 0 }) },
    });
    expect(await screen.findByText(/Broadcasts are part of Pro/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Name")).not.toBeInTheDocument();
  });

  it("offers approved templates but never authentication ones, and one row per variable", async () => {
    const user = userEvent.setup();
    setup();
    await user.click(await screen.findByRole("combobox", { name: "Template" }));
    expect(await screen.findByRole("option", { name: /sale_offer/ })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /login_code/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole("option", { name: /sale_offer/ }));
    expect(screen.getByTestId("template-body")).toHaveTextContent("Hi {{1}}, our sale is on until {{2}}.");
    expect(screen.getByText("Variable 1")).toBeInTheDocument();
    expect(screen.getByText("Variable 2")).toBeInTheDocument();
    expect(screen.queryByText("Variable 3")).not.toBeInTheDocument();
  });

  it("asks the server for the preview with the mapping and shows who, the cost and a sample", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    await fill(user);

    const eligible = await screen.findByTestId("eligible");
    expect(eligible).toHaveTextContent("3 people");
    const skipped = screen.getByTestId("skipped");
    expect(within(skipped).getByText(/1 skipped: asked not to get marketing messages/)).toBeInTheDocument();
    expect(within(skipped).getByText(/1 skipped: haven't agreed/)).toBeInTheDocument();
    expect(screen.getByTestId("sample")).toHaveTextContent("Hi Asha, our sale is on until 31 October.");
    expect(screen.getByText("₹2.35", { exact: false })).toBeInTheDocument();
    expect(screen.getByText(/typed in by hand, not yet checked against Meta/)).toBeInTheDocument();
    expect(screen.getByText(/Meta bills your WhatsApp Business Account directly/)).toBeInTheDocument();

    // The preview is re-asked as the mapping changes: under load the last one can still be on its way.
    const lastPreview = () => calls.filter((c: Call) => c.method === "POST" && c.path.endsWith("/broadcasts/preview")).at(-1)?.body;
    await waitFor(() => expect(lastPreview()).toEqual({
      social_account_id: "wa1",
      segment_id: "s1",
      template_name: "sale_offer",
      template_language: "en",
      variables: [
        { source: "field", field: "first_name", fallback: null },
        { source: "fixed", value: "31 October" },
      ],
    }));
  });

  it("lists what stops a send and keeps the button off", async () => {
    const user = userEvent.setup();
    setup({
      "POST /v1/w/:wid/broadcasts/preview": () =>
        json({ ...preview, audience: { ...preview.audience, eligible: 0 }, problems: ["No one in this segment can be sent to yet."] }),
    });
    await fill(user);
    expect(await screen.findByTestId("problems")).toHaveTextContent("No one in this segment can be sent to yet.");
    expect(screen.getByRole("button", { name: "Send broadcast" })).toBeDisabled();
  });

  it("creates the broadcast and starts it after a confirmation", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    await fill(user);
    await screen.findByTestId("eligible");
    const send = screen.getByRole("button", { name: "Send broadcast" });
    await waitFor(() => expect(send).toBeEnabled());
    await user.click(send);

    const dialog = await screen.findByRole("alertdialog");
    expect(dialog).toHaveTextContent("3 people in Everyone will get it");
    expect(dialog).toHaveTextContent("about ₹2.35");
    expect(dialog).toHaveTextContent("replies STOP");
    expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/broadcasts") && !c.path.endsWith("/preview"))).toBe(false);

    await user.click(within(dialog).getByRole("button", { name: "Send" }));
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/w/maple/broadcasts/b1"));
    const created = calls.find((c) => c.method === "POST" && c.path.endsWith("/broadcasts"));
    expect(created?.body).toMatchObject({ name: "Diwali sale", social_account_id: "wa1", segment_id: "s1" });
    const started = calls.find((c) => c.path.endsWith("/broadcasts/b1/start"));
    expect(started?.body).toEqual({ scheduled_at: null });
  });

  it("schedules at a time in the workspace's zone", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    await fill(user);
    await user.click(screen.getByRole("radio", { name: "Schedule" }));
    const send = screen.getByRole("button", { name: "Schedule broadcast" });
    expect(send).toBeDisabled();
    const day = new Date(Date.now() + 3 * 86_400_000).toISOString().slice(0, 10);
    await pickDate(user, "Date", day);
    await user.type(screen.getByLabelText("Time"), "10:30");
    await screen.findByTestId("eligible");
    await waitFor(() => expect(send).toBeEnabled());
    await user.click(send);
    await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Schedule" }));
    await waitFor(() => expect(calls.some((c) => c.path.endsWith("/broadcasts/b1/start"))).toBe(true));
    const body = calls.find((c) => c.path.endsWith("/broadcasts/b1/start"))?.body as { scheduled_at: string };
    // 10:30 in Asia/Kolkata (UTC+5:30) is 05:00 UTC.
    expect(body.scheduled_at).toBe(`${day}T05:00:00.000Z`);
  });

  it("shows the server's reason against the field that failed and keeps nothing sent", async () => {
    const user = userEvent.setup();
    const { calls } = setup({
      "POST /v1/w/:wid/broadcasts": () =>
        new Response(
          JSON.stringify({
            type: "about:blank",
            title: "validation_error",
            status: 422,
            code: "validation_error",
            errors: [{ field: "template_name", message: "That template isn't approved on this number. Choose another." }],
          }),
          { status: 422, headers: { "Content-Type": "application/problem+json" } },
        ),
    });
    await fill(user);
    await screen.findByTestId("eligible");
    await user.click(screen.getByRole("button", { name: "Save as draft" }));
    expect(await screen.findByText("That template isn't approved on this number. Choose another.")).toBeInTheDocument();
    expect(calls.some((c) => c.path.endsWith("/start"))).toBe(false);
    expect(nav.push).not.toHaveBeenCalledWith("/w/maple/broadcasts/b1");
  });

  it("goes to the broadcast, with the draft kept, when starting is refused", async () => {
    const user = userEvent.setup();
    nav.push.mockClear();
    setup({
      "POST /v1/w/:wid/broadcasts/:id/start": () =>
        problem(402, "quota_exceeded", "Your plan includes 2,500 broadcast recipients a month and 100 are left.", {
          entitlement: "broadcast_recipients_monthly",
          limit: 2500,
        }),
    });
    await fill(user);
    await screen.findByTestId("eligible");
    const send = screen.getByRole("button", { name: "Send broadcast" });
    await waitFor(() => expect(send).toBeEnabled());
    await user.click(send);
    await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Send" }));
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/w/maple/broadcasts/b1"));
  });
});

describe("the variable mapping helpers", () => {
  it("keeps only what each source uses", () => {
    expect(
      toSpecs([
        { source: "field", field: "city", value: "ignored", fallback: " Pune " },
        { source: "field", field: "first_name", value: "", fallback: "" },
        { source: "fixed", field: "city", value: "31 October", fallback: "x" },
      ]),
    ).toEqual([
      { source: "field", field: "city", fallback: "Pune" },
      { source: "field", field: "first_name", fallback: null },
      { source: "fixed", value: "31 October" },
    ]);
  });

  it("needs a field or a text for each variable", () => {
    expect(variablesReady([])).toBe(true);
    expect(variablesReady([{ source: "fixed", field: "", value: " ", fallback: "" }])).toBe(false);
    expect(variablesReady([{ source: "field", field: "", value: "", fallback: "" }])).toBe(false);
    expect(variablesReady([{ source: "field", field: "city", value: "", fallback: "" }])).toBe(true);
  });
});
