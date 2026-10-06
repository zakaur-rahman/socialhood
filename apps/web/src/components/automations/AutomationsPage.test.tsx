import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/sonner";
import { handOff, resetAgentHandoff } from "@/lib/agent/handoff";
import type { Automation, AutomationTemplate, SocialAccount } from "@/lib/api/types";
import { draftCard } from "@/test/agent";
import { account, automation, billingState, json, noContent, planList, problem, renderWithApi, template, type Call } from "@/test/api";

import { AutomationsPage } from "./AutomationsPage";

const nav = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: nav.push, replace: nav.replace }),
  useParams: () => ({ slug: "maple" }),
  usePathname: () => "/w/maple/automations",
  useSearchParams: () => new URLSearchParams(),
}));

const linkDm = automation({
  id: "au1",
  name: "Comment LINK, DM the link",
  status: "active",
  display_status: "active",
  keywords: ["link", "price", "details", "shop", "buy"],
  post_scope: "selected",
  posts: [{ media_item_id: "m1" }, { media_item_id: "m2" }, { media_item_id: "m3" }],
  priority: 1,
  stats: { runs_7d: 1284, daily_7d: [100, 120, 150, 300, 250, 200, 164], last_run_at: "2026-09-28T11:48:00Z" },
  queue: { waiting: 2140, eta_minutes: 171, order: "oldest_first" },
});
const giveaway = automation({
  id: "au2",
  name: "Giveaway replies",
  status: "active",
  display_status: "scheduled",
  trigger: "comment_any",
  keywords: [],
  post_scope: "next_post",
  starts_at: "2026-10-01T04:00:00Z",
  priority: 2,
  created_at: "2026-09-21T10:00:00Z",
});
const faq = automation({
  id: "au3",
  name: "Answer FAQs",
  status: "paused",
  display_status: "paused",
  trigger: "dm_keyword",
  action: "ai_reply",
  keywords: ["shipping"],
  priority: 3,
  created_at: "2026-09-22T10:00:00Z",
});
const other = automation({ id: "au4", name: "Book a call", social_account_id: "a2", trigger: "dm_keyword", keywords: ["book"] });

const accounts = [account({ id: "a1", username: "maple.bakery" }), account({ id: "a2", username: "maple.cakes" })];

function handlers({
  items = [linkDm, giveaway, faq, other],
  accountList = accounts,
  templates = [],
  calls,
}: {
  items?: Automation[];
  accountList?: SocialAccount[];
  templates?: AutomationTemplate[];
  calls?: (call: Call) => void;
} = {}) {
  const record = (response: Response) => (call: Call) => {
    calls?.(call);
    return response.clone();
  };
  return {
    "GET /v1/w/:wid/automations/summary": () =>
      json({ active: 2, runs_7d: 1284, dms_sent_7d: 1240, waiting: 2140, longest_eta_minutes: 171 }),
    "GET /v1/w/:wid/automations": () => json({ items, next_cursor: null }),
    "GET /v1/w/:wid/automation-templates": () => json({ items: templates }),
    "GET /v1/w/:wid/social-accounts": () => json({ items: accountList }),
    "PUT /v1/w/:wid/automations/priorities": record(noContent()),
    "POST /v1/w/:wid/automations/pause": record(noContent()),
    "POST /v1/w/:wid/automations/:id/activate": (call: Call, p: Record<string, string>) => {
      calls?.(call);
      if (p.id === "au3") {
        return new Response(
          JSON.stringify({
            type: "about:blank",
            title: "validation_error",
            status: 422,
            code: "validation_error",
            errors: [{ field: "ai_instructions", message: "Add instructions for the AI." }],
          }),
          { status: 422, headers: { "Content-Type": "application/problem+json" } },
        );
      }
      return json({ ...items.find((item) => item.id === p.id), status: "active", display_status: "active" });
    },
    "POST /v1/w/:wid/automations/:id/pause": (call: Call, p: Record<string, string>) => {
      calls?.(call);
      return json({ ...items.find((item) => item.id === p.id), status: "paused", display_status: "paused" });
    },
    "DELETE /v1/w/:wid/automations/:id": record(noContent()),
    "POST /v1/w/:wid/automations/:id/duplicate": record(problem(500, "internal")),
  };
}

