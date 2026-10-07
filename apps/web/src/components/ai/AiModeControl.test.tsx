import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Conversation } from "@/lib/api/types";
import { browser } from "@/lib/billing/browser";
import {
  account,
  aiSettings,
  billingState,
  conversation,
  json,
  planList,
  problem,
  renderWithApi,
  workspace,
  type Call,
} from "@/test/api";

import { AiModeMenu } from "./AiModeControl";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

const now = new Date("2026-09-28T12:00:00Z");

const freeBilling = billingState({
  plan: "free",
  status: "free",
  trial_eligible: true,
  entitlements: [{ key: "ai_modes", value: ["off", "suggest"] }],
});

function setup(
  detail: Partial<Conversation> = {},
  { patch, billing = billingState() }: { patch?: (call: Call) => Response; billing?: ReturnType<typeof billingState> } = {},
) {
  const conv = conversation(detail);
  const view = renderWithApi(
    <AiModeMenu conversation={conv} now={now} />,
    {
      handlers: {
        "GET /v1/w/:wid/social-accounts": () => json({ items: [account({ ai_mode: "suggest" })] }),
        "GET /v1/w/:wid/billing": () => json(billing),
        "GET /v1/billing/plans": () => json(planList()),
        "POST /v1/w/:wid/billing/checkout": () => json({ checkout_url: "https://checkout.dodo.test/s/1", trial: true }),
        "GET /v1/w/:wid/ai-settings": () =>
          json(aiSettings({ escalation_phrases: ["lawyer", "cancel my order"], takeover_minutes: 30 })),
        "PATCH /v1/w/:wid/conversations/:id": (call) =>
          patch ? patch(call) : json({ ...conv, ...(call.body as object) }),
      },
      upgradeDialog: true,
    },
  );
  const patches = () => view.calls.filter((c) => c.method === "PATCH").map((c) => c.body);
  return { ...view, patches };
}

async function openMenu() {
  await userEvent.click(await screen.findByRole("button", { name: "AI mode: Suggest. Change" }));
  return screen.findByRole("menu");
}

beforeEach(() => {
  toast.success.mockReset();
  toast.error.mockReset();
});

describe("AI mode in the thread header (FR-SUG-01, UX-INB-05)", () => {
  it("lists the account default and each mode; Off saves an override", async () => {
    const { patches } = setup();
    const menu = await openMenu();
    await waitFor(() => expect(within(menu).getByRole("menuitemradio", { name: "Account default · Suggest" })).toBeInTheDocument());
    expect(within(menu).getByRole("menuitemradio", { name: "Account default · Suggest" })).toHaveAttribute("aria-checked", "true");
    await userEvent.click(within(menu).getByRole("menuitemradio", { name: "Off" }));
    await waitFor(() => expect(patches()).toHaveLength(1));
    expect(patches()[0]).toMatchObject({ ai_mode_override: "off", clear_ai_mode_override: false });
  });

  it("Auto asks first, listing the escalation rules, the owner's phrases and the takeover period", async () => {
    const user = userEvent.setup();
    const { patches } = setup();
    const menu = await openMenu();
    await user.click(within(menu).getByRole("menuitemradio", { name: "Auto" }));

    const dialog = await screen.findByRole("alertdialog", { name: "Turn on Auto for this conversation?" });
    const rules = within(dialog).getByRole("list", { name: "Escalation rules" });
    expect(within(rules).getByText("The customer asks for a refund")).toBeInTheDocument();
    expect(within(rules).getByText("The answer isn't in your knowledge")).toBeInTheDocument();
    expect(await within(rules).findByText("A message has one of your escalation phrases: “lawyer”, “cancel my order”")).toBeInTheDocument();
    expect(within(dialog).getByText(/Auto pauses in that conversation for 30 minutes/)).toBeInTheDocument();
    expect(patches()).toHaveLength(0);

    await user.click(within(dialog).getByRole("button", { name: "Turn on Auto" }));
    await waitFor(() => expect(patches()).toHaveLength(1));
    expect(patches()[0]).toMatchObject({ ai_mode_override: "auto" });
  });

  it("a 402 from the API opens the upgrade dialog, not a toast", async () => {
    const user = userEvent.setup();
    setup({}, {
      patch: () => problem(402, "entitlement_required", "Auto mode is part of Pro.", { entitlement: "ai_modes", limit: null }),
    });
    const menu = await openMenu();
    await user.click(within(menu).getByRole("menuitemradio", { name: "Auto" }));
    await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Turn on Auto" }));

    const upgrade = await screen.findByRole("dialog", { name: "Auto mode is part of Pro" });
    // Already on a paid plan: the owner is sent to billing rather than a second checkout.
    expect(within(upgrade).getByRole("link", { name: "View billing" })).toHaveAttribute("href", "/w/maple/settings/billing");
    expect(toast.error).not.toHaveBeenCalled();
  });

  it("on a plan without Auto: a Pro badge, and choosing it offers the trial instead of saving", async () => {
    const user = userEvent.setup();
    const assign = vi.spyOn(browser, "assign").mockImplementation(() => {});
    const { patches, calls } = setup({}, { billing: freeBilling });
    const menu = await openMenu();
    const auto = await within(menu).findByRole("menuitemradio", { name: "Auto Pro" });
    await user.click(auto);
    const upgrade = await screen.findByRole("dialog", { name: "Auto mode is part of Pro" });
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(patches()).toHaveLength(0);
    // Straight to checkout (F-15).
    await user.click(await within(upgrade).findByRole("button", { name: "Start 7-day trial" }));
    await waitFor(() => expect(assign).toHaveBeenCalledWith("https://checkout.dodo.test/s/1"));
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ plan: "pro" });
    assign.mockRestore();
  });

  it("Account default clears the override", async () => {
    const user = userEvent.setup();
    const { patches } = setup({ ai: { effective_mode: "off", override: "off", paused_until: null } });
    await user.click(await screen.findByRole("button", { name: "AI mode: Off. Change" }));
    const menu = await screen.findByRole("menu");
    await user.click(await within(menu).findByRole("menuitemradio", { name: "Account default · Suggest" }));
    await waitFor(() => expect(patches()).toHaveLength(1));
    expect(patches()[0]).toMatchObject({ clear_ai_mode_override: true });
  });

  it("AI paused: Resume ends the takeover", async () => {
    const user = userEvent.setup();
    const { patches } = setup({
      ai: { effective_mode: "auto", override: null, paused_until: "2026-09-28T13:40:00Z" },
    });
    expect(screen.getByText("AI paused")).toBeInTheDocument();
    // In a narrow thread header only Resume shows; it still says what is paused.
    expect(screen.getByRole("button", { name: "Resume" })).toHaveAccessibleDescription("AI paused");
    await user.click(screen.getByRole("button", { name: "Resume" }));
    await waitFor(() => expect(patches()).toHaveLength(1));
    expect(patches()[0]).toMatchObject({ resume_ai: true });
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("AI resumed"));
  });

  it("a pause means nothing outside Auto, so the mode shows", async () => {
    setup({ ai: { effective_mode: "suggest", override: null, paused_until: "2026-09-28T13:40:00Z" } });
    expect(await screen.findByRole("button", { name: "AI mode: Suggest. Change" })).toBeInTheDocument();
    expect(screen.queryByText("AI paused")).not.toBeInTheDocument();
  });
});

