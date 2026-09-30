import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { AiSettings, SocialAccount } from "@/lib/api/types";
import { account, aiSettings, billingState, json, planList, problem, renderWithApi, workspace, type Call } from "@/test/api";

import { AiSettingsPage } from "./AiSettingsPage";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));
vi.mock("next/navigation", () => ({ usePathname: () => "/w/maple/settings/ai" }));

const accounts = [
  account({ id: "a1", username: "maple.bakery", ai_mode: "suggest" }),
  account({ id: "a2", platform: "whatsapp", username: null, display_name: "Maple Orders", ai_mode: "off" }),
  account({ id: "a3", username: "old.maple", ai_mode: "suggest", status: "disconnected" }),
];

function setup({
  role = "owner",
  billing = billingState(),
  patch,
}: {
  role?: "owner" | "admin" | "agent";
  billing?: ReturnType<typeof billingState>;
  patch?: (call: Call) => Response;
} = {}) {
  let settings: AiSettings = aiSettings({ escalation_phrases: ["lawyer"], business_description: "Linen dresses." });
  const view = renderWithApi(<AiSettingsPage />, {
    ws: { ...workspace, role, plan: billing.plan },
    handlers: {
      "GET /v1/w/:wid/social-accounts": () => json({ items: accounts }),
      "GET /v1/w/:wid/billing": () => json(billing),
      "GET /v1/w/:wid/ai-settings": () => json(settings),
      "PUT /v1/w/:wid/ai-settings": (call) => {
        settings = { ...(call.body as AiSettings), updated_at: "2026-09-28T12:00:00Z" };
        return json(settings);
      },
      "PATCH /v1/w/:wid/social-accounts/:id": (call, p) =>
        patch
          ? patch(call)
          : json({ ...(accounts.find((a) => a.id === p.id) as SocialAccount), ...(call.body as object) }),
      "GET /v1/billing/plans": () => json(planList()),
    },
    upgradeDialog: true,
  });
  const patches = () => view.calls.filter((c) => c.method === "PATCH").map((c) => ({ path: c.path, body: c.body }));
  return { ...view, patches };
}

beforeEach(() => {
  toast.success.mockReset();
  toast.error.mockReset();
});

