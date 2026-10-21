import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ConversationListItem, ScheduledMessage, SocialAccount } from "@/lib/api/types";
import { account, conversation, json, listItem, noContent, renderWithApi, type Call } from "@/test/api";

import { useInboxUi } from "./inbox-context";
import { InboxShell } from "./InboxShell";

const nav = vi.hoisted(() => ({ params: {} as { id?: string }, push: vi.fn(), search: "" }));
vi.mock("next/navigation", () => ({
  useParams: () => nav.params,
  useRouter: () => ({ push: nav.push, replace: vi.fn() }),
  usePathname: () => (nav.params.id ? `/w/maple/inbox/${nav.params.id}` : "/w/maple/inbox"),
  useSearchParams: () => new URLSearchParams(nav.search),
}));

const originalMatchMedia = window.matchMedia;

/** jsdom has no layout: answer min-width media queries for a given viewport width. */
function setWidth(width: number) {
  window.matchMedia = (query: string) => {
    const min = /min-width:\s*(\d+)px/.exec(query);
    return {
      matches: min ? width >= Number(min[1]) : false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    } as MediaQueryList;
  };
}

const rows = [
  listItem({ id: "c1", last_message_at: "2026-09-28T11:55:00Z" }),
  listItem({
    id: "c2",
    contact: { id: "p2", display_name: "Kabir Shah", username: "kabir", profile_picture_url: null },
    last_message_at: "2026-09-28T10:00:00Z",
  }),
];

function handlers({
  accounts = [account()],
  list = rows,
  scheduled = [],
  counts = { needs_reply: 0, needs_you: 0, unread: 0 },
  onList,
}: {
  accounts?: SocialAccount[];
  list?: ConversationListItem[];
  scheduled?: ScheduledMessage[];
  counts?: { needs_reply: number; needs_you: number; unread: number };
  onList?: (call: Call) => void;
} = {}) {
  return {
    "GET /v1/w/:wid/social-accounts": () => json({ items: accounts }),
    "GET /v1/w/:wid/conversations/counts": () => json(counts),
    "GET /v1/w/:wid/conversations": (call: Call) => {
      onList?.(call);
      const view = call.url.searchParams.get("view");
      return json({ items: view === "all" ? list : [], next_cursor: null });
    },
    "GET /v1/w/:wid/scheduled-messages": () => json({ items: scheduled, next_cursor: null }),
    "GET /v1/w/:wid/conversations/:id": (_: Call, p: Record<string, string>) => json(conversation({ id: p.id })),
    "PATCH /v1/w/:wid/conversations/:id": (call: Call, p: Record<string, string>) =>
      json(conversation({ id: p.id, ...(call.body as object) })),
    "POST /v1/w/:wid/conversations/:id/unread": () => noContent(),
  };
}

function renderShell(options: Parameters<typeof handlers>[0] = {}) {
  return renderWithApi(
    <InboxShell>
      <div>Thread pane</div>
    </InboxShell>,
    { handlers: handlers(options) },
  );
}

function pane(name: "list" | "thread" | "details"): HTMLElement | null {
  return document.querySelector(`[data-pane="${name}"]`);
}

beforeEach(() => {
  nav.params = {};
  nav.search = "";
  nav.push.mockReset();
  window.localStorage.clear();
});
afterEach(() => {
  window.matchMedia = originalMatchMedia;
});

