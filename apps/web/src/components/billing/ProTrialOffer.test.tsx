import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { billingState, json, planList, renderWithApi, workspace } from "@/test/api";

import { ProTrialOffer } from "./ProTrialOffer";

const search = vi.hoisted(() => ({ value: "" }));
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(search.value) }));

const free = billingState({
  plan: "free",
  status: "free",
  trial_eligible: true,
  billing_available: true,
  prices: [{ plan: "pro", amount_minor: 99_900, currency: "INR", interval: "month" }],
});

function setup(role: "owner" | "admin" | "agent" = "owner", billing = free) {
  return renderWithApi(<ProTrialOffer />, {
    ws: { ...workspace, role, plan: billing.plan },
    upgradeDialog: true,
    handlers: {
      "GET /v1/w/:wid/billing": () => json(billing),
      "GET /v1/billing/plans": () => json(planList()),
    },
  });
}

beforeEach(() => {
  window.history.replaceState(null, "", "/w/maple/home?plan=pro");
});
afterEach(() => {
  search.value = "";
});

describe("?plan=pro from the pricing page (UI-ISS-073)", () => {
  it("offers the trial once to the owner of a Free workspace, and drops the parameter", async () => {
    search.value = "plan=pro";
    setup();
    const dialog = await screen.findByRole("dialog", { name: "Upgrade to Pro" });
    expect(await within(dialog).findByRole("button", { name: "Start 7-day trial" })).toBeInTheDocument();
    await waitFor(() => expect(window.location.search).toBe(""));
  });

  it("does nothing without the parameter or for another plan", async () => {
    search.value = "plan=max";
    const { calls } = setup();
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(calls.some((call) => call.path.endsWith("/billing"))).toBe(false);
  });

  it("does not offer it on a paid plan, but still drops the parameter", async () => {
    search.value = "plan=pro";
    setup("owner", billingState());
    await waitFor(() => expect(window.location.search).toBe(""));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("C-149: does not offer it while paid plans aren't on sale", async () => {
    search.value = "plan=pro";
    setup("owner", { ...free, billing_available: false, prices: [] });
    await waitFor(() => expect(window.location.search).toBe(""));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("does not offer it to an admin, who cannot pay", async () => {
    search.value = "plan=pro";
    setup("admin");
    await waitFor(() => expect(window.location.search).toBe(""));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
