import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { keys } from "@/lib/api/queries";
import type { BillingState, Payment } from "@/lib/api/types";
import { browser } from "@/lib/billing/browser";
import { billingState, json, planList, problem, renderWithApi, workspace, type Call } from "@/test/api";

import { BillingPage } from "./BillingPage";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

const nav = vi.hoisted(() => ({ replace: vi.fn(), push: vi.fn(), search: "" }));
vi.mock("next/navigation", () => ({
  useRouter: () => nav,
  usePathname: () => "/w/maple/settings/billing",
  useSearchParams: () => new URLSearchParams(nav.search),
}));

const inr = { plan: "pro" as const, amount_minor: 99_900, currency: "INR", interval: "month" as const };

const free = billingState({
  plan: "free",
  status: "free",
  current_period_end: null,
  trial_eligible: true,
  prices: [inr],
  entitlements: [{ key: "active_automations", value: 3 }],
  usage: [
    { metric: "ai_credits", used: 120, limit: 200, period_end: "2026-10-01" },
    { metric: "scheduled_posts", used: 10, limit: 10, period_end: "2026-10-01" },
    { metric: "knowledge_characters", used: 1_240, limit: 200_000 },
  ],
});

const pro = billingState({ current_period_end: "2026-10-31T18:30:00Z", prices: [inr] });

function setup({
  billing = free,
  role = "owner",
  handlers = {},
}: {
  billing?: BillingState | (() => BillingState);
  role?: "owner" | "admin" | "agent";
  handlers?: Record<string, (call: Call) => Response>;
} = {}) {
  const state = { billing: typeof billing === "function" ? billing() : billing };
  const view = renderWithApi(<BillingPage />, {
    ws: { ...workspace, role, plan: state.billing.plan },
    handlers: {
      "GET /v1/w/:wid/billing": () => json(typeof billing === "function" ? billing() : state.billing),
      "GET /v1/billing/plans": () => json(planList()),
      "POST /v1/w/:wid/billing/checkout": () => json({ checkout_url: "https://checkout.dodo.test/s/1", trial: true }),
      "POST /v1/w/:wid/billing/portal": () => json({ portal_url: "https://portal.dodo.test/p/1" }),
      "GET /v1/w/:wid/billing/payments": () => json({ items: [], next_cursor: null }),
      "POST /v1/w/:wid/billing/cancel": () => {
        state.billing = { ...state.billing, cancel_at_period_end: true };
        return json(state.billing);
      },
      "POST /v1/w/:wid/billing/resume": () => {
        state.billing = { ...state.billing, cancel_at_period_end: false };
        return json(state.billing);
      },
      ...handlers,
    },
  });
  const posts = (suffix: string) => view.calls.filter((c) => c.method === "POST" && c.path.endsWith(suffix));
  return { ...view, posts };
}

beforeEach(() => {
  nav.replace.mockReset();
  nav.search = "";
  toast.success.mockReset();
  toast.error.mockReset();
});

afterEach(() => vi.restoreAllMocks());