describe("InboxShell layout at the four widths (UX-INB-01)", () => {
  it("≥ 1280 px: list 320, thread, details 300 inline", async () => {
    setWidth(1440);
    nav.params = { id: "c1" };
    renderShell();
    await screen.findByText("Kabir Shah");
    // UI-078: the list and details are resizable here, 320 px until someone drags them.
    expect(pane("list")).toHaveClass("w-(--pane-w)");
    expect(pane("list")?.style.getPropertyValue("--pane-w")).toBe("320px");
    expect(pane("thread")).toHaveTextContent("Thread pane");
    expect(pane("details")).toHaveClass("w-(--pane-w)");
    expect(pane("details")?.style.getPropertyValue("--pane-w")).toBe("320px");
    expect(pane("details")?.tagName).toBe("ASIDE");
    const strip = screen.getByRole("radiogroup", { name: "Platform" });
    expect(within(strip).getByRole("radio", { name: "All" })).toHaveTextContent("All");
  });

  it("1024–1279 px: list 320 and thread; details wait for the sheet", async () => {
    setWidth(1100);
    nav.params = { id: "c1" };
    renderShell();
    await screen.findByText("Kabir Shah");
    expect(pane("list")).toHaveClass("w-(--pane-w)");
    expect(pane("list")?.style.getPropertyValue("--pane-w")).toBe("320px");
    expect(pane("thread")).toBeInTheDocument();
    expect(pane("details")).toBeNull();
    // The segmented platform control is labelled at every width (C-063).
    const strip = screen.getByRole("radiogroup", { name: "Platform" });
    expect(within(strip).getByRole("radio", { name: "All" })).toHaveTextContent("All");
  });

  it("768–1023 px: list 300 and thread", async () => {
    setWidth(900);
    nav.params = { id: "c1" };
    renderShell();
    await screen.findByText("Kabir Shah");
    expect(pane("list")).toHaveClass("w-[300px]");
    expect(pane("thread")).toBeInTheDocument();
    expect(pane("details")).toBeNull();
    // Not resizable on tablets: no handle.
    expect(screen.queryByRole("separator", { name: "Resize the conversation list" })).toBeNull();
  });

  it("from 1024 px the list resizes with its handle, and the width is remembered (UI-078)", async () => {
    setWidth(1100);
    renderShell();
    await screen.findByText("Kabir Shah");
    const handle = screen.getByRole("separator", { name: "Resize the conversation list" });
    handle.focus();
    fireEvent.keyDown(handle, { key: "ArrowRight" });
    expect(pane("list")?.style.getPropertyValue("--pane-w")).toBe("336px");
    expect(window.localStorage.getItem("socialhood:pane-width:inbox-list")).toBe("336");
    window.localStorage.removeItem("socialhood:pane-width:inbox-list");
  });

  it("< 768 px: one pane at a time", async () => {
    setWidth(390);
    const view = renderShell();
    await screen.findByText("Kabir Shah");
    expect(pane("list")).toHaveClass("w-full");
    expect(pane("thread")).toBeNull();

    nav.params = { id: "c1" };
    view.rerender(
      <InboxShell>
        <div>Thread pane</div>
      </InboxShell>,
    );
    expect(pane("list")).toBeNull();
    expect(pane("thread")).toHaveTextContent("Thread pane");
  });

  it("rows link to their conversation and mark the open one", async () => {
    setWidth(1440);
    nav.params = { id: "c2" };
    renderShell();
    const kabir = await screen.findByRole("link", { name: /Kabir Shah/ });
    expect(kabir).toHaveAttribute("href", "/w/maple/inbox/c2");
    expect(kabir).toHaveAttribute("aria-current", "page");
  });
});

describe("the context panel's width threshold (C-063)", () => {
  it("≥ 1440 px: starts open", async () => {
    setWidth(1500);
    nav.params = { id: "c1" };
    renderShell();
    await screen.findByText("Kabir Shah");
    expect(pane("details")).not.toBeNull();
  });

  it("1280–1439 px: starts collapsed", async () => {
    setWidth(1300);
    nav.params = { id: "c1" };
    renderShell();
    await screen.findByText("Kabir Shah");
    expect(pane("details")).toBeNull();
  });

  it("the remembered choice wins at either width", async () => {
    window.localStorage.setItem("socialhood:inbox-details", "1");
    setWidth(1300);
    nav.params = { id: "c1" };
    const view = renderShell();
    await screen.findByText("Kabir Shah");
    expect(pane("details")).not.toBeNull();
    view.unmount();

    window.localStorage.setItem("socialhood:inbox-details", "0");
    setWidth(1500);
    renderShell();
    await screen.findByText("Kabir Shah");
    expect(pane("details")).toBeNull();
  });
});