describe("the one AI mode control (C-063)", () => {
  // UI-030: the trigger is the Button primitive (28 px, 40 px on coarse pointers) in the AI pill's
  // colours; the menu is non-modal by default now, so the page isn't made inert behind it.
  it("is a Button in the AI pill's colours, and its menu leaves the page usable", async () => {
    const user = userEvent.setup();
    setup();
    const trigger = await screen.findByRole("button", { name: "AI mode: Suggest. Change" });
    // The menu trigger's data-slot replaces the Button's; its variant and size stay.
    expect(trigger).toHaveAttribute("data-variant", "ghost");
    expect(trigger).toHaveAttribute("data-size", "sm");
    expect(trigger).toHaveClass("bg-brand-soft", "text-brand-fg", "border-brand-line", "pointer-coarse:min-h-10");
    await user.click(trigger);
    await screen.findByRole("menu");
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    // A modal menu would hide the rest of the page from screen readers (aria-hidden on its ancestors).
    expect(trigger.closest("[aria-hidden]")).toBeNull();
  });

  it("says what the default is", async () => {
    setup();
    const trigger = await screen.findByRole("button", { name: "AI mode: Suggest. Change" });
    await waitFor(() =>
      expect(trigger).toHaveAttribute("title", "Account default · Suggest. Change it for this conversation"),
    );
  });

  it("agents can change it too (members may set a conversation's mode)", async () => {
    const user = userEvent.setup();
    const conv = conversation();
    const view = renderWithApi(<AiModeMenu conversation={conv} now={now} />, {
      ws: { ...workspace, role: "agent" },
      handlers: {
        "GET /v1/w/:wid/social-accounts": () => json({ items: [account()] }),
        "GET /v1/w/:wid/billing": () => json(billingState()),
        "PATCH /v1/w/:wid/conversations/:id": (call) => json({ ...conv, ...(call.body as object) }),
      },
    });
    await user.click(await screen.findByRole("button", { name: "AI mode: Suggest. Change" }));
    await user.click(await screen.findByRole("menuitemradio", { name: "Off" }));
    await waitFor(() => expect(view.calls.some((c) => c.method === "PATCH")).toBe(true));
    expect(view.calls.some((c) => c.path.endsWith("/ai-settings"))).toBe(false);
  });
});