describe("Settings → AI (UX-SCR-07, T5.5)", () => {
  it("each account's mode; Off and Suggest save at once", async () => {
    const user = userEvent.setup();
    const { patches } = setup();
    const instagram = await screen.findByRole("radiogroup", { name: "@maple.bakery" });
    expect(within(instagram).getByRole("radio", { name: "Suggest" })).toHaveAttribute("aria-checked", "true");
    expect(within(screen.getByRole("radiogroup", { name: "Maple Orders" })).getByRole("radio", { name: "Off" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await user.click(within(instagram).getByRole("radio", { name: "Off" }));
    await waitFor(() => expect(patches()).toEqual([{ path: "/v1/w/w1/social-accounts/a1", body: { ai_mode: "off" } }]));
  });

  it("Auto asks first, listing the escalation rules", async () => {
    const user = userEvent.setup();
    const { patches } = setup();
    const instagram = await screen.findByRole("radiogroup", { name: "@maple.bakery" });
    await user.click(within(instagram).getByRole("radio", { name: "Auto" }));
    const dialog = await screen.findByRole("alertdialog", { name: "Turn on Auto for @maple.bakery?" });
    expect(within(dialog).getByText("The customer asks for a refund")).toBeInTheDocument();
    expect(patches()).toEqual([]);
    await user.click(within(dialog).getByRole("button", { name: "Turn on Auto" }));
    await waitFor(() => expect(patches()).toEqual([{ path: "/v1/w/w1/social-accounts/a1", body: { ai_mode: "auto" } }]));
  });

  it("on Free, Auto is disabled with a Pro badge on every account, and the hint opens the upgrade dialog", async () => {
    const user = userEvent.setup();
    const { patches } = setup({
      billing: billingState({ plan: "free", status: "free", entitlements: [{ key: "ai_modes", value: ["off", "suggest"] }] }),
    });
    const instagram = await screen.findByRole("radiogroup", { name: "@maple.bakery" });
    const auto = await within(instagram).findByRole("radio", { name: "Auto Pro" });
    expect(auto).toBeDisabled();
    expect(within(screen.getByRole("radiogroup", { name: "Maple Orders" })).getByRole("radio", { name: "Auto Pro" })).toBeDisabled();
    // Off and Suggest still work on Free.
    expect(within(instagram).getByRole("radio", { name: "Off" })).toBeEnabled();
    expect(screen.getByText("Auto is part of Pro.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Upgrade for Auto" }));
    expect(await screen.findByRole("dialog", { name: "Auto mode is part of Pro" })).toBeInTheDocument();
    expect(patches()).toEqual([]);
  });

  it("lists every connected account with Off, Suggest and Auto (C-066)", async () => {
    setup();
    const list = await screen.findByRole("list", { name: "AI mode per account" });
    const rows = within(list).getAllByRole("radiogroup");
    expect(rows.map((row) => row.getAttribute("aria-labelledby"))).toEqual(["ai-mode-label-a1", "ai-mode-label-a2"]);
    for (const row of rows) {
      expect(within(row).getAllByRole("radio").map((radio) => radio.textContent)).toEqual(["Off", "Suggest", "Auto"]);
    }
    expect(within(list).getByText("WhatsApp Cloud API")).toBeInTheDocument();
    // A disconnected account has no AI mode to choose.
    expect(screen.queryByRole("radiogroup", { name: "@old.maple" })).toBeNull();
    expect(screen.getByText("2 connected")).toBeInTheDocument();
    expect(screen.queryByText("Auto is part of Pro.")).toBeNull();
  });

  it("a 402 from the API opens the upgrade dialog", async () => {
    const user = userEvent.setup();
    setup({ patch: () => problem(402, "entitlement_required", "Auto mode is part of Pro.") });
    const instagram = await screen.findByRole("radiogroup", { name: "@maple.bakery" });
    await user.click(within(instagram).getByRole("radio", { name: "Auto" }));
    await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Turn on Auto" }));
    // A 402 from before C-049 carries only its detail; the dialog still knows what it is about.
    expect(await screen.findByRole("dialog", { name: "Auto mode is part of Pro" })).toBeInTheDocument();
    expect(toast.error).not.toHaveBeenCalled();
  });

  it("takeover period and escalation phrases save with the rest of the settings", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    const takeover = await screen.findByRole("radiogroup", { name: "Human takeover" });
    expect(within(takeover).getByRole("radio", { name: "2 h" })).toHaveAttribute("aria-checked", "true");
    await user.click(within(takeover).getByRole("radio", { name: "Until resumed" }));

    const builtIn = screen.getByRole("list", { name: "Built-in escalation rules" });
    expect(within(builtIn).getAllByRole("listitem")).toHaveLength(6);
    expect(screen.getByText("1 of 20 used")).toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: "Add to Your escalation phrases" }), "cancel my order{Enter}");
    expect(screen.getByText("2 of 20 used")).toBeInTheDocument();
    const bar = screen.getByRole("region", { name: "Save changes" });
    expect(within(bar).getByRole("status")).toHaveTextContent("Unsaved changes");
    await user.click(within(bar).getByRole("button", { name: "Save" }));

    await waitFor(() => expect(calls.some((c) => c.method === "PUT")).toBe(true));
    expect(calls.find((c) => c.method === "PUT")?.body).toMatchObject({
      takeover_minutes: 0,
      escalation_phrases: ["lawyer", "cancel my order"],
      business_description: "Linen dresses.",
      tone: "friendly",
    });
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("AI settings saved"));
    await waitFor(() => expect(within(bar).getByRole("status")).toHaveTextContent("All changes saved"));
  });

  it("phrases are removable chips; Add skips a duplicate; Reset undoes (C-066)", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    const field = await screen.findByRole("textbox", { name: "Add to Your escalation phrases" });
    await user.type(field, "LAWYER");
    await user.click(screen.getByRole("button", { name: "Add" }));
    expect(screen.getByText("That one is already in the list.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Remove lawyer" }));
    expect(screen.getByText("0 of 20 used")).toBeInTheDocument();
    const bar = screen.getByRole("region", { name: "Save changes" });
    await user.click(within(bar).getByRole("button", { name: "Reset" }));
    expect(screen.getByRole("button", { name: "Remove lawyer" })).toBeInTheDocument();
    expect(within(bar).getByRole("status")).toHaveTextContent("All changes saved");
    expect(calls.some((c) => c.method === "PUT")).toBe(false);
  });

  it("agents see the modes read-only and no settings (the API keeps them to admins)", async () => {
    const { calls } = setup({ role: "agent" });
    const instagram = await screen.findByRole("radiogroup", { name: "@maple.bakery" });
    expect(within(instagram).getByRole("radio", { name: "Off" })).toBeDisabled();
    expect(screen.getByText("Only owners and admins can change AI settings.")).toBeInTheDocument();
    expect(calls.some((c) => c.path.endsWith("/ai-settings"))).toBe(false);
  });
});
