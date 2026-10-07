import { useMutation, useQuery } from "@tanstack/react-query";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useApi, useUpgradeDialog } from "@/lib/api/provider";
import { unwrap } from "@/lib/api/queries";
import type { BillingState } from "@/lib/api/types";
import { browser } from "@/lib/billing/browser";
import { billingState, json, planList, problem, renderWithApi, workspace } from "@/test/api";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

const freeBilling = billingState({
  plan: "free",
  status: "free",
  trial_eligible: true,
  prices: [{ plan: "pro", amount_minor: 99_900, currency: "INR", interval: "month" }],
  entitlements: [
    { key: "active_automations", value: 3 },
    { key: "ai_modes", value: ["off", "suggest"] },
  ],
  usage: [{ metric: "ai_credits", used: 200, limit: 200, period_end: "2026-10-01" }],
});

/** Any gated action: here, activating an automation. */
function Activate({ opt_out = false }: { opt_out?: boolean }) {
  const api = useApi();
  const activate = useMutation({
    mutationFn: () =>
      unwrap(api.POST("/v1/w/{wid}/automations/{automation_id}/activate", { params: { path: { wid: "w1", automation_id: "au1" } } })),
    meta: opt_out ? { upgradeDialog: false } : undefined,
  });
  return (
    <button type="button" onClick={() => activate.mutate()}>
      Activate
    </button>
  );
}

function setup({
  billing = freeBilling,
  role = "owner",
  gate = () =>
    problem(402, "quota_exceeded", "Your plan includes 3 active automations.", { entitlement: "active_automations", limit: 3 }),
  checkout = () => json({ checkout_url: "https://checkout.dodo.test/s/1", trial: true }),
  ui = <Activate />,
}: {
  billing?: BillingState;
  role?: "owner" | "admin" | "agent";
  gate?: () => Response;
  checkout?: () => Response;
  ui?: React.ReactElement;
} = {}) {
  return renderWithApi(ui, {
    ws: { ...workspace, role, plan: billing.plan },
    upgradeDialog: true,
    handlers: {
      "GET /v1/w/:wid/billing": () => json(billing),
      "GET /v1/billing/plans": () => json(planList()),
      "POST /v1/w/:wid/automations/:id/activate": gate,
      "POST /v1/w/:wid/billing/checkout": checkout,
    },
  });
}

afterEach(() => vi.restoreAllMocks());