function row(name: string): HTMLElement {
  return screen.getByRole("link", { name }).closest("li") as HTMLElement;
}

beforeEach(() => {
  nav.push.mockReset();
  nav.replace.mockReset();
});

describe("AutomationsPage (UX-SCR-02)", () => {
  it("shows the 7-day figures and rows grouped by account", async () => {
    renderWithApi(<AutomationsPage />, { handlers: handlers() });
    await screen.findByRole("link", { name: "Comment LINK, DM the link" });

    const figures = screen.getByRole("region", { name: "Last 7 days" });
    expect(within(figures).getByText("1,284")).toBeInTheDocument();
    expect(within(figures).getByText("1,240")).toBeInTheDocument();
    expect(within(figures).getByText("All sent in about 3 h")).toBeInTheDocument();

    const groups = screen.getAllByRole("region").filter((region) => region.querySelector("h2"));
    expect(groups.map((group) => group.querySelector("h2")?.textContent)).toEqual(["@maple.bakery3", "@maple.cakes1"]);
  });

  it("renders a row: switch, trigger, three chips and +n, action, runs with the trend, last run and queue", async () => {
    renderWithApi(<AutomationsPage />, { handlers: handlers() });
    await screen.findByRole("link", { name: "Comment LINK, DM the link" });
    const link = row("Comment LINK, DM the link");

    expect(within(link).getByRole("switch", { name: "Active: Comment LINK, DM the link" })).toBeChecked();
    expect(within(link).getByText("Comment on 3 posts")).toBeInTheDocument();
    expect(within(link).getByText("Keywords: link, price, details, shop, buy")).toBeInTheDocument();
    const chips = within(link).getByTestId("keyword-chips");
    expect([...chips.querySelectorAll("[aria-hidden]")].map((chip) => chip.textContent)).toEqual([
      "link",
      "price",
      "details",
      "+2",
    ]);
    expect(within(link).getByText("Message + link")).toBeInTheDocument();
    expect(within(link).getByText(/1,284 runs/).closest("p")).toHaveTextContent("1,284 runs in 7 days");
    expect(within(link).getByTestId("trend-line")).toBeInTheDocument();
    expect(within(link).getByText("2,140 waiting · about 3 h")).toBeInTheDocument();

    const scheduled = row("Giveaway replies");
    expect(within(scheduled).getByText("Any comment on next post")).toBeInTheDocument();
    expect(within(scheduled).getByText("Starts 1 Oct")).toBeInTheDocument();
    expect(within(row("Answer FAQs")).getByText("AI reply")).toBeInTheDocument();
    expect(within(row("Answer FAQs")).getByRole("switch")).not.toBeChecked();
    expect(screen.getByRole("link", { name: "Answer FAQs" })).toHaveAttribute("href", "/w/maple/automations/au3");
  });

  it("switches automations on and off", async () => {
    const user = userEvent.setup();
    const calls: string[] = [];
    renderWithApi(<AutomationsPage />, { handlers: handlers({ calls: (call) => calls.push(`${call.method} ${call.path}`) }) });
    await screen.findByRole("link", { name: "Comment LINK, DM the link" });

    await user.click(screen.getByRole("switch", { name: "Active: Comment LINK, DM the link" }));
    await waitFor(() => expect(screen.getByRole("switch", { name: "Active: Comment LINK, DM the link" })).not.toBeChecked());
    expect(calls).toContain("POST /v1/w/w1/automations/au1/pause");

    // One that isn't ready stays off (FR-AUT-02).
    await user.click(screen.getByRole("switch", { name: "Active: Answer FAQs" }));
    await waitFor(() => expect(calls).toContain("POST /v1/w/w1/automations/au3/activate"));
    expect(screen.getByRole("switch", { name: "Active: Answer FAQs" })).not.toBeChecked();
  });

  it("changes priority with the keyboard (FR-AUT-15)", async () => {
    const user = userEvent.setup();
    const bodies: unknown[] = [];
    renderWithApi(<AutomationsPage />, {
      handlers: handlers({ calls: (call) => (call.path.endsWith("/priorities") ? bodies.push(call.body) : undefined) }),
    });
    await screen.findByRole("link", { name: "Answer FAQs" });

    const handle = screen.getByRole("button", { name: "Reorder Answer FAQs" });
    handle.focus();
    await user.keyboard("{ArrowUp}");

    await waitFor(() => expect(bodies).toHaveLength(1));
    expect(bodies[0]).toEqual({ social_account_id: "a1", ordered_ids: ["au1", "au3", "au2"] });
    // The rows move at once and the move is announced.
    const names = within(row("Comment LINK, DM the link").closest("ul") as HTMLElement)
      .getAllByRole("link")
      .map((link) => link.textContent);
    expect(names).toEqual(["Comment LINK, DM the link", "Answer FAQs", "Giveaway replies"]);
    expect(screen.getByText("Moved Answer FAQs to position 2 of 3.")).toBeInTheDocument();
    expect(handle).toHaveFocus();

    // The same from the row menu.
    await user.click(screen.getByRole("button", { name: "More actions for Comment LINK, DM the link" }));
    await user.click(await screen.findByRole("menuitem", { name: "Move down" }));
    await waitFor(() => expect(bodies).toHaveLength(2));
    expect(bodies[1]).toEqual({ social_account_id: "a1", ordered_ids: ["au3", "au1", "au2"] });
  });

  it("hides reordering while a filter narrows the list", async () => {
    const user = userEvent.setup();
    renderWithApi(<AutomationsPage />, { handlers: handlers() });
    await screen.findByRole("link", { name: "Answer FAQs" });
    expect(screen.getByRole("button", { name: "Reorder Answer FAQs" })).toBeInTheDocument();
    await user.type(screen.getByRole("searchbox", { name: "Search automations" }), "faq");
    expect(await screen.findByText("Clear the search and filters to change the order.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Answer FAQs" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reorder Answer FAQs" })).not.toBeInTheDocument();
  });

  it("pauses several at once", async () => {
    const user = userEvent.setup();
    const bodies: unknown[] = [];
    renderWithApi(<AutomationsPage />, {
      handlers: handlers({ calls: (call) => (call.path === "/v1/w/w1/automations/pause" ? bodies.push(call.body) : undefined) }),
    });
    await screen.findByRole("link", { name: "Answer FAQs" });

    await user.click(screen.getByRole("checkbox", { name: "Select Comment LINK, DM the link" }));
    await user.click(screen.getByRole("checkbox", { name: "Select Giveaway replies" }));
    const bar = screen.getByRole("region", { name: "Selected automations" });
    expect(bar).toHaveTextContent("2 selected");
    await user.click(within(bar).getByRole("button", { name: "Pause" }));

    await waitFor(() => expect(bodies).toEqual([{ ids: ["au1", "au2"] }]));
    await waitFor(() => expect(screen.queryByRole("region", { name: "Selected automations" })).not.toBeInTheDocument());
  });

  it("deletes after confirming", async () => {
    const user = userEvent.setup();
    const calls: string[] = [];
    renderWithApi(<AutomationsPage />, { handlers: handlers({ calls: (call) => calls.push(`${call.method} ${call.path}`) }) });
    await screen.findByRole("link", { name: "Book a call" });

    await user.click(screen.getByRole("button", { name: "More actions for Book a call" }));
    await user.click(await screen.findByRole("menuitem", { name: "Delete" }));
    const dialog = await screen.findByRole("alertdialog", { name: "Delete Book a call?" });
    expect(calls).not.toContain("DELETE /v1/w/w1/automations/au4");
    await user.click(within(dialog).getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(calls).toContain("DELETE /v1/w/w1/automations/au4"));
    await waitFor(() => expect(screen.queryByRole("link", { name: "Book a call" })).not.toBeInTheDocument());
  });

  it("empty: three template cards and Browse all templates", async () => {
    const user = userEvent.setup();
    const templates = [
      template({ key: "t1", name: "Send a link to commenters" }),
      template({ key: "t2", name: "Giveaway replies", trigger: "comment_any" }),
      template({ key: "t3", name: "Price on request", action: "ai_reply", category: "sell" }),
      template({ key: "t4", name: "Catalogue by DM", trigger: "dm_keyword", category: "sell" }),
    ];
    renderWithApi(<AutomationsPage />, { handlers: handlers({ items: [], templates }) });

    expect(await screen.findByText("Reply automatically")).toBeInTheDocument();
    const cards = await screen.findAllByRole("article");
    expect(cards.map((card) => card.querySelector("h3")?.textContent)).toEqual([
      "Send a link to commenters",
      "Giveaway replies",
      "Price on request",
    ]);
    const browse = screen.getByRole("button", { name: "Browse all templates" });
    browse.focus();
    await user.keyboard("{Enter}");
    const dialog = await screen.findByRole("dialog", { name: "New automation" });
    expect(within(dialog).getByRole("article", { name: "Catalogue by DM" })).toBeInTheDocument();
    // Esc puts focus back on what opened it (UX-A11Y-02).
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(browse).toHaveFocus());
  });

  it("New automation opens the gallery; Esc puts focus back on it, and the next opening starts fresh", async () => {
    const user = userEvent.setup();
    const templates = [template({ key: "t1", name: "Send a link to commenters" }), template({ key: "t4", name: "Catalogue by DM", category: "sell" })];
    renderWithApi(<AutomationsPage />, { handlers: handlers({ templates }) });
    await screen.findByRole("link", { name: "Comment LINK, DM the link" });

    const newAutomation = screen.getByRole("button", { name: "New automation" });
    newAutomation.focus();
    await user.keyboard("{Enter}");
    const dialog = await screen.findByRole("dialog", { name: "New automation" });
    const categories = within(dialog).getByRole("group", { name: "Categories" });
    await user.click(within(categories).getAllByRole("button").find((button) => button.textContent !== "All")!);
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(newAutomation).toHaveFocus());
    expect(nav.replace).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "New automation" }));
    const again = await screen.findByRole("dialog", { name: "New automation" });
    expect(within(again).getByRole("button", { name: "All" })).toHaveAttribute("aria-pressed", "true");
  });

  it("shows skeleton rows while loading", () => {
    renderWithApi(<AutomationsPage />, {
      handlers: { ...handlers(), "GET /v1/w/:wid/automations": () => new Promise<Response>(() => {}) },
    });
    expect(screen.getByLabelText("Loading automations")).toHaveAttribute("aria-busy", "true");
  });
});

