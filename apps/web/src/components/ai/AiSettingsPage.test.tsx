import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { AiSettings, SocialAccount } from "@/lib/api/types";
import { account, aiSettings, billingState, json, planList, problem, renderWithApi, workspace, type Call } from "@/test/api";

import { AiSettingsPage } from "./AiSettingsPage";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

const accounts = [
  account({ id: "a1", username: "maple.bakery", ai_mode: "suggest" }),
  account({ id: "a2", platform: "whatsapp", username: null, display_name: "Maple Orders", ai_mode: "off" }),
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

  it("on Free, Auto carries a Pro badge and opens the upgrade dialog; a 402 does the same", async () => {
    const user = userEvent.setup();
    const { patches } = setup({
      billing: billingState({ plan: "free", status: "free", entitlements: [{ key: "ai_modes", value: ["off", "suggest"] }] }),
    });
    const instagram = await screen.findByRole("radiogroup", { name: "@maple.bakery" });
    await user.click(await within(instagram).findByRole("radio", { name: "Auto Pro" }));
    expect(await screen.findByRole("dialog", { name: "Auto mode is part of Pro" })).toBeInTheDocument();
    expect(patches()).toEqual([]);
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
    await user.type(screen.getByRole("textbox", { name: "Add to Escalation phrases" }), "cancel my order{Enter}");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(calls.some((c) => c.method === "PUT")).toBe(true));
    expect(calls.find((c) => c.method === "PUT")?.body).toMatchObject({
      takeover_minutes: 0,
      escalation_phrases: ["lawyer", "cancel my order"],
      business_description: "Linen dresses.",
      tone: "friendly",
    });
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("AI settings saved"));
  });

  it("agents see the modes read-only and no settings (the API keeps them to admins)", async () => {
    const { calls } = setup({ role: "agent" });
    const instagram = await screen.findByRole("radiogroup", { name: "@maple.bakery" });
    expect(within(instagram).getByRole("radio", { name: "Off" })).toBeDisabled();
    expect(screen.getByText("Only owners and admins can change AI settings.")).toBeInTheDocument();
    expect(calls.some((c) => c.path.endsWith("/ai-settings"))).toBe(false);
  });
});