describe("UpgradeDialog: every 402 opens it (F-15, T8.4)", () => {
  it("names the limit, what Pro includes and its price, and starts the trial straight away", async () => {
    const user = userEvent.setup();
    const assign = vi.spyOn(browser, "assign").mockImplementation(() => {});
    const { calls } = setup();
    await user.click(screen.getByRole("button", { name: "Activate" }));

    const dialog = await screen.findByRole("dialog", { name: "Automation limit reached" });
    expect(dialog).toHaveTextContent("Free includes 3 active automations.");
    expect(await within(dialog).findByText("Pro includes 50 active automations.")).toBeInTheDocument();
    expect(dialog).toHaveTextContent("Try Pro free for 7 days, then ₹999 a month. Cancel anytime.");
    expect(within(dialog).getByRole("link", { name: "Compare plans" })).toHaveAttribute("href", "/w/maple/settings/billing");

    await user.click(within(dialog).getByRole("button", { name: "Start 7-day trial" }));
    await waitFor(() => expect(assign).toHaveBeenCalledWith("https://checkout.dodo.test/s/1"));
    expect(calls.find((c) => c.path.endsWith("/billing/checkout"))?.body).toEqual({ plan: "pro" });
    // Nothing is granted here: the plan changes when Dodo's webhook arrives.
    expect(within(dialog).getByRole("button", { name: "Start 7-day trial" })).toBeDisabled();
  });

  it("without a trial it offers Upgrade to Pro", async () => {
    const user = userEvent.setup();
    setup({ billing: { ...freeBilling, trial_eligible: false } });
    await user.click(screen.getByRole("button", { name: "Activate" }));
    const dialog = await screen.findByRole("dialog", { name: "Automation limit reached" });
    expect(within(dialog).getByRole("button", { name: "Upgrade to Pro" })).toBeInTheDocument();
    expect(dialog).toHaveTextContent("Pro is ₹999 a month.");
  });

  it("AI credits: the limit and the reset date", async () => {
    const user = userEvent.setup();
    setup({
      gate: () =>
        problem(402, "quota_exceeded", "Your AI credits for this period are used up.", {
          entitlement: "ai_credits_monthly",
          limit: 200,
        }),
    });
    await user.click(screen.getByRole("button", { name: "Activate" }));
    const dialog = await screen.findByRole("dialog", { name: "AI credits used up" });
    expect(dialog).toHaveTextContent("You've used all 200 AI credits for this month. They reset on 1 Oct.");
    expect(dialog).toHaveTextContent("Pro includes 5,000 AI credits a month.");
  });

  it("a checkout refused with 409 says why, and the dialog stays", async () => {
    const user = userEvent.setup();
    const assign = vi.spyOn(browser, "assign").mockImplementation(() => {});
    setup({ checkout: () => problem(409, "conflict", "Already on a paid plan") });
    await user.click(screen.getByRole("button", { name: "Activate" }));
    const dialog = await screen.findByRole("dialog", { name: "Automation limit reached" });
    await user.click(within(dialog).getByRole("button", { name: "Start 7-day trial" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "This workspace already has a paid plan. Change it from Manage billing.",
    );
    expect(assign).not.toHaveBeenCalled();
  });

  it("admins can't pay (owner only, §2.15): the billing page and who can", async () => {
    const user = userEvent.setup();
    setup({ role: "admin" });
    await user.click(screen.getByRole("button", { name: "Activate" }));
    const dialog = await screen.findByRole("dialog", { name: "Automation limit reached" });
    expect(dialog).toHaveTextContent("Only the workspace owner can change the plan.");
    expect(within(dialog).getByRole("link", { name: "See plans" })).toHaveAttribute("href", "/w/maple/settings/billing");
    expect(within(dialog).queryByRole("button", { name: /trial|Upgrade/ })).not.toBeInTheDocument();
  });

  it("agents are told to ask an owner, with no upgrade action", async () => {
    const user = userEvent.setup();
    setup({ role: "agent" });
    await user.click(screen.getByRole("button", { name: "Activate" }));
    const dialog = await screen.findByRole("dialog", { name: "Automation limit reached" });
    expect(dialog).toHaveTextContent("Ask an owner of this workspace to upgrade.");
    expect(within(dialog).queryByRole("link")).not.toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Not now" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("on a paid plan the owner goes to billing instead of a second checkout", async () => {
    const user = userEvent.setup();
    setup({ billing: billingState() });
    await user.click(screen.getByRole("button", { name: "Activate" }));
    const dialog = await screen.findByRole("dialog", { name: "Automation limit reached" });
    expect(dialog).toHaveTextContent("Pro includes 3 active automations.");
    expect(within(dialog).getByRole("link", { name: "View billing" })).toBeInTheDocument();
  });

  it("the same 402 right after Not now doesn't reopen it (no loops)", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    await user.click(screen.getByRole("button", { name: "Activate" }));
    await user.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Not now" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Activate" }));
    await waitFor(() => expect(calls.filter((c) => c.path.endsWith("/activate"))).toHaveLength(2));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("Esc gives focus back to what had it, though no trigger opened it (UX-A11Y-02)", async () => {
    const user = userEvent.setup();
    setup();
    const activate = screen.getByRole("button", { name: "Activate" });
    await user.click(activate);
    const dialog = await screen.findByRole("dialog");
    await waitFor(() => expect(dialog).toContainElement(document.activeElement as HTMLElement));
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(activate).toHaveFocus();
  });

  it("other errors don't open it, and a mutation can opt out", async () => {
    const user = userEvent.setup();
    const first = setup({ gate: () => problem(409, "conflict", "Busy") });
    await user.click(screen.getByRole("button", { name: "Activate" }));
    await waitFor(() => expect(first.calls.some((c) => c.path.endsWith("/activate"))).toBe(true));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    first.unmount();

    const second = setup({ ui: <Activate opt_out /> });
    await user.click(screen.getByRole("button", { name: "Activate" }));
    await waitFor(() => expect(second.calls.some((c) => c.path.endsWith("/activate"))).toBe(true));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("a 402 from a query opens it too, and screens can open it themselves", async () => {
    function Gated() {
      const api = useApi();
      useQuery({
        queryKey: ["gated"],
        queryFn: () => unwrap(api.GET("/v1/w/{wid}/billing", { params: { path: { wid: "gated" } } })),
      });
      return null;
    }
    function Opener() {
      const upgrade = useUpgradeDialog();
      return (
        <button type="button" onClick={() => upgrade.open({ code: "entitlement_required", entitlement: "ai_modes" })}>
          Open
        </button>
      );
    }
    const user = userEvent.setup();
    renderWithApi(
      <>
        <Gated />
        <Opener />
      </>,
      {
        upgradeDialog: true,
        handlers: {
          "GET /v1/w/:wid/billing": (_call, p) =>
            p.wid === "gated"
              ? problem(402, "entitlement_required", "Comment insights is part of Pro.")
              : json(freeBilling),
          "GET /v1/billing/plans": () => json(planList()),
        },
      },
    );
    expect(await screen.findByRole("dialog", { name: "Comment insights is part of Pro" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Not now" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Open" }));
    expect(await screen.findByRole("dialog", { name: "Auto mode is part of Pro" })).toBeInTheDocument();
  });
});
