import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { account, automation, billingState, json, planList, problem, renderWithApi, template, type Call } from "@/test/api";

import { AutomationSection } from "./AutomationSection";

const nav = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: nav.push, replace: vi.fn() }) }));

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

const maple = account({ id: "a1", username: "maple.bakery", capabilities: ["publish"] });
const studio = account({ id: "a2", username: "maple.studio", capabilities: ["publish"] });

function renderSection({ beforeCreate = async () => true, create }: { beforeCreate?: () => Promise<boolean>; create?: () => Response } = {}) {
  const created: Call[] = [];
  renderWithApi(
    <AutomationSection wid="w1" slug="maple" postId="sp1" linked={[]} accounts={[maple, studio]} plan="pro" readOnly={false} beforeCreate={beforeCreate} />,
    {
      handlers: {
        "GET /v1/w/:wid/automation-templates": () => json({ items: [template()] }),
        "POST /v1/w/:wid/automations": (call) => {
          created.push(call);
          return create ? create() : json(automation({ id: "au5", trigger: null, keywords: [] }), 201);
        },
        "PUT /v1/w/:wid/automations/:id": () => json(automation({ id: "au5" })),
        "GET /v1/w/:wid/billing": () => json(billingState({ plan: "free", status: "free" })),
        "GET /v1/billing/plans": () => json(planList()),
      },
      upgradeDialog: true,
    },
  );
  return { created };
}

beforeEach(() => {
  nav.push.mockReset();
  toast.error.mockReset();
});

describe("AutomationSection (FR-AUT-18)", () => {
  it("asks which account when the post has several, then starts from blank", async () => {
    const user = userEvent.setup();
    const { created } = renderSection();
    expect(screen.getByText(/Answer the first comments on this post automatically/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Add comment automation" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Start from blank" }));
    expect(within(dialog).getByRole("heading", { name: "Which account?" })).toBeInTheDocument();
    await user.click(within(dialog).getByRole("radio", { name: "@maple.studio" }));
    await user.click(within(dialog).getByRole("button", { name: "Start from blank" }));
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/w/maple/automations/au5?focus=first"));
    expect(created[0].body).toEqual({ name: "Untitled automation", social_account_id: "a2" });
  });

  it("doesn't create anything while the post's latest changes aren't saved", async () => {
    const user = userEvent.setup();
    const { created } = renderSection({ beforeCreate: async () => false });
    await user.click(screen.getByRole("button", { name: "Add comment automation" }));
    await user.click(await screen.findByRole("button", { name: "Use template: Send a link to commenters" }));
    await user.click(screen.getByRole("button", { name: "Use template" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Your changes to this post aren't saved yet. Save them first, then add the automation."));
    expect(created).toHaveLength(0);
  });

  it("shows why the automation couldn't be created", async () => {
    const user = userEvent.setup();
    renderSection({ create: () => problem(409, "conflict", "This post is publishing. Add the automation afterwards.") });
    await user.click(screen.getByRole("button", { name: "Add comment automation" }));
    await user.click(await screen.findByRole("button", { name: "Use template: Send a link to commenters" }));
    await user.click(screen.getByRole("button", { name: "Use template" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("This post is publishing. Add the automation afterwards."));
    expect(nav.push).not.toHaveBeenCalled();
  });

  it("over a plan limit (402): the upgrade dialog is the only message", async () => {
    const user = userEvent.setup();
    renderSection({
      create: () =>
        problem(402, "quota_exceeded", "Your plan includes 3 active automations.", { entitlement: "active_automations", limit: 3 }),
    });
    await user.click(screen.getByRole("button", { name: "Add comment automation" }));
    await user.click(await screen.findByRole("button", { name: "Use template: Send a link to commenters" }));
    await user.click(screen.getByRole("button", { name: "Use template" }));
    const upgrade = await screen.findByRole("dialog", { name: "Automation limit reached" });
    expect(upgrade).toHaveTextContent("Free includes 3 active automations.");
    expect(toast.error).not.toHaveBeenCalled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(nav.push).not.toHaveBeenCalled();
  });
});
