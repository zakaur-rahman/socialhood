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
  billing_available: true,
  prices: [inr],
  entitlements: [{ key: "active_automations", value: 3 }],
  usage: [
    { metric: "ai_credits", used: 120, limit: 200, period_end: "2026-10-01" },
    { metric: "scheduled_posts", used: 10, limit: 10, period_end: "2026-10-01" },
    { metric: "knowledge_characters", used: 1_240, limit: 200_000 },
  ],
});

const pro = billingState({ current_period_end: "2026-10-31T18:30:00Z", prices: [inr], current_price: inr });

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
    expect(current).toHaveTextContent("Upgrade for WhatsApp, Auto replies and more automations");
    const credits = screen.getByRole("meter", { name: "AI credits" });
    expect(credits).toHaveAttribute("aria-valuetext", "120 of 200 credits");
    expect(screen.getByText("Scheduled posts").closest("[data-level]")).toHaveAttribute("data-level", "full");
    expect(screen.getByText("Free includes 10 scheduled posts a month.")).toBeInTheDocument();
    expect(screen.getAllByText("Resets on 1 Oct")).toHaveLength(2);
    // Limits GET …/billing doesn't count are listed, never counted by the page.
    expect(screen.getByRole("list", { name: "Other limits" })).toHaveTextContent("3 active automations");

    // C-171: Usage opens first; the plans are on the Billing tab, and the address keeps it.
    expect(screen.queryByRole("list", { name: "Plans" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: /Billing/ }));
    expect(nav.replace).toHaveBeenCalledWith("/w/maple/settings/billing?tab=billing", { scroll: false });
    const plans = await screen.findByRole("list", { name: "Plans" });
    const cards = within(plans).getAllByRole("listitem").filter((li) => li.parentElement === plans);
    expect(cards).toHaveLength(4); // Free, Creator, Business and Agency (C-172, C-173)
    expect(cards[0]).toHaveAttribute("aria-current", "true");
    expect(cards[1]).toHaveTextContent("₹999 a month");
    expect(cards[1]).toHaveTextContent("25 active automations");
    expect(cards[2]).toHaveTextContent("Coming soon");

    // D-10: the header card holds the one primary; the Creator plan card offers the same action as a secondary.
    expect(within(current).getByRole("button", { name: "Start 7-day trial" })).toHaveAttribute("data-variant", "default");
    expect(within(cards[1]).getByRole("button", { name: "Start 7-day trial" })).toHaveAttribute("data-variant", "secondary");

    await user.click(within(current).getByRole("button", { name: "Start 7-day trial" }));
    await waitFor(() => expect(assign).toHaveBeenCalledWith("https://checkout.dodo.test/s/1"));
    expect(posts("/billing/checkout")[0].body).toEqual({ plan: "pro", period: "month" });
  });

  it("C-174: the 6 months switch shows the total and monthly equivalent, and checks out that period with no trial", async () => {
    const user = userEvent.setup();
    const assign = vi.spyOn(browser, "assign").mockImplementation(() => undefined);
    nav.search = "tab=billing";
    const { posts } = setup({
      handlers: { "GET /v1/billing/plans": () => json(planList({ sixMonth: true, businessOnSale: true, agencyOnSale: true })) },
    });
    const plans = await screen.findByRole("list", { name: "Plans" });
    await user.click(screen.getByRole("radio", { name: "6 months" }));

    const creator = within(plans).getByTestId("plan-pro");
    expect(creator).toHaveTextContent("$81 every 6 months");
    expect(creator).toHaveTextContent("($13.50 a month)");
    expect(within(creator).queryByRole("button", { name: /trial/i })).not.toBeInTheDocument();
    const agency = within(plans).getByTestId("plan-agency");
    expect(agency).toHaveTextContent("$315 every 6 months");
    expect(agency).toHaveTextContent("($52.50 a month), save 25%");
    expect(agency).not.toHaveTextContent("Coming soon");
    expect(within(agency).queryByRole("link", { name: "Contact us" })).not.toBeInTheDocument();

    await user.click(within(agency).getByRole("button", { name: "Upgrade to Agency" }));
    await waitFor(() => expect(assign).toHaveBeenCalled());
    expect(posts("/billing/checkout")[0].body).toEqual({ plan: "agency", period: "six_month" });
  });

  it("only the chosen plan's card spins; the other upgrade buttons are disabled", async () => {
    const user = userEvent.setup();
    vi.spyOn(browser, "assign").mockImplementation(() => undefined);
    nav.search = "tab=billing";
    setup({ handlers: { "GET /v1/billing/plans": () => json(planList({ businessOnSale: true, agencyOnSale: true })) } });
    const plans = await screen.findByRole("list", { name: "Plans" });
    await user.click(within(plans).getByRole("button", { name: "Upgrade to Business" }));
    await waitFor(() => expect(within(plans).getByRole("button", { name: "Upgrade to Business" })).toHaveAttribute("aria-busy", "true"));
    const other = within(plans).getByRole("button", { name: "Upgrade to Agency" });
    expect(other).toBeDisabled();
    expect(other).not.toHaveAttribute("aria-busy");
  });

  it("C-174: no 6 months switch until something six-month is on sale", async () => {
    nav.search = "tab=billing";
    setup();
    await screen.findByRole("list", { name: "Plans" });
    expect(screen.queryByRole("radio", { name: "6 months" })).not.toBeInTheDocument();
  });

  it("C-174: under 6 months, a plan with no six-month product keeps its monthly price and trial button", async () => {
    const user = userEvent.setup();
    nav.search = "tab=billing";
    const list = planList({ businessOnSale: true });
    const six = { plan: "max", amount_minor: 15_300, currency: "USD", interval: "six_month" };
    // Only Business has a six-month product; Creator is monthly only and Agency isn't on sale.
    const items = list.items.map((offer: { plan: string }) => (offer.plan === "max" ? { ...offer, six_month_price: six } : offer));
    setup({ handlers: { "GET /v1/billing/plans": () => json({ ...list, items }) } });
    const plans = await screen.findByRole("list", { name: "Plans" });
    await user.click(screen.getByRole("radio", { name: "6 months" }));

    const creator = within(plans).getByTestId("plan-pro");
    expect(creator).toHaveTextContent("₹999 a month");
    expect(creator).not.toHaveTextContent("every 6 months");
    expect(within(creator).getByRole("button", { name: "Start 7-day trial" })).toBeInTheDocument();
    // Not on sale: the planned six-month price, labelled, with no way to buy it.
    const agency = within(plans).getByTestId("plan-agency");
    expect(agency).toHaveTextContent("$315 every 6 months");
    expect(agency).toHaveTextContent("when we launch");
    expect(within(agency).queryByRole("button")).not.toBeInTheDocument();
    expect(within(agency).getByRole("link", { name: "Contact us" })).toBeInTheDocument();
  });

  it("C-174: the current plan shows what was bought; a reset date stays monthly on six-month billing", async () => {
    const six = { plan: "pro" as const, amount_minor: 8100, currency: "USD", interval: "six_month" as const };
    setup({
      billing: billingState({
        current_period_end: "2027-04-30T18:30:00Z",
        prices: [inr, six],
        current_price: six,
        usage: [{ metric: "ai_credits", used: 120, limit: 1500, period_end: "2026-11-01" }],
      }),
    });
    const current = await screen.findByRole("region", { name: "Creator" });
    expect(current).toHaveTextContent("$81 every 6 months");
    expect(current).not.toHaveTextContent("₹999");
    expect(screen.getByText("Resets on 1 Nov")).toBeInTheDocument();
  });

  it("C-149: without billing on the server, Free says paid plans aren't on sale and offers no checkout", async () => {
    nav.search = "tab=billing";
    setup({
      billing: { ...free, billing_available: false, prices: [] },
      handlers: { "GET /v1/billing/plans": () => json(planList({ billingOff: true })) },
    });

    const current = await screen.findByRole("region", { name: "Free" });
    expect(current).toHaveTextContent("Paid plans aren't available yet. Everything on Free keeps working.");
    expect(within(current).queryByRole("button", { name: /trial|Upgrade/ })).not.toBeInTheDocument();
    expect(screen.getByText(/Paid plans are coming soon\./)).toBeInTheDocument();

    const plans = await screen.findByRole("list", { name: "Plans" });
    const cards = within(plans).getAllByRole("listitem").filter((li) => li.parentElement === plans);
    expect(cards[1]).toHaveTextContent("Coming soon");
    expect(cards[1]).toHaveTextContent("$15");
    expect(cards[1]).toHaveTextContent("when we launch");
    expect(cards[1]).toHaveTextContent("25 active automations");
    expect(within(cards[1]).queryByRole("button")).not.toBeInTheDocument();
  });

  it("C-172: with billing off the paid plans show their planned prices, and Agency is a Coming soon card with a Contact us link and no checkout", async () => {
    nav.search = "tab=billing";
    setup({
      billing: { ...free, billing_available: false, prices: [] },
      handlers: { "GET /v1/billing/plans": () => json(planList({ billingOff: true })) },
    });
    const plans = await screen.findByRole("list", { name: "Plans" });
    const cards = within(plans).getAllByRole("listitem").filter((li) => li.parentElement === plans);
    expect(cards).toHaveLength(4);
    expect(cards[1]).toHaveTextContent("Creator");
    expect(within(cards[1]).getByTestId("planned-price-pro")).toHaveTextContent("$15");
    expect(cards[1]).toHaveTextContent("when we launch");
    expect(cards[2]).toHaveTextContent("Business");
    expect(within(cards[2]).getByTestId("planned-price-max")).toHaveTextContent("$30");
    expect(cards[2]).toHaveTextContent("when we launch");

    const agency = within(plans).getByTestId("plan-agency");
    expect(agency).toHaveTextContent("Agency");
    expect(agency).toHaveTextContent("Coming soon");
    expect(agency).toHaveTextContent("$70");
    expect(agency).toHaveTextContent("12,000 AI credits a month");
    expect(agency).not.toHaveTextContent(/Enterprise|from \$99/);
    expect(within(agency).getByRole("link", { name: "Contact us" })).toHaveAttribute("href", "mailto:support@amplychat.com");
    expect(within(agency).queryByRole("button")).not.toBeInTheDocument();
  });

  it("C-172: with billing on, Creator shows its Dodo price instead of the planned one; Business still shows the planned $30", async () => {
    nav.search = "tab=billing";
    setup();
    const plans = await screen.findByRole("list", { name: "Plans" });
    const cards = within(plans).getAllByRole("listitem").filter((li) => li.parentElement === plans);
    expect(cards[1]).toHaveTextContent("₹999 a month");
    expect(cards[1]).not.toHaveTextContent("when we launch");
    expect(within(cards[1]).queryByTestId("planned-price-pro")).not.toBeInTheDocument();
    expect(cards[2]).toHaveTextContent("$30");
    expect(cards[2]).toHaveTextContent("when we launch");
    // Agency has no checkout even when billing is on.
    const agency = within(plans).getByTestId("plan-agency");
    expect(within(agency).queryByRole("button")).not.toBeInTheDocument();
    expect(within(agency).getByRole("link", { name: "Contact us" })).toBeInTheDocument();
  });

  it("C-149: a billing_unavailable answer to checkout says paid plans aren't available", async () => {
    const user = userEvent.setup();
    setup({
      handlers: {
        "POST /v1/w/:wid/billing/checkout": () => problem(503, "billing_unavailable", "Paid plans aren't available yet."),
      },
    });
    const current = await screen.findByRole("region", { name: "Free" });
    await user.click(within(current).getByRole("button", { name: "Start 7-day trial" }));
    expect(await within(current).findByRole("alert")).toHaveTextContent("Paid plans aren't available yet.");
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

  it("Creator: renewal date and price; Manage billing opens the portal in a new tab", async () => {
    const user = userEvent.setup();
    const tab = { go: vi.fn(), cancel: vi.fn() };
    vi.spyOn(browser, "openPending").mockReturnValue(tab);
    setup({ billing: pro });
    const current = await screen.findByRole("region", { name: "Creator" });
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
    const current = await screen.findByRole("region", { name: "Creator" });
    await user.click(within(current).getByRole("button", { name: "Cancel plan" }));
    const confirm = await screen.findByRole("alertdialog", { name: "Cancel Creator?" });
    expect(confirm).toHaveTextContent("Creator stays until 1 Nov.");
    expect(confirm).toHaveTextContent("Accounts in Auto switch to Suggest");
    expect(confirm).toHaveTextContent("Nothing is deleted.");
    expect(posts("/billing/cancel")).toHaveLength(0);
    await user.click(within(confirm).getByRole("button", { name: "Cancel plan" }));

    await waitFor(() => expect(posts("/billing/cancel")).toHaveLength(1));
    await waitFor(() => expect(current).toHaveTextContent("Creator until 1 Nov. Then the workspace moves to Free."));
    expect(current).toHaveTextContent("Cancelling");
    expect(toast.success).toHaveBeenCalledWith("Creator until 1 Nov");

    await user.click(within(current).getByRole("button", { name: "Resume Creator" }));
    const resume = await screen.findByRole("alertdialog", { name: "Resume Creator?" });
    expect(resume).toHaveTextContent("Creator renews on 1 Nov at ₹999 a month");
    await user.click(within(resume).getByRole("button", { name: "Resume Creator" }));
    await waitFor(() => expect(posts("/billing/resume")).toHaveLength(1));
    await waitFor(() => expect(current).toHaveTextContent("Renews on 1 Nov"));
  });

  it("on hold: payment failed, the grace end, and Update payment method", async () => {
    setup({ billing: billingState({ status: "on_hold", grace_until: "2026-10-03T06:00:00Z" }) });
    const current = await screen.findByRole("region", { name: "Creator" });
    expect(current).toHaveTextContent("On hold");
    expect(current).toHaveTextContent("Update your payment method by 3 Oct to keep Creator.");
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
    expect(await screen.findByText("Your Creator trial has started")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Creator" })).toHaveTextContent("Trial");
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
        await screen.findByText("Payment received? It can take a minute. We'll email you when your plan is active."),
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
  beforeEach(() => {
    nav.search = "tab=billing"; // C-171: the history is on the Billing tab
  });

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
    // The percentage rounds down, like the ring (UI-037): 2 of 3 is 66%, it read 67% before.
    expect(tiles[1]).toHaveTextContent("66%");
    expect(within(tiles[2]).getByRole("meter", { name: "WhatsApp accounts" })).toHaveAttribute(
      "aria-valuetext",
      "1 of 3 connected",
    );
  });

  it("GR-29: Facebook Pages have their own meter, with the Facebook mark", async () => {
    setup({
      billing: billingState({
        usage: [
          { metric: "instagram_accounts", used: 1, limit: 1 },
          { metric: "facebook_accounts", used: 1, limit: 3 },
        ],
      }),
    });
    const usage = await screen.findByRole("list", { name: "Usage" });
    const tiles = within(usage).getAllByRole("listitem");
    expect(tiles).toHaveLength(2);
    expect(tiles[1]).toHaveTextContent("Facebook Pages");
    expect(within(tiles[1]).getByRole("meter", { name: "Facebook Pages" })).toHaveAttribute(
      "aria-valuetext",
      "1 of 3 connected",
    );
    expect(tiles[1].querySelector(".bg-facebook-logo")).not.toBeNull();
  });
});

describe("the Usage and Billing tabs (C-171)", () => {
  it("says tax is added at checkout (C-172)", async () => {
    nav.search = "tab=billing";
    setup();
    expect(await screen.findByText(/Tax is added at checkout where it applies\./)).toBeInTheDocument();
  });

  it("?tab=billing opens Billing; Usage is the default", async () => {
    nav.search = "tab=billing";
    setup();
    expect(await screen.findByRole("tab", { name: /Billing/ })).toHaveAttribute("aria-selected", "true");
    expect(await screen.findByRole("list", { name: "Plans" })).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Usage" })).not.toBeInTheDocument();
  });

  it("marks Usage when a monthly allowance has run out, not when a slot is full", async () => {
    setup();
    await screen.findByRole("tab", { name: /Usage/ });
    // The fixture has scheduled posts used up.
    expect(screen.getByTestId("usage-ran-out")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Usage/ })).toHaveTextContent("a limit has run out");
  });
});
