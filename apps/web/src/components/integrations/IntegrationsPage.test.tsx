import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { WebhookDelivery, WebhookEndpoint, WebhookEventType } from "@/lib/api/types";
import { json, renderWithApi, type Call } from "@/test/api";

import { IntegrationsPage } from "./IntegrationsPage";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

const EVENTS: WebhookEventType[] = [
  { type: "lead.captured", version: 1, description: "An automation's question saved an email, phone or field.", emitted: true },
  { type: "contact.tagged", version: 1, description: "A tag was added to or removed from a contact.", emitted: true },
  { type: "broadcast.finished", version: 1, description: "A broadcast finished sending.", emitted: false },
];

function endpoint(values: Partial<WebhookEndpoint> = {}): WebhookEndpoint {
  return {
    id: "ep-1",
    url: "https://hooks.example.com/in",
    description: "Zapier",
    events: ["lead.captured"],
    status: "active",
    failing_deliveries: 0,
    last_success_at: null,
    last_failure_at: null,
    disabled_at: null,
    created_at: "2026-10-24T09:00:00Z",
    ...values,
  };
}

function delivery(values: Partial<WebhookDelivery> = {}): WebhookDelivery {
  return {
    id: "d-1",
    endpoint_id: "ep-1",
    event_id: "ev-1",
    event_type: "lead.captured",
    status: "failed",
    attempts: 7,
    response_code: 500,
    duration_ms: 120,
    error: "The endpoint answered 500.",
    next_attempt_at: null,
    last_attempt_at: "2026-10-24T09:00:00Z",
    replay_of_id: null,
    created_at: "2026-10-24T08:00:00Z",
    payload: {},
    ...values,
  };
}

function setup({ endpoints = [] as WebhookEndpoint[], deliveries = [] as WebhookDelivery[], create }: { endpoints?: WebhookEndpoint[]; deliveries?: WebhookDelivery[]; create?: (call: Call) => Response } = {}) {
  return renderWithApi(<IntegrationsPage />, {
    handlers: {
      "GET /v1/w/:wid/webhook-events": () => json({ items: EVENTS }),
      "GET /v1/w/:wid/webhook-endpoints": () => json({ items: endpoints, limit: 1 }),
      "GET /v1/w/:wid/webhook-endpoints/:id/deliveries": () => json({ items: deliveries, next_cursor: null }),
      "POST /v1/w/:wid/webhook-endpoints": (call) =>
        create ? create(call) : json({ ...endpoint(), ...(call.body as object), signing_secret: "whsec_abc123" }, 201),
      "PATCH /v1/w/:wid/webhook-endpoints/:id": (call) => json(endpoint(call.body as Partial<WebhookEndpoint>)),
      "POST /v1/w/:wid/webhook-deliveries/:id/replay": () => json(delivery({ id: "d-2", status: "pending", attempts: 0 }), 202),
    },
  });
}

beforeEach(() => {
  toast.success.mockReset();
  toast.error.mockReset();
});

describe("Settings › Integrations (GR-04)", () => {
  it("adds an endpoint and shows its signing secret once", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    expect(await screen.findByText("No endpoints yet")).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "Add endpoint" })[0]);
    const dialog = await screen.findByRole("dialog", { name: "Add a webhook endpoint" });
    await user.type(within(dialog).getByRole("textbox", { name: "Endpoint address" }), "https://hooks.example.com/in");
    await user.type(within(dialog).getByRole("textbox", { name: "Name (optional)" }), "Zapier");
    expect(within(dialog).getByText(/Coming with that feature/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Add endpoint" }));
    const secret = await screen.findByRole("dialog", { name: "Your signing secret" });
    expect(within(secret).getByTestId("signing-secret")).toHaveTextContent("whsec_abc123");
    const [post] = calls.filter((c) => c.method === "POST");
    expect(post.body).toEqual({ url: "https://hooks.example.com/in", description: "Zapier", events: ["lead.captured"] });
  });

  it("shows the address the API refused on the field", async () => {
    const user = userEvent.setup();
    setup({
      create: () =>
        new Response(
          JSON.stringify({
            type: "about:blank",
            title: "Validation error",
            status: 422,
            code: "validation_error",
            errors: [{ field: "url", message: "Use an address that starts with https://." }],
          }),
          { status: 422, headers: { "Content-Type": "application/problem+json" } },
        ),
    });
    await user.click((await screen.findAllByRole("button", { name: "Add endpoint" }))[0]);
    const dialog = await screen.findByRole("dialog", { name: "Add a webhook endpoint" });
    const url = within(dialog).getByRole("textbox", { name: "Endpoint address" });
    await user.type(url, "https://hooks.example.com/in");
    await user.click(within(dialog).getByRole("button", { name: "Add endpoint" }));
    expect(await within(dialog).findByText("Use an address that starts with https://.")).toBeInTheDocument();
    expect(url).toHaveAttribute("aria-invalid", "true");
  });

  it("pauses an endpoint and resends a failed delivery", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ endpoints: [endpoint()], deliveries: [delivery()] });
    const card = await screen.findByRole("region", { name: "Zapier" });
    expect(within(card).getByText("On")).toBeInTheDocument();
    const row = await within(card).findByTestId("webhook-delivery");
    expect(row).toHaveTextContent("lead.captured");
    expect(row).toHaveTextContent("Failed");
    expect(row).toHaveTextContent("The endpoint answered 500.");
    expect(row).toHaveTextContent("120 ms");

    await user.click(within(card).getByRole("switch", { name: "Send events to Zapier" }));
    await waitFor(() =>
      expect(calls.filter((c) => c.method === "PATCH").map((c) => c.body)).toEqual([{ status: "paused" }]),
    );
    await user.click(within(row).getByRole("button", { name: "Send lead.captured again" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/replay"))).toBe(true));
    expect(toast.success).toHaveBeenCalledWith("Sent again");
  });

  it("says when an endpoint was turned off after failures", async () => {
    setup({ endpoints: [endpoint({ status: "disabled", failing_deliveries: 5 })] });
    const card = await screen.findByRole("region", { name: "Zapier" });
    expect(within(card).getByText("Turned off after failures")).toBeInTheDocument();
    expect(within(card).getByRole("button", { name: "Send test event" })).toBeDisabled();
  });
});