describe("InboxShell list states (§4.7)", () => {
  beforeEach(() => setWidth(1440));

  it("no accounts: Connect an account", async () => {
    renderShell({ accounts: [account({ status: "disconnected" })] });
    const link = await screen.findByRole("link", { name: "Connect an account" });
    expect(link).toHaveAttribute("href", "/w/maple/settings/connections");
    expect(screen.getByText("Messages from Instagram and WhatsApp will appear here.")).toBeInTheDocument();
  });

  it("no conversations yet", async () => {
    renderShell({ list: [] });
    expect(await screen.findByText("No conversations yet")).toBeInTheDocument();
    expect(screen.getByText("New messages appear here as they arrive.")).toBeInTheDocument();
  });

  it("filter empty: All caught up, with Show all", async () => {
    const user = userEvent.setup();
    const views: (string | null)[] = [];
    renderShell({ onList: (call) => views.push(call.url.searchParams.get("view")) });
    await screen.findByText("Kabir Shah");
    await user.click(screen.getByRole("radio", { name: "Unread" }));
    expect(await screen.findByText("All caught up")).toBeInTheDocument();
    expect(screen.getByText('Nothing matches "Unread" right now.')).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Show all" }));
    expect(await screen.findByText("Kabir Shah")).toBeInTheDocument();
    expect(views).toEqual(["all", "unread"]);
  });

  it("Needs you and Archived are plain chips; there is no More menu (D-15 item 4)", async () => {
    const user = userEvent.setup();
    const views: (string | null)[] = [];
    renderShell({ onList: (call) => views.push(call.url.searchParams.get("view")) });
    await screen.findByText("Kabir Shah");
    expect(screen.queryByRole("button", { name: /More views/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: "Needs you" }));
    expect(await screen.findByText('Nothing matches "Needs you" right now.')).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: "Archived" }));
    expect(await screen.findByText('Nothing matches "Archived" right now.')).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Archived" })).toHaveAttribute("aria-checked", "true");
    expect(views).toEqual(["all", "needs_you", "archived"]);
  });

  // UI-052: the counts query, on the two chips that mean "waiting on someone".
  it("Needs reply and Needs you carry their counts in the name; the other chips don't", async () => {
    renderShell({ counts: { needs_reply: 3, needs_you: 120, unread: 9 } });
    await screen.findByText("Kabir Shah");
    const reply = await screen.findByRole("radio", { name: "Needs reply, 3" });
    expect(within(reply).getByTestId("count-needs_reply")).toHaveTextContent("3");
    expect(screen.getByRole("radio", { name: "Needs you, 99+" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Unread" })).toBeInTheDocument();
  });

  it("a zero count shows no badge", async () => {
    renderShell();
    await screen.findByText("Kabir Shah");
    expect(screen.getByRole("radio", { name: "Needs reply" })).toBeInTheDocument();
    expect(screen.queryByTestId("count-needs_reply")).not.toBeInTheDocument();
  });

  it("a chip writes the view to the address; All takes it out", async () => {
    const user = userEvent.setup();
    renderShell();
    await screen.findByText("Kabir Shah");
    await user.click(screen.getByRole("radio", { name: "Unread" }));
    expect(nav.push).toHaveBeenLastCalledWith("/w/maple/inbox?view=unread", { scroll: false });
    await user.click(within(screen.getByRole("radiogroup", { name: "Views" })).getByRole("radio", { name: "All" }));
    expect(nav.push).toHaveBeenLastCalledWith("/w/maple/inbox", { scroll: false });
  });

  it("the view follows the address when it changes (Back, or Home's link with the inbox mounted)", async () => {
    const views: (string | null)[] = [];
    const shell = renderShell({ onList: (call) => views.push(call.url.searchParams.get("view")) });
    await screen.findByText("Kabir Shah");
    nav.search = "view=needs_reply";
    shell.rerender(
      <InboxShell>
        <div>Thread pane</div>
      </InboxShell>,
    );
    expect(await screen.findByRole("radio", { name: "Needs reply" })).toHaveAttribute("aria-checked", "true");
    expect(views).toContain("needs_reply");
    nav.search = "";
    shell.rerender(
      <InboxShell>
        <div>Thread pane</div>
      </InboxShell>,
    );
    const chips = screen.getByRole("radiogroup", { name: "Views" });
    await waitFor(() => expect(within(chips).getByRole("radio", { name: "All" })).toHaveAttribute("aria-checked", "true"));
  });

  it("opening a conversation keeps the list's filters in the address, rows included", async () => {
    setWidth(1440);
    const user = userEvent.setup();
    nav.search = "platform=instagram";
    renderShell();
    const row = await screen.findByRole("link", { name: /Kabir Shah/ });
    expect(row).toHaveAttribute("href", "/w/maple/inbox/c2?platform=instagram");
    await user.keyboard("j");
    expect(nav.push).toHaveBeenLastCalledWith("/w/maple/inbox/c1?platform=instagram");
  });

  it("opens on the view in the link (Home's Needs reply tile)", async () => {
    nav.search = "view=needs_reply";
    const views: (string | null)[] = [];
    renderShell({ onList: (call) => views.push(call.url.searchParams.get("view")) });
    expect(await screen.findByText('Nothing matches "Needs reply" right now.')).toBeInTheDocument();
    expect(views).toEqual(["needs_reply"]);
    expect(screen.getByRole("radio", { name: "Needs reply" })).toHaveAttribute("aria-checked", "true");
  });

  // UI-030: Chats | Scheduled is the Tabs primitive (sm), with the count badge of UX-SH-01.
  it("Chats and Scheduled are tabs that swap the list; the Scheduled tab names its count", async () => {
    const user = userEvent.setup();
    const message: ScheduledMessage = {
      id: "s1",
      conversation_id: "c1",
      text: "Following up on the Aria dress",
      attachment_asset_ids: [],
      send_at: "2026-09-28T13:00:00Z",
      status: "scheduled",
      error: null,
      contact: { display_name: "Priya Nair", username: "priya.styles", profile_picture_url: null },
      platform: "instagram",
    };
    renderShell({ scheduled: [message, { ...message, id: "s2" }] });
    await screen.findByText("Kabir Shah");
    const tabs = screen.getByRole("tablist", { name: "Inbox sections" });
    expect(tabs).toHaveAttribute("data-size", "sm");
    expect(within(tabs).getByRole("tab", { name: "Chats" })).toHaveAttribute("aria-selected", "true");
    const scheduledTab = await within(tabs).findByRole("tab", { name: "Scheduled, 2 to send" });
    const count = within(scheduledTab).getByTestId("scheduled-count");
    expect(count).toHaveTextContent("2");
    expect(count).toHaveAttribute("data-tone", "count");
    expect(count).toHaveAttribute("data-size", "md");
    expect(screen.getByRole("tabpanel", { name: "Chats" })).toContainElement(screen.getByRole("list", { name: "Conversations" }));

    await user.click(scheduledTab);
    expect(scheduledTab).toHaveAttribute("aria-selected", "true");
    const panel = screen.getByRole("tabpanel", { name: "Scheduled, 2 to send" });
    expect(await within(panel).findByRole("list", { name: "Scheduled messages" })).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Conversations" })).not.toBeInTheDocument();
    // The search and view chips belong to Chats.
    expect(screen.queryByRole("searchbox", { name: "Search conversations" })).not.toBeInTheDocument();
  });

  it("without scheduled messages the tab has no count", async () => {
    renderShell();
    await screen.findByText("Kabir Shah");
    expect(screen.getByRole("tab", { name: "Scheduled" })).toBeInTheDocument();
    expect(screen.queryByTestId("scheduled-count")).not.toBeInTheDocument();
  });

  it("searches on the server after a pause", async () => {
    const user = userEvent.setup();
    const queries: (string | null)[] = [];
    renderShell({ onList: (call) => queries.push(call.url.searchParams.get("q")) });
    await screen.findByText("Kabir Shah");
    await user.type(screen.getByRole("searchbox", { name: "Search conversations" }), "dubai");
    await waitFor(() => expect(queries).toContain("dubai"));
    expect(queries.filter((q) => q && q !== "dubai")).toEqual([]); // debounced: no request per keystroke
  });

  it("remembers the platform per workspace", async () => {
    const user = userEvent.setup();
    const platforms: (string | null)[] = [];
    renderShell({
      accounts: [account(), account({ id: "a2", platform: "whatsapp", username: null, phone_number: "+91 98765 43210" })],
      onList: (call) => platforms.push(call.url.searchParams.get("platform")),
    });
    await screen.findByText("Kabir Shah");
    await user.click(screen.getByRole("radio", { name: "WhatsApp" }));
    await waitFor(() => expect(platforms).toContain("whatsapp"));
    expect(window.localStorage.getItem("socialhood:inbox-platform:w1")).toBe("whatsapp");
  });

  it("the platform is in the address, and the address wins over the remembered one", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem("socialhood:inbox-platform:w1", "instagram");
    nav.search = "platform=whatsapp";
    const platforms: (string | null)[] = [];
    renderShell({
      accounts: [account(), account({ id: "a2", platform: "whatsapp", username: null, phone_number: "+91 98765 43210" })],
      onList: (call) => platforms.push(call.url.searchParams.get("platform")),
    });
    await screen.findByRole("radiogroup", { name: "Platform" });
    await waitFor(() => expect(platforms).toContain("whatsapp"));
    expect(platforms).not.toContain("instagram");
    await user.click(within(screen.getByRole("radiogroup", { name: "Platform" })).getByRole("radio", { name: "All" }));
    expect(nav.push).toHaveBeenLastCalledWith("/w/maple/inbox?platform=all", { scroll: false });
  });

  // UI-052 (UI-ISS-078): the Scheduled tab honours the platform filter; the account filter can't apply
  // (a scheduled message carries no account), so it isn't offered there.
  it("the Scheduled tab shows only the chosen platform's messages, with its count", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem("socialhood:inbox-platform:w1", "all"); // an earlier test's choice stays in memory
    const base: ScheduledMessage = {
      id: "s1",
      conversation_id: "c1",
      text: "Following up on the Aria dress",
      attachment_asset_ids: [],
      send_at: "2026-09-28T13:00:00Z",
      status: "scheduled",
      error: null,
      contact: { display_name: "Priya Nair", username: "priya.styles", profile_picture_url: null },
      platform: "instagram",
    };
    const whatsapp: ScheduledMessage = {
      ...base,
      id: "s2",
      platform: "whatsapp",
      contact: { display_name: "Kabir Shah", username: null, profile_picture_url: null },
    };
    renderShell({
      accounts: [account(), account({ id: "a2", platform: "whatsapp", username: null, phone_number: "+91 98765 43210" })],
      scheduled: [base, whatsapp],
    });
    await screen.findByText("Kabir Shah");
    await screen.findByRole("tab", { name: "Scheduled, 2 to send" });
    await user.click(screen.getByRole("radio", { name: "WhatsApp" }));
    const tab = await screen.findByRole("tab", { name: "Scheduled, 1 to send" });
    await user.click(tab);
    const list = await screen.findByRole("list", { name: "Scheduled messages" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(1);
    expect(within(list).getByText("Kabir Shah")).toBeInTheDocument();
    expect(screen.getByRole("radiogroup", { name: "Platform" })).toBeInTheDocument();
  });

  // UI-031: the search is the SearchInput primitive; Esc empties it before anything else.
  it("the search is a SearchInput; Esc clears it and keeps focus", async () => {
    const user = userEvent.setup();
    renderShell();
    await screen.findByText("Kabir Shah");
    const search = screen.getByRole("searchbox", { name: "Search conversations" });
    expect(search.closest('[data-slot="search-input"]')).not.toBeNull();
    expect(search).toHaveAttribute("data-size", "lg");
    await user.type(search, "dubai");
    await user.keyboard("{Escape}");
    expect(search).toHaveValue("");
    expect(search).toHaveFocus();
  });
});

// UI-031: below 1280 px the details sheet has a title row holding its close button, so the
// panel's first row (Open in Instagram) can't sit under the button.
describe("the details sheet (UX-INB-09)", () => {
  function OpenDetails() {
    const ui = useInboxUi();
    return (
      <button type="button" onClick={ui.toggleDetails}>
        Open details
      </button>
    );
  }

  it("titles the sheet and scrolls only the panel under the title row", async () => {
    const user = userEvent.setup();
    setWidth(900);
    nav.params = { id: "c1" };
    renderWithApi(
      <InboxShell>
        <OpenDetails />
      </InboxShell>,
      { handlers: handlers() },
    );
    await user.click(await screen.findByRole("button", { name: "Open details" }));
    const sheet = await screen.findByRole("dialog", { name: "Details" });
    const title = within(sheet).getByRole("heading", { name: "Details" });
    expect(title).not.toHaveClass("sr-only");
    const header = title.closest('[data-slot="sheet-header"]') as HTMLElement;
    const scroll = within(sheet).getByTestId("details-scroll");
    expect(scroll).toHaveClass("min-h-0", "flex-1", "overflow-y-auto");
    expect(sheet).not.toHaveClass("overflow-y-auto");
    const open = await within(scroll).findByRole("link", { name: /Open in Instagram/ });
    expect(header).not.toContainElement(open);
    expect(within(sheet).getByRole("button", { name: "Close" })).toBeInTheDocument();
  });
});

describe("keyboard shortcuts (FR-INB-12)", () => {
  beforeEach(() => setWidth(1440));

  it("j and k move between conversations; / focuses search", async () => {
    const user = userEvent.setup();
    const view = renderShell();
    await screen.findByText("Kabir Shah");
    await user.keyboard("j");
    expect(nav.push).toHaveBeenLastCalledWith("/w/maple/inbox/c1");

    nav.params = { id: "c1" };
    view.rerender(
      <InboxShell>
        <div>Thread pane</div>
      </InboxShell>,
    );
    await user.keyboard("j");
    expect(nav.push).toHaveBeenLastCalledWith("/w/maple/inbox/c2");
    await user.keyboard("k"); // c1 is first: nowhere to go
    expect(nav.push).toHaveBeenCalledTimes(2);

    await user.keyboard("/");
    await waitFor(() => expect(screen.getByRole("searchbox")).toHaveFocus());
    await user.keyboard("j"); // typing in search is not a shortcut
    expect(nav.push).toHaveBeenCalledTimes(2);
  });

  it("e archives the open conversation and moves on; u marks it unread", async () => {
    const user = userEvent.setup();
    nav.params = { id: "c1" };
    const { calls } = renderShell();
    await screen.findByText("Kabir Shah");
    await user.keyboard("u");
    await waitFor(() => expect(calls.some((c) => c.path === "/v1/w/w1/conversations/c1/unread")).toBe(true));

    await user.keyboard("e");
    await waitFor(() => expect(calls.some((c) => c.method === "PATCH")).toBe(true));
    const patch = calls.find((c) => c.method === "PATCH");
    expect(patch?.body).toEqual({ clear_ai_mode_override: false, resume_ai: false, status: "archived" });
    expect(nav.push).toHaveBeenLastCalledWith("/w/maple/inbox/c2");
    await waitFor(() => expect(within(pane("list")!).queryByText("Priya Nair")).not.toBeInTheDocument());
  });

  it("Esc closes the details panel", async () => {
    const user = userEvent.setup();
    nav.params = { id: "c1" };
    renderShell();
    await screen.findByText("Kabir Shah");
    expect(pane("details")).not.toBeNull();
    await user.keyboard("{Escape}");
    expect(pane("details")).toBeNull();
    // Remembered per device (C-063). Last in the file: the choice also stays in memory.
    expect(window.localStorage.getItem("socialhood:inbox-details")).toBe("0");
  });
});

// UI-053 (D-14, WCAG 2.1.4): the single-key shortcuts can be turned off, per device, from the Keyboard
// shortcuts dialog. The setting is read first from localStorage, so each test sets it explicitly (a value
// written in one test also stays in memory).
describe("single-key shortcuts switch (D-14)", () => {
  beforeEach(() => {
    setWidth(1440);
    window.localStorage.setItem("socialhood:inbox-shortcuts", "1");
    window.localStorage.setItem("socialhood:inbox-details", "1");
  });

  it("? opens the Keyboard shortcuts dialog, which lists the keys and holds the switch (on by default)", async () => {
    const user = userEvent.setup();
    renderShell();
    await screen.findByText("Kabir Shah");
    await user.keyboard("?");
    const dialog = await screen.findByRole("dialog", { name: "Keyboard shortcuts" });
    const keys = dialog.querySelectorAll("kbd");
    expect(Array.from(keys).map((key) => key.textContent)).toEqual(["j", "k", "/", "e", "u", "?", "Esc"]);
    expect(within(dialog).getByRole("switch", { name: "Single-key shortcuts" })).toBeChecked();
  });

  it("the list header's keyboard button opens it, and Esc returns focus to the button", async () => {
    const user = userEvent.setup();
    renderShell();
    await screen.findByText("Kabir Shah");
    const trigger = screen.getByRole("button", { name: "Keyboard shortcuts" });
    await user.click(trigger);
    await screen.findByRole("dialog", { name: "Keyboard shortcuts" });
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(trigger).toHaveFocus();
  });

  it("off: j, k, e, u, / and ? do nothing; the choice is saved on the device", async () => {
    const user = userEvent.setup();
    nav.params = { id: "c1" };
    const { calls } = renderShell();
    await screen.findByText("Kabir Shah");
    await user.click(screen.getByRole("button", { name: "Keyboard shortcuts" }));
    await user.click(await screen.findByRole("switch", { name: "Single-key shortcuts" }));
    expect(window.localStorage.getItem("socialhood:inbox-shortcuts")).toBe("0");
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

    await user.keyboard("jkeu/?");
    expect(nav.push).not.toHaveBeenCalled();
    expect(calls.some((c) => c.method === "PATCH" || c.path.endsWith("/unread"))).toBe(false);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("searchbox")).not.toHaveFocus();

    // Esc is not a character key: it still closes the details panel.
    expect(pane("details")).not.toBeNull();
    await user.keyboard("{Escape}");
    expect(pane("details")).toBeNull();
  });

  it("a stored off keeps them off on load; turning it back on restores them", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem("socialhood:inbox-shortcuts", "0");
    renderShell();
    await screen.findByText("Kabir Shah");
    await user.keyboard("j");
    expect(nav.push).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Keyboard shortcuts" }));
    const toggle = await screen.findByRole("switch", { name: "Single-key shortcuts" });
    expect(toggle).not.toBeChecked();
    await user.click(toggle);
    expect(window.localStorage.getItem("socialhood:inbox-shortcuts")).toBe("1");
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await user.keyboard("j");
    expect(nav.push).toHaveBeenLastCalledWith("/w/maple/inbox/c1");
  });

  it("shortcuts with a modifier are left alone", async () => {
    const user = userEvent.setup();
    renderShell();
    await screen.findByText("Kabir Shah");
    await user.keyboard("{Control>}j{/Control}");
    expect(nav.push).not.toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
