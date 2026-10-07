import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { SocialAccount } from "@/lib/api/types";
import { account, automation, json, renderWithApi, template, workspace, type Call } from "@/test/api";

import { TemplateGallery } from "./TemplateGallery";

const nav = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: nav.push, replace: vi.fn() }),
}));

const templates = [
  template({ key: "link_to_commenters", name: "Send a link to commenters", category: "grow" }),
  template({ key: "giveaway", name: "Giveaway replies", category: "grow", trigger: "comment_any", icon: "gift" }),
  template({
    key: "price_on_request",
    name: "Price on request",
    category: "sell",
    action: "ai_reply",
    requires_paid_plan: true,
    icon: "tag",
  }),
  template({ key: "faqs", name: "Answer FAQs", category: "support", trigger: "dm_keyword", action: "ai_reply" }),
];

function renderGallery(accounts: SocialAccount[], plan: "free" | "pro" = "pro") {
  const bodies: unknown[] = [];
  const view = renderWithApi(
    <TemplateGallery
      open
      onOpenChange={() => {}}
      templates={templates}
      templatesLoading={false}
      accounts={accounts}
      plan={plan}
    />,
    {
      ws: { ...workspace, plan },
      handlers: {
        "POST /v1/w/:wid/automations": (call: Call) => {
          bodies.push(call.body);
          return json(automation({ id: "new1" }), 201);
        },
      },
    },
  );
  return { ...view, bodies };
}

function cardNames() {
  return screen.getAllByRole("article").map((card) => card.querySelector("h3")?.textContent);
}

beforeEach(() => nav.push.mockReset());

describe("TemplateGallery (UX-SCR-11)", () => {
  it("filters by category and keeps Start from blank last", async () => {
    const user = userEvent.setup();
    renderGallery([account()]);
    const dialog = screen.getByRole("dialog", { name: "New automation" });
    expect(cardNames()).toEqual(["Send a link to commenters", "Giveaway replies", "Price on request", "Answer FAQs"]);
    const items = within(dialog).getAllByRole("listitem");
    expect(items[items.length - 1]).toHaveTextContent("Start from blank");

    // The categories are filter chips (ToggleGroup, one choice): a radio group.
    const categories = within(dialog).getByRole("radiogroup", { name: "Categories" });
    expect(within(categories).getByRole("radio", { name: "All" })).toBeChecked();
    await user.click(within(categories).getByRole("radio", { name: "Sell" }));
    expect(within(categories).getByRole("radio", { name: "Sell" })).toBeChecked();
    expect(within(categories).getByRole("radio", { name: "All" })).not.toBeChecked();
    expect(cardNames()).toEqual(["Price on request"]);
    expect(within(dialog).getByRole("button", { name: "Start from blank" })).toBeInTheDocument();
  });

  it("shows the card's trigger and action, and Pro on Free for paid templates", () => {
    renderGallery([account()], "free");
    const card = screen.getByRole("article", { name: "Price on request" });
    expect(card).toHaveTextContent("Comment keyword");
    expect(card).toHaveTextContent("AI reply");
    expect(within(card).getByText("Pro")).toBeInTheDocument();
    expect(within(screen.getByRole("article", { name: "Send a link to commenters" })).queryByText("Pro")).toBeNull();
  });

  it("with one account: creates the draft from the template and opens the editor on the first incomplete step", async () => {
    const user = userEvent.setup();
    const { bodies } = renderGallery([account({ id: "a1" })]);
    await user.click(screen.getByRole("button", { name: "Use template: Send a link to commenters" }));
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/w/maple/automations/new1?focus=first"));
    expect(bodies).toEqual([{ template_key: "link_to_commenters", social_account_id: "a1" }]);
  });

  it("with several accounts: asks which one first", async () => {
    const user = userEvent.setup();
    const { bodies } = renderGallery([
      account({ id: "a1", username: "maple.bakery" }),
      account({ id: "a2", username: "maple.cakes" }),
    ]);
    await user.click(screen.getByRole("button", { name: "Use template: Giveaway replies" }));
    const dialog = await screen.findByRole("dialog", { name: "Which account?" });
    expect(bodies).toEqual([]);
    await user.click(within(dialog).getByRole("radio", { name: /maple\.cakes/ }));
    await user.click(within(dialog).getByRole("button", { name: "Use template" }));
    await waitFor(() => expect(bodies).toEqual([{ template_key: "giveaway", social_account_id: "a2" }]));
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/w/maple/automations/new1?focus=first"));
  });

  it("Start from blank creates an untitled draft", async () => {
    const user = userEvent.setup();
    const { bodies } = renderGallery([account({ id: "a1" })]);
    await user.click(screen.getByRole("button", { name: "Start from blank" }));
    await waitFor(() => expect(bodies).toEqual([{ name: "Untitled automation", social_account_id: "a1" }]));
  });
});