describe("Billing page (UX-SCR-07, F-15)", () => {
  it("Free: the plan, a meter per limit, the plans side by side, and Start 7-day trial goes to checkout", async () => {
    const user = userEvent.setup();
    const assign = vi.spyOn(browser, "assign").mockImplementation(() => {});
    const { posts } = setup();

    const current = await screen.findByRole("region", { name: "Free" });
    expect(current).toHaveTextContent("Upgrade for more accounts");
    const credits = screen.getByRole("meter", { name: "AI credits" });
    expect(credits).toHaveAttribute("aria-valuetext", "120 of 200 credits");
    expect(screen.getByText("Scheduled posts").closest("[data-level]")).toHaveAttribute("data-level", "full");
    expect(screen.getByText("Free includes 10 scheduled posts a month.")).toBeInTheDocument();
    expect(screen.getAllByText("Resets on 1 Oct")).toHaveLength(2);
    // Limits GET …/billing doesn't count are listed, never counted by the page.
    expect(screen.getByRole("list", { name: "Other limits" })).toHaveTextContent("3 active automations");

    const plans = await screen.findByRole("list", { name: "Plans" });
    const cards = within(plans).getAllByRole("listitem").filter((li) => li.parentElement === plans);
    expect(cards).toHaveLength(3);
    expect(cards[0]).toHaveAttribute("aria-current", "true");
    expect(cards[1]).toHaveTextContent("₹999 a month");
    expect(cards[1]).toHaveTextContent("50 active automations");
    expect(cards[2]).toHaveTextContent("Coming soon");

    await user.click(within(current).getByRole("button", { name: "Start 7-day trial" }));
    await waitFor(() => expect(assign).toHaveBeenCalledWith("https://checkout.dodo.test/s/1"));
    expect(posts("/billing/checkout")[0].body).toEqual({ plan: "pro" });
  });

  it("checkout errors get their own copy", async () => {
    const user = userEvent.setup();
    setup({ handlers: { "POST /v1/w/:wid/billing/checkout": () => problem(503, "internal", "Dodo is down") } });
    const current = await screen.findByRole("region", { name: "Free" });
    await user.click(within(current).getByRole("button", { name: "Start 7-day trial" }));
    expect(await within(current).findByRole("alert")).toHaveTextContent(
      "Payments aren't available right now. Try again in a few minutes.",
    );
  });

  it("Pro: renewal date and price; Manage billing opens the portal in a new tab", async () => {
    const user = userEvent.setup();
    const tab = { go: vi.fn(), cancel: vi.fn() };
    vi.spyOn(browser, "openPending").mockReturnValue(tab);
    setup({ billing: pro });
    const current = await screen.findByRole("region", { name: "Pro" });
    expect(current).toHaveTextContent("Active");
    expect(current).toHaveTextContent("Renews on 1 Nov · ₹999 a month");
    expect(within(current).queryByRole("button", { name: /trial|Upgrade/ })).not.toBeInTheDocument();
    await user.click(within(current).getByRole("button", { name: "Manage billing" }));
    await waitFor(() => expect(tab.go).toHaveBeenCalledWith("https://portal.dodo.test/p/1"));
  });

  it("a portal without a billing account closes the tab and says so", async () => {
    const user = userEvent.setup();
    const tab = { go: vi.fn(), cancel: vi.fn() };
    vi.spyOn(browser, "openPending").mockReturnValue(tab);
    setup({ billing: pro, handlers: { "POST /v1/w/:wid/billing/portal": () => problem(409, "conflict") } });
    await user.click(await screen.findByRole("button", { name: "Manage billing" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith(
      "There's no billing account for this workspace yet. It's created when you upgrade.",
    ));
    expect(tab.cancel).toHaveBeenCalled();
  });

  it("Cancel asks first with the end date and what Free changes, then Resume undoes it", async () => {
    const user = userEvent.setup();
    const { posts } = setup({ billing: pro });
    const current = await screen.findByRole("region", { name: "Pro" });
    await user.click(within(current).getByRole("button", { name: "Cancel plan" }));
    const confirm = await screen.findByRole("alertdialog", { name: "Cancel Pro?" });
    expect(confirm).toHaveTextContent("Pro stays until 1 Nov.");
    expect(confirm).toHaveTextContent("Accounts in Auto switch to Suggest");
    expect(confirm).toHaveTextContent("Nothing is deleted.");
    expect(posts("/billing/cancel")).toHaveLength(0);
    await user.click(within(confirm).getByRole("button", { name: "Cancel plan" }));

    await waitFor(() => expect(posts("/billing/cancel")).toHaveLength(1));
    await waitFor(() => expect(current).toHaveTextContent("Pro until 1 Nov. Then the workspace moves to Free."));
    expect(current).toHaveTextContent("Cancelling");
    expect(toast.success).toHaveBeenCalledWith("Pro until 1 Nov");

    await user.click(within(current).getByRole("button", { name: "Resume Pro" }));
    const resume = await screen.findByRole("alertdialog", { name: "Resume Pro?" });
    expect(resume).toHaveTextContent("Pro renews on 1 Nov at ₹999 a month");
    await user.click(within(resume).getByRole("button", { name: "Resume Pro" }));
    await waitFor(() => expect(posts("/billing/resume")).toHaveLength(1));
    await waitFor(() => expect(current).toHaveTextContent("Renews on 1 Nov"));
  });

  it("on hold: payment failed, the grace end, and Update payment method", async () => {
    setup({ billing: billingState({ status: "on_hold", grace_until: "2026-10-03T06:00:00Z" }) });
    const current = await screen.findByRole("region", { name: "Pro" });
    expect(current).toHaveTextContent("On hold");
    expect(current).toHaveTextContent("Update your payment method by 3 Oct to keep Pro.");
    expect(within(current).getByRole("button", { name: "Update payment method" })).toBeInTheDocument();
    expect(within(current).queryByRole("button", { name: "Cancel plan" })).not.toBeInTheDocument();
  });

  it("admins see it read-only", async () => {
    setup({ role: "admin" });
    const current = await screen.findByRole("region", { name: "Free" });
    expect(current).toHaveTextContent("Only the workspace owner can change the plan.");
    expect(screen.queryByRole("button", { name: /trial|Upgrade|Manage|Cancel/ })).not.toBeInTheDocument();
  });

  it("agents are sent to their notification settings", async () => {
    const { calls } = setup({ role: "agent" });
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/w/maple/settings/notifications"));
    expect(calls.some((c) => c.path.endsWith("/billing"))).toBe(false);
  });
});

describe("checkout return (F-15, FR-BIL-02)", () => {
  it("waits for the webhook: Confirming your payment… until GET …/billing shows Pro (usage.updated)", async () => {
    nav.search = "checkout=return";
    let current: BillingState = free;
    const { queryClient } = setup({ billing: () => current });
    expect(await screen.findByText("Confirming your payment…")).toBeInTheDocument();
    // The return URL alone changes nothing, and the address loses ?checkout=return.
    expect(screen.getByRole("region", { name: "Free" })).toBeInTheDocument();
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/w/maple/settings/billing", { scroll: false }));

    current = billingState({ status: "trialing", trial_ends_at: "2026-10-07T06:00:00Z", prices: [inr] });
    await act(() => queryClient.invalidateQueries({ queryKey: keys.billing(workspace.id) }));
    expect(await screen.findByText("Your Pro trial has started")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Pro" })).toHaveTextContent("Trial");
  });

  it("polls every 3 s, and after 60 s says it can take a minute", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      nav.search = "checkout=return";
      const { calls } = setup();
      expect(await screen.findByText("Confirming your payment…")).toBeInTheDocument();
      const gets = () => calls.filter((c) => c.method === "GET" && c.path === "/v1/w/w1/billing").length;
      const first = gets();
      await act(() => vi.advanceTimersByTimeAsync(9_500));
      expect(gets()).toBeGreaterThanOrEqual(first + 3);
      await act(() => vi.advanceTimersByTimeAsync(52_000));
      expect(
        await screen.findByText("Payment received? It can take a minute. We'll email you when Pro is active."),
      ).toBeInTheDocument();
      const after = gets();
      await act(() => vi.advanceTimersByTimeAsync(10_000));
      expect(gets()).toBe(after);
    } finally {
      vi.useRealTimers();
    }
  });
});

function payment(overrides: Partial<Payment> = {}): Payment {
  return {
    id: "p1",
    occurred_at: "2026-09-28T06:00:00Z",
    amount_minor: 99_900,
    currency: "INR",
    status: "succeeded",
    invoice_url: "https://invoices.dodo.test/p1",
    failure_reason: null,
    ...overrides,
  };
}

describe("payment history (C-066)", () => {
  it("lists payments newest first: date, amount and currency, status, invoice; older ones on demand", async () => {
    const user = userEvent.setup();
    const { calls } = setup({
      billing: pro,
      handlers: {
        "GET /v1/w/:wid/billing/payments": (call) =>
          call.url.searchParams.get("cursor") === "c2"
            ? json({ items: [payment({ id: "p4", occurred_at: "2026-06-28T06:00:00Z" })], next_cursor: null })
            : json({
                items: [
                  payment(),
                  payment({
                    id: "p2",
                    occurred_at: "2026-08-28T06:00:00Z",
                    status: "failed",
                    invoice_url: null,
                    failure_reason: "The card was declined.",
                  }),
                  payment({ id: "p3", occurred_at: "2026-07-28T06:00:00Z", status: "refunded", amount_minor: 1_299, currency: "USD" }),
                ],
                next_cursor: "c2",
              }),
      },
    });
    const card = await screen.findByRole("region", { name: "Payment history" });
    const table = await within(card).findByRole("table", { name: "Payments, newest first" });
    const rows = () => within(table).getAllByRole("row").slice(1);
    expect(rows()).toHaveLength(3);
    expect(rows()[0]).toHaveTextContent("28 Sep");
    expect(rows()[0]).toHaveTextContent("₹999");
    expect(rows()[0]).toHaveTextContent("INR");
    expect(rows()[0]).toHaveTextContent("Paid");
    const invoice = within(rows()[0]).getByRole("link", { name: "Invoice for 28 Sep (opens in a new tab)" });
    expect(invoice).toHaveAttribute("href", "https://invoices.dodo.test/p1");
    expect(invoice).toHaveAttribute("target", "_blank");
    expect(rows()[1]).toHaveTextContent("Failed");
    expect(rows()[1]).toHaveTextContent("The card was declined.");
    expect(rows()[1]).toHaveTextContent("No invoice");
    expect(rows()[2]).toHaveTextContent("Refunded");
    expect(rows()[2]).toHaveTextContent("$12.99");
    expect(rows()[2]).toHaveTextContent("USD");

    await user.click(within(card).getByRole("button", { name: "Show older payments" }));
    await waitFor(() => expect(rows()).toHaveLength(4));
    expect(rows()[3]).toHaveTextContent("28 Jun");
    expect(within(card).queryByRole("button", { name: "Show older payments" })).toBeNull();
    const cursors = calls.filter((c) => c.path === "/v1/w/w1/billing/payments").map((c) => c.url.searchParams.get("cursor"));
    expect(cursors).toEqual([null, "c2"]);
  });

  it("an empty history says so", async () => {
    setup();
    const card = await screen.findByRole("region", { name: "Payment history" });
    expect(await within(card).findByText("No payments yet")).toBeInTheDocument();
    expect(within(card).queryByRole("table")).toBeNull();
  });

  it("admins see the history too", async () => {
    setup({ role: "admin", billing: pro, handlers: { "GET /v1/w/:wid/billing/payments": () => json({ items: [payment()], next_cursor: null }) } });
    const card = await screen.findByRole("region", { name: "Payment history" });
    expect(await within(card).findByRole("table")).toBeInTheDocument();
  });
});

describe("plan hero and quotas (C-066)", () => {
  it("a meter per metric GET …/billing counts, with its percentage and reset date", async () => {
    setup({
      billing: billingState({
        usage: [
          { metric: "ai_credits", used: 64, limit: 5000, period_end: "2026-10-28" },
          { metric: "instagram_accounts", used: 2, limit: 3 },
          { metric: "whatsapp_accounts", used: 1, limit: 3 },
        ],
      }),
    });
    const usage = await screen.findByRole("list", { name: "Usage" });
    const tiles = within(usage).getAllByRole("listitem");
    expect(tiles).toHaveLength(3);
    expect(tiles[0]).toHaveTextContent("AI credits");
    expect(tiles[0]).toHaveTextContent("1%");
    expect(tiles[0]).toHaveTextContent("Resets on 28 Oct");
    expect(tiles[1]).toHaveTextContent("Instagram accounts");
    expect(tiles[1]).toHaveTextContent("67%");
    expect(within(tiles[2]).getByRole("meter", { name: "WhatsApp accounts" })).toHaveAttribute(
      "aria-valuetext",
      "1 of 3 connected",
    );
  });
});