describe("A failed action says so once (UI-024, C-051)", () => {
  /** The page with the app's Toaster and upgrade dialog, and Duplicate answering `duplicate`. */
  async function duplicateBookACall(duplicate: () => Response) {
    const user = userEvent.setup();
    toast.dismiss(); // the earlier tests' toasts, which sonner would replay to this Toaster
    renderWithApi(
      <>
        <AutomationsPage />
        <Toaster />
      </>,
      {
        upgradeDialog: true,
        handlers: {
          ...handlers(),
          "POST /v1/w/:wid/automations/:id/duplicate": duplicate,
          "GET /v1/w/:wid/billing": () => json(billingState({ plan: "free", status: "free" })),
          "GET /v1/billing/plans": () => json(planList()),
        },
      },
    );
    await screen.findByRole("link", { name: "Book a call" });
    await user.click(screen.getByRole("button", { name: "More actions for Book a call" }));
    await user.click(await screen.findByRole("menuitem", { name: "Duplicate" }));
  }
  const toasts = () => document.querySelectorAll("[data-sonner-toast]");

  it("a plan limit (402) is the upgrade dialog's alone: no toast", async () => {
    await duplicateBookACall(() =>
      problem(402, "quota_exceeded", "Your plan includes 3 active automations.", { entitlement: "active_automations", limit: 3 }),
    );
    expect(await screen.findByRole("dialog", { name: "Automation limit reached" })).toBeInTheDocument();
    // Sonner adds a toast on a timer after the call: give it the time it would take.
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(toasts()).toHaveLength(0);
  });

  it("any other failure is an error toast", async () => {
    await duplicateBookACall(() => problem(500, "internal"));
    await waitFor(() => expect(toasts()).toHaveLength(1));
    expect(toasts()[0]).toHaveAttribute("data-type", "error");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("An automation draft from Ask Social Hood (FR-AGT-03)", () => {
  beforeEach(() => resetAgentHandoff());

  function draftHandlers(onCall: (call: Call) => void) {
    const created = automation({
      id: "au9",
      name: "Price DM",
      status: "draft",
      display_status: "draft",
      trigger: null,
      keywords: [],
      action: null,
      message_text: null,
      public_reply_texts: [],
    });
    return {
      ...handlers(),
      "POST /v1/w/:wid/automations": (call: Call) => {
        onCall(call);
        return json(created, 201);
      },
      "PUT /v1/w/:wid/automations/:id": (call: Call) => {
        onCall(call);
        return json({ ...created, ...(call.body as object) });
      },
    };
  }

  it("shows what was prepared instead of the gallery; Open in editor creates the draft, fills it and opens it", async () => {
    const user = userEvent.setup();
    const seen: Call[] = [];
    handOff(draftCard());
    renderWithApi(<AutomationsPage openGallery />, { handlers: draftHandlers((call) => seen.push(call)) });

    const dialog = await screen.findByRole("dialog", { name: "Automation from Ask Social Hood" });
    expect(screen.queryByRole("dialog", { name: "New automation" })).toBeNull();
    const details = within(dialog).getByTestId("agent-draft");
    expect(details).toHaveTextContent("Price DM");
    await waitFor(() => expect(details).toHaveTextContent("@maple.bakery"));
    expect(details).toHaveTextContent("DM keyword");
    expect(details).toHaveTextContent("price, cost");
    expect(details).toHaveTextContent("Hi {first_name|there}! Our price list is here.");
    // Nothing is created until the member confirms.
    expect(seen).toHaveLength(0);

    await user.click(within(dialog).getByRole("button", { name: "Open in editor" }));
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/w/maple/automations/au9?focus=first"));
    expect(seen.map((call) => `${call.method} ${call.path}`)).toEqual([
      "POST /v1/w/w1/automations",
      "PUT /v1/w/w1/automations/au9",
    ]);
    expect(seen[0].body).toEqual({ name: "Price DM", social_account_id: "a1", template_key: null });
    expect(seen[1].body).toMatchObject({
      name: "Price DM",
      trigger: "dm_keyword",
      keywords: ["price", "cost"],
      action: "send_message",
      message_text: "Hi {first_name|there}! Our price list is here.",
    });
  });

  it("asks which account when the draft names none and there are several; Cancel leaves it", async () => {
    const user = userEvent.setup();
    const seen: Call[] = [];
    handOff(draftCard({ prefill: { ...draftCard().prefill, social_account_id: null } }));
    renderWithApi(<AutomationsPage openGallery />, { handlers: draftHandlers((call) => seen.push(call)) });

    const dialog = await screen.findByRole("dialog", { name: "Automation from Ask Social Hood" });
    const open = within(dialog).getByRole("button", { name: "Open in editor" });
    const cakes = await within(dialog).findByRole("radio", { name: "@maple.cakes" });
    expect(open).toBeDisabled();
    await user.click(cakes);
    expect(open).toBeEnabled();
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(seen).toHaveLength(0);
    expect(nav.replace).toHaveBeenCalledWith("/w/maple/automations");
  });
});
