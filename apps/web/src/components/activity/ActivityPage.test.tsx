import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it, vi } from "vitest";

import type { ActivityItem } from "@/lib/api/types";
import { account, automation, json, renderWithApi } from "@/test/api";

import { ActivityPage } from "./ActivityPage";

const nav = vi.hoisted(() => ({ search: "" }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useParams: () => ({ slug: "maple" }),
  usePathname: () => "/w/maple/settings/activity",
  useSearchParams: () => new URLSearchParams(nav.search),
}));

function item(values: Partial<ActivityItem> = {}): ActivityItem {
  return {
    id: "run-1",
    kind: "automation_run",
    outcome: "failed",
    occurred_at: new Date(Date.now() - 5 * 60_000).toISOString(),
    title: "Send the link couldn't reply to @priya",
    reason: "@maple.bakery needs reconnecting before you can send from it.",
    error_code: "account_needs_reconnect",
    automation_id: "au1",
    automation_name: "Send the link",
    social_account_id: "a1",
    account_label: "@maple.bakery",
    platform: "instagram",
    action: { label: "Reconnect Instagram", href: "/settings/connections" },
    retryable: false,
    retry: null,
    ...values,
  };
}

function setup(pages: { items: ActivityItem[]; next_cursor: string | null }[]) {
  let served = 0;
  return renderWithApi(<ActivityPage />, {
    handlers: {
      "GET /v1/w/:wid/activity": () => json(pages[Math.min(served++, pages.length - 1)]),
      "GET /v1/w/:wid/social-accounts": () => json({ items: [account(), account({ id: "a2", username: "maple.two" })] }),
      "GET /v1/w/:wid/automations": () => json({ items: [automation({ id: "au1", name: "Send the link" })] }),
      "POST /v1/w/:wid/messages/:id/retry": () => json({ id: "m1" }, 202),
      "POST /v1/w/:wid/webhook-deliveries/:id/replay": () => json({ id: "d2" }, 202),
    },
  });
}

// Radix Select's pointer APIs, which jsdom lacks (as in components/ui/select.test.tsx).
beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});

describe("Settings, Activity (GR-05)", () => {
  it("shows a failed run with its reason and the reconnect link", async () => {
    setup([{ items: [item()], next_cursor: null }]);
    const row = (await screen.findAllByRole("listitem"))[0];
    expect(row).toHaveTextContent("Send the link couldn't reply to @priya");
    expect(row).toHaveTextContent("Failed");
    expect(row).toHaveTextContent("@maple.bakery needs reconnecting before you can send from it.");
    expect(row).toHaveTextContent("5m ago");
    const link = within(row).getByRole("link", { name: "Reconnect Instagram" });
    expect(link).toHaveAttribute("href", "/w/maple/settings/connections");
    expect(within(row).queryByRole("button", { name: /Retry/ })).toBeNull();
  });

  it("asks for failures only and filters by automation, account and type", async () => {
    const user = userEvent.setup();
    const { calls } = setup([{ items: [item()], next_cursor: null }]);
    await screen.findByText("Send the link couldn't reply to @priya");
    const first = calls.find((c) => c.path.endsWith("/activity"));
    expect(first?.url.searchParams.get("failures_only")).toBe("true");

    await user.click(screen.getByRole("switch", { name: "Failures only" }));
    await waitFor(() =>
      expect(calls.some((c) => c.path.endsWith("/activity") && c.url.searchParams.get("failures_only") === "false")).toBe(true),
    );
    await user.click(screen.getByRole("combobox", { name: "Type" }));
    await user.click(await screen.findByRole("option", { name: "Messages" }));
    await waitFor(() => expect(calls.some((c) => c.url.searchParams.get("kind") === "message")).toBe(true));
    await user.click(screen.getByRole("combobox", { name: "Automation" }));
    await user.click(await screen.findByRole("option", { name: "Send the link" }));
    await waitFor(() => expect(calls.some((c) => c.url.searchParams.get("automation_id") === "au1")).toBe(true));
  });

  it("opens filtered to one automation from an alert's link", async () => {
    nav.search = "automation=au1";
    const { calls } = setup([{ items: [], next_cursor: null }]);
    await screen.findByText("Nothing here");
    expect(calls.find((c) => c.path.endsWith("/activity"))?.url.searchParams.get("automation_id")).toBe("au1");
    nav.search = "";
  });

  it("retries a message and a webhook delivery where that is safe", async () => {
    const user = userEvent.setup();
    const { calls } = setup([
      {
        items: [
          item({
            id: "m1",
            kind: "message",
            title: "A message to @priya wasn't sent",
            reason: "Instagram didn't respond.",
            error_code: "platform_unavailable",
            action: null,
            retryable: true,
            retry: { kind: "message", target_id: "m1" },
          }),
          item({
            id: "d1",
            kind: "webhook_delivery",
            title: "A lead.captured event wasn't delivered to Zapier",
            reason: "The endpoint answered 500.",
            error_code: "endpoint_error",
            action: { label: "Check the endpoint", href: "/settings/integrations" },
            retryable: true,
            retry: { kind: "webhook_delivery", target_id: "d1" },
          }),
        ],
        next_cursor: null,
      },
    ]);
    const rows = await screen.findAllByRole("listitem");
    await user.click(within(rows[0]).getByRole("button", { name: /Retry/ }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/v1/w/w1/messages/m1/retry")).toBe(true));
    expect(within(rows[1]).getByRole("link", { name: "Check the endpoint" })).toHaveAttribute(
      "href",
      "/w/maple/settings/integrations",
    );
    await user.click(within(rows[1]).getByRole("button", { name: /Retry/ }));
    await waitFor(() =>
      expect(calls.some((c) => c.method === "POST" && c.path === "/v1/w/w1/webhook-deliveries/d1/replay")).toBe(true),
    );
  });

  it("pages with the cursor", async () => {
    const user = userEvent.setup();
    const { calls } = setup([
      { items: [item({ id: "run-1" })], next_cursor: "next-page" },
      { items: [item({ id: "run-2", title: "Older one couldn't reply" })], next_cursor: null },
    ]);
    await screen.findByText("Send the link couldn't reply to @priya");
    await user.click(screen.getByRole("button", { name: "Show older" }));
    expect(await screen.findByText("Older one couldn't reply")).toBeInTheDocument();
    expect(calls.filter((c) => c.path.endsWith("/activity")).at(-1)?.url.searchParams.get("cursor")).toBe("next-page");
    expect(screen.queryByRole("button", { name: "Show older" })).toBeNull();
  });

  it("says when nothing has failed", async () => {
    setup([{ items: [], next_cursor: null }]);
    expect(await screen.findByText("Nothing has failed")).toBeInTheDocument();
  });
});
