import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Calendar, ScheduledPostSummary, SocialAccount } from "@/lib/api/types";
import { rangeFor } from "@/lib/schedule/dates";
import { account, json, postDetail, problem, renderWithApi, workspace, type Call } from "@/test/api";
import { calendar, calendarMessage, detail, ist, NOW, postingSlots, scheduledPost } from "@/test/schedule";

import { SchedulePage } from "./SchedulePage";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

const nav = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: nav.push, replace: vi.fn() }),
  useParams: () => ({ slug: "maple" }),
  usePathname: () => "/w/maple/schedule",
}));

// ---- fixtures: the week of Mon 28 Sep to Sun 4 Oct 2026, now Tue 29 Sep 10:00 in Kolkata

const linen = scheduledPost({ id: "p-linen", caption: "Linen styles", publish_at: ist("2026-09-29", "12:00") });
const arrivals = scheduledPost({
  id: "p-arrivals",
  caption: "New arrivals",
  status: "published",
  publish_at: ist("2026-09-28", "09:00"),
  published_at: ist("2026-09-28", "09:00"),
  targets: [
    {
      social_account_id: "a1",
      status: "published",
      permalink: "https://www.instagram.com/p/arrivals/",
      post_id: "po1",
      platform_media_id: "17900000000000001",
    },
  ],
});
const festive = scheduledPost({
  id: "p-festive",
  caption: "Festive teaser",
  status: "failed",
  publish_at: ist("2026-09-29", "09:00"),
  targets: [{ social_account_id: "a1", status: "failed", error: { code: "platform_rejected", message: "Instagram rejected this: aspect ratio" } }],
});
const behind = scheduledPost({ id: "p-behind", caption: "Behind the scenes", status: "draft", publish_at: ist("2026-10-01", "09:00") });
const lookbook = scheduledPost({
  id: "p-lookbook",
  caption: "Lookbook",
  publish_at: ist("2026-10-04", "18:00"),
  targets: [{ social_account_id: "a2", status: "pending" }],
});
const diwali = scheduledPost({ id: "d-diwali", caption: "Diwali collection teaser", status: "draft", format: "reel", publish_at: null });
const packing = scheduledPost({ id: "d-pack", caption: "How we pack orders", status: "draft", format: null, asset_count: 0, publish_at: null });

const accounts: SocialAccount[] = [
  account({ id: "a1", username: "maple.bakery", capabilities: ["publish"] }),
  account({ id: "a2", username: "maple.cakes", capabilities: ["publish"] }),
];

function weekCalendar(overrides: Partial<Calendar> = {}): Calendar {
  return calendar({
    posts: [arrivals, festive, linen, behind, lookbook],
    messages: [calendarMessage({ id: "dm1" }), calendarMessage({ id: "dm2", contact: { display_name: "Kabir Shah" } })],
    slots: [
      { social_account_id: "a1", at: ist("2026-09-30", "18:00") },
      { social_account_id: "a1", at: ist("2026-10-02", "18:00") },
    ],
    accounts: [
      { social_account_id: "a1", published_24h: 1, publishing_limit: 50, next_free_at: ist("2026-09-30", "18:00") },
      { social_account_id: "a2", published_24h: 0, publishing_limit: 50, next_free_at: null },
    ],
    ...overrides,
  });
}

type Options = {
  cal?: (call: Call) => Calendar;
  lists?: Partial<Record<string, ScheduledPostSummary[]>>;
  reschedule?: (call: Call, id: string) => Response;
  schedule?: (call: Call, id: string) => Response;
  bulk?: (call: Call) => Response;
  role?: "owner" | "admin" | "agent";
};

/** A small stateful fake: moves and schedules change what the next calendar read returns. */
function setup({ cal, lists = {}, reschedule, schedule, bulk, role = "owner" }: Options = {}) {
  const posts = new Map([linen, arrivals, festive, behind, lookbook, diwali, packing].map((p) => [p.id, p]));
  const onCalendar = new Set([linen.id, arrivals.id, festive.id, behind.id, lookbook.id]);
  const at = (call: Call) => (call.body as { publish_at: string }).publish_at;
  const save = (post: ScheduledPostSummary) => {
    posts.set(post.id, post);
    if (post.publish_at) onCalendar.add(post.id);
    return json(detail(post));
  };
  const handlers = {
    "GET /v1/w/:wid/social-accounts": () => json({ items: accounts }),
    "GET /v1/w/:wid/calendar": (call: Call) => {
      const from = call.url.searchParams.get("from") ?? "";
      const to = call.url.searchParams.get("to") ?? "";
      if (cal) return json(cal(call));
      return json(weekCalendar({ start: from, end: to, posts: [...onCalendar].map((id) => posts.get(id)!) }));
    },
    "GET /v1/w/:wid/scheduled-posts": (call: Call) => {
      const view = call.url.searchParams.get("view") ?? "scheduled";
      const fallback: Record<string, ScheduledPostSummary[]> = {
        drafts: [diwali, packing].filter((p) => posts.get(p.id)?.status === "draft"),
        scheduled: [linen, lookbook],
        published: [arrivals],
        failed: [festive],
      };
      return json({ items: lists[view] ?? fallback[view] ?? [], next_cursor: null });
    },
    "GET /v1/w/:wid/posts/:id": () => json(postDetail()),
    "GET /v1/w/:wid/social-accounts/:id/posting-slots": (_: Call, p: Record<string, string>) =>
      json(postingSlots({ social_account_id: p.id })),
    "POST /v1/w/:wid/scheduled-posts": (call: Call) =>
      json(detail(scheduledPost({ id: "new1", status: "draft", publish_at: (call.body as { publish_at: string | null }).publish_at })), 201),
    "POST /v1/w/:wid/scheduled-posts/bulk": (call: Call) =>
      bulk ? bulk(call) : json({ updated: [], deleted_ids: (call.body as { ids: string[] }).ids, skipped: [] }),
    "POST /v1/w/:wid/scheduled-posts/:id/reschedule": (call: Call, p: Record<string, string>) =>
      reschedule ? reschedule(call, p.id) : save({ ...posts.get(p.id)!, publish_at: at(call) }),
    "POST /v1/w/:wid/scheduled-posts/:id/schedule": (call: Call, p: Record<string, string>) =>
      schedule ? schedule(call, p.id) : save({ ...posts.get(p.id)!, status: "scheduled", publish_at: at(call) }),
    "POST /v1/w/:wid/scheduled-posts/:id/queue": (_: Call, p: Record<string, string>) =>
      save({ ...posts.get(p.id)!, status: "scheduled", publish_at: ist("2026-09-30", "18:00") }),
  };
  return renderWithApi(<SchedulePage now={NOW} />, { handlers, ws: { ...workspace, role } });
}

function callsTo(calls: Call[], method: string, pattern: RegExp): Call[] {
  return calls.filter((call) => call.method === method && pattern.test(call.path));
}

// ---- layout for the pointer: jsdom has none, so each grid element gets a fixed box

const WEEK = rangeFor("week", "2026-09-29").days;
const MONTH = rangeFor("month", "2026-09-29").days;
const COLUMN_HEIGHT = 48 * 44;

function box(left: number, top: number, width: number, height: number): DOMRect {
  return { x: left, y: top, left, top, width, height, right: left + width, bottom: top + height, toJSON: () => ({}) } as DOMRect;
}

function mockLayout() {
  return vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
    if (this.dataset.testid === "week-scroller") return box(0, 0, 900, COLUMN_HEIGHT);
    if (this.dataset.day) return box(100 + WEEK.indexOf(this.dataset.day) * 100, 0, 100, COLUMN_HEIGHT);
    if (this.dataset.monthDay) {
      const i = MONTH.indexOf(this.dataset.monthDay);
      return box((i % 7) * 100, 100 + Math.floor(i / 7) * 100, 100, 100);
    }
    return box(0, 0, 0, 0);
  });
}

/** The pointer over a day and time of the Week grid. */
function weekPoint(day: string, time: string) {
  const [h, m] = time.split(":").map(Number);
  return { clientX: 100 + WEEK.indexOf(day) * 100 + 50, clientY: ((h * 60 + m) / 1440) * COLUMN_HEIGHT + 1 };
}

function monthPoint(day: string) {
  const i = MONTH.indexOf(day);
  return { clientX: (i % 7) * 100 + 50, clientY: 100 + Math.floor(i / 7) * 100 + 50 };
}

function drag(from: Element, to: { clientX: number; clientY: number }) {
  const pointer = { pointerId: 1, pointerType: "mouse", button: 0 };
  fireEvent.pointerDown(from, { ...pointer, clientX: 1, clientY: 1 });
  fireEvent.pointerMove(from, { ...pointer, ...to });
  fireEvent.pointerUp(from, { ...pointer, ...to });
}

async function card(id: string): Promise<HTMLElement> {
  await screen.findAllByRole("group", { name: "Tuesday 29 September" });
  const el = await waitFor(() => {
    const found = document.querySelector<HTMLElement>(`[data-post-id="${id}"]`);
    if (!found) throw new Error(`no card ${id}`);
    return found;
  });
  return el;
}

function day(name: string): HTMLElement {
  return screen.getByRole("group", { name });
}

const originalMatchMedia = window.matchMedia;

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

beforeEach(() => {
  window.localStorage.clear();
  // The remembered view also lives in memory for the page view (use-browser-state), so set it.
  window.localStorage.setItem("socialhood:schedule-view", "week");
  toast.mockReset();
  toast.success.mockReset();
  toast.error.mockReset();
  nav.push.mockReset();
});
afterEach(() => {
  window.matchMedia = originalMatchMedia;
  vi.restoreAllMocks();
});

describe("Schedule page: Week (UX-SCR-04, FR-PUB-08)", () => {
  it("shows the week in the workspace time zone with posts, free queue times and scheduled DMs", async () => {
    const { calls } = setup();
    expect(await screen.findByText("Times in Asia/Kolkata")).toBeInTheDocument();
    expect(screen.getByText("28 Sep – 4 Oct")).toBeInTheDocument();
    await card("p-linen");
    const [request] = callsTo(calls, "GET", /\/calendar$/);
    expect(request.url.searchParams.get("from")).toBe("2026-09-28");
    expect(request.url.searchParams.get("to")).toBe("2026-10-04");

    const tuesday = day("Tuesday 29 September");
    expect(within(tuesday).getByRole("link", { name: /^Linen styles, Scheduled, Today 12:00/ })).toBeInTheDocument();
    expect(within(tuesday).getByRole("link", { name: /^Festive teaser, Failed/ })).toBeInTheDocument();
    expect(within(tuesday).getByTestId("now-line")).toBeInTheDocument();
    expect(within(day("Monday 28 September")).getByRole("link", { name: /^New arrivals, Published/ })).toBeInTheDocument();
    // Drafts with a time are drawn on the calendar too, muted.
    const draft = within(day("Thursday 1 October")).getByRole("link", { name: /^Behind the scenes, Draft/ });
    expect(draft.closest("[data-status]")).toHaveAttribute("data-status", "draft");
    // Free posting times (FR-PUB-09) and the Messages layer.
    expect(within(day("Wednesday 30 September")).getByTestId("queue-slot")).toHaveTextContent("Queue · 18:00");
    expect(within(day("Thursday 1 October")).getByRole("button", { name: "2 scheduled DMs, 21:00" })).toBeInTheDocument();
  });

  it("hovering a published card shows its first results, and its menu links to Instagram", async () => {
    const user = userEvent.setup();
    setup();
    const link = within(await card("p-arrivals")).getByRole("link", { name: /^New arrivals, Published/ });
    await user.hover(link);
    expect((await screen.findAllByText("1,204 likes · 212 comments")).length).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: "Actions for New arrivals" }));
    expect(await screen.findByRole("menuitem", { name: "View on Instagram" })).toHaveAttribute(
      "href",
      "https://www.instagram.com/p/arrivals/",
    );
    expect(screen.getByRole("menuitem", { name: "Comments and results" })).toHaveAttribute("href", "/w/maple/comments/po1");
    expect(screen.queryByRole("menuitem", { name: "Move to…" })).not.toBeInTheDocument();
  });

  it("opens the scheduled DMs of a time, each linking to its conversation", async () => {
    const user = userEvent.setup();
    setup();
    await card("p-linen");
    await user.click(within(day("Thursday 1 October")).getByRole("button", { name: "2 scheduled DMs, 21:00" }));
    const links = await screen.findAllByRole("link", { name: /Your order ships tomorrow/ });
    expect(links[0]).toHaveAttribute("href", "/w/maple/inbox/c1");
    expect(screen.getByText("Kabir Shah")).toBeInTheDocument();
  });

  it("dragging a draft onto Wednesday 18:00 schedules it (T7.6)", async () => {
    mockLayout();
    const { calls } = setup();
    await card("p-linen");
    const draft = await waitFor(() => {
      const el = document.querySelector('[data-draft-id="d-diwali"]');
      if (!el) throw new Error("no draft");
      return el;
    });
    expect(draft).toHaveTextContent("Reel · drag onto the calendar");

    drag(draft, weekPoint("2026-09-30", "18:00"));

    await waitFor(() => expect(callsTo(calls, "POST", /d-diwali\/schedule$/)).toHaveLength(1));
    expect(callsTo(calls, "POST", /d-diwali\/schedule$/)[0].body).toEqual({ publish_at: "2026-09-30T12:30:00.000Z" });
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Scheduled for Tomorrow 18:00"));
    await waitFor(() =>
      expect(within(day("Wednesday 30 September")).getByRole("link", { name: /^Diwali collection teaser, Scheduled/ })).toBeInTheDocument(),
    );
  });

  it("a published post can't be dragged (T7.6)", async () => {
    mockLayout();
    const { calls } = setup();
    drag(await card("p-arrivals"), weekPoint("2026-09-30", "18:00"));
    expect(toast.error).toHaveBeenCalledWith("Published posts can't be moved.");
    expect(calls.filter((call) => call.method === "POST")).toHaveLength(0);
    expect(within(day("Monday 28 September")).getByRole("link", { name: /^New arrivals/ })).toBeInTheDocument();
  });

  it("a publishing post can't be dragged either", async () => {
    mockLayout();
    const publishing = scheduledPost({ id: "p-live", caption: "Going out now", status: "publishing", publish_at: ist("2026-09-29", "10:00") });
    const { calls } = setup({ cal: () => weekCalendar({ start: "2026-09-28", end: "2026-10-04", posts: [publishing] }) });
    drag(await card("p-live"), weekPoint("2026-09-30", "18:00"));
    expect(toast.error).toHaveBeenCalledWith("Publishing started, so this post can't be moved.");
    expect(calls.filter((call) => call.method === "POST")).toHaveLength(0);
  });

  it("dragging a scheduled post reschedules it, snapping to 15 minutes", async () => {
    mockLayout();
    const { calls } = setup();
    drag(await card("p-linen"), weekPoint("2026-10-01", "15:10"));
    await waitFor(() => expect(callsTo(calls, "POST", /p-linen\/reschedule$/)).toHaveLength(1));
    expect(callsTo(calls, "POST", /p-linen\/reschedule$/)[0].body).toEqual({ publish_at: "2026-10-01T09:30:00.000Z" });
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Moved to Thu 1 Oct 15:00"));
    expect(within(day("Thursday 1 October")).getByRole("link", { name: /^Linen styles/ })).toBeInTheDocument();
    expect(within(day("Tuesday 29 September")).queryByRole("link", { name: /^Linen styles/ })).not.toBeInTheDocument();
  });

  it("moves the card at once and puts it back when the API refuses", async () => {
    mockLayout();
    const { calls } = setup({ reschedule: () => problem(409, "conflict", "Publishing started") });
    drag(await card("p-linen"), weekPoint("2026-10-01", "15:00"));
    await waitFor(() => expect(callsTo(calls, "POST", /p-linen\/reschedule$/)).toHaveLength(1));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Publishing started"));
    await waitFor(() =>
      expect(within(day("Tuesday 29 September")).getByRole("link", { name: /^Linen styles/ })).toBeInTheDocument(),
    );
    expect(within(day("Thursday 1 October")).queryByRole("link", { name: /^Linen styles/ })).not.toBeInTheDocument();
  });

  it("refuses a move to less than 5 minutes from now, and the card stays", async () => {
    mockLayout();
    const { calls } = setup();
    drag(await card("p-linen"), weekPoint("2026-09-29", "10:00"));
    expect(toast.error).toHaveBeenCalledWith("Pick a time at least 5 minutes from now.");
    expect(calls.filter((call) => call.method === "POST")).toHaveLength(0);
    expect(within(day("Tuesday 29 September")).getByRole("link", { name: /^Linen styles/ })).toBeInTheDocument();
  });

  it("opens the composer when a dropped draft isn't ready to schedule (F-13)", async () => {
    mockLayout();
    setup({
      schedule: () =>
        new Response(
          JSON.stringify({
            type: "about:blank",
            title: "validation_error",
            status: 422,
            code: "validation_error",
            errors: [{ field: "asset_ids", message: "Add a photo or video." }],
          }),
          { status: 422, headers: { "Content-Type": "application/problem+json" } },
        ),
    });
    await card("p-linen");
    const draft = await waitFor(() => {
      const el = document.querySelector('[data-draft-id="d-pack"]');
      if (!el) throw new Error("no draft");
      return el;
    });
    drag(draft, weekPoint("2026-09-30", "18:00"));
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/w/maple/schedule/d-pack"));
    expect(toast.error).toHaveBeenCalledWith("Finish this post to schedule it. The checklist shows what's missing.");
  });

  it('"Move to…" works by keyboard (T7.6)', async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    await card("p-linen");
    const trigger = within(day("Tuesday 29 September")).getByRole("button", { name: "Actions for Linen styles" });
    trigger.focus();
    await user.keyboard("{Enter}");
    const item = await screen.findByRole("menuitem", { name: "Move to…" });
    await waitFor(() => expect(item).toHaveFocus());
    await user.keyboard("{Enter}");

    const dialog = await screen.findByRole("dialog", { name: "Move to…" });
    const date = within(dialog).getByLabelText("Date");
    const time = within(dialog).getByLabelText("Time");
    expect(date).toHaveValue("2026-09-29");
    expect(time).toHaveValue("12:00");
    await user.clear(date);
    await user.type(date, "2026-10-02");
    await user.clear(time);
    await user.type(time, "18:30");
    await user.keyboard("{Enter}");

    await waitFor(() => expect(callsTo(calls, "POST", /p-linen\/reschedule$/)).toHaveLength(1));
    expect(callsTo(calls, "POST", /p-linen\/reschedule$/)[0].body).toEqual({ publish_at: "2026-10-02T13:00:00.000Z" });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(within(day("Friday 2 October")).getByRole("link", { name: /^Linen styles/ })).toBeInTheDocument();
  });

  it('"Move to…" refuses a time less than 5 minutes away and says so', async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    await card("p-linen");
    await user.click(within(day("Tuesday 29 September")).getByRole("button", { name: "Actions for Linen styles" }));
    await user.click(await screen.findByRole("menuitem", { name: "Move to…" }));
    const dialog = await screen.findByRole("dialog", { name: "Move to…" });
    fireEvent.change(within(dialog).getByLabelText("Time"), { target: { value: "10:02" } });
    await user.click(within(dialog).getByRole("button", { name: "Move" }));
    expect(within(dialog).getByRole("alert")).toHaveTextContent("Pick a time at least 5 minutes from now.");
    expect(callsTo(calls, "POST", /reschedule$/)).toHaveLength(0);
  });

  it("shows the API's refusal inside the Move to… dialog", async () => {
    const user = userEvent.setup();
    setup({ reschedule: () => problem(409, "conflict", "Publishing started") });
    await card("p-linen");
    await user.click(within(day("Tuesday 29 September")).getByRole("button", { name: "Actions for Linen styles" }));
    await user.click(await screen.findByRole("menuitem", { name: "Move to…" }));
    const dialog = await screen.findByRole("dialog", { name: "Move to…" });
    fireEvent.change(within(dialog).getByLabelText("Time"), { target: { value: "20:00" } });
    await user.click(within(dialog).getByRole("button", { name: "Move" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Publishing started");
  });

  it("schedules a draft from its menu with Schedule for…, and queues one with Add to queue", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    await card("p-linen");
    const rail = screen.getByRole("complementary", { name: "Drafts and queue" });
    await user.click(within(rail).getByRole("button", { name: "Actions for How we pack orders" }));
    await user.click(await screen.findByRole("menuitem", { name: "Add to queue" }));
    await waitFor(() => expect(callsTo(calls, "POST", /d-pack\/queue$/)).toHaveLength(1));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Added to the queue for Tomorrow 18:00"));

    await user.click(within(rail).getByRole("button", { name: "Actions for Diwali collection teaser" }));
    await user.click(await screen.findByRole("menuitem", { name: "Schedule for…" }));
    const dialog = await screen.findByRole("dialog", { name: "Schedule for…" });
    fireEvent.change(within(dialog).getByLabelText("Date"), { target: { value: "2026-10-03" } });
    fireEvent.change(within(dialog).getByLabelText("Time"), { target: { value: "11:00" } });
    await user.click(within(dialog).getByRole("button", { name: "Schedule" }));
    await waitFor(() => expect(callsTo(calls, "POST", /d-diwali\/schedule$/)).toHaveLength(1));
    expect(callsTo(calls, "POST", /d-diwali\/schedule$/)[0].body).toEqual({ publish_at: "2026-10-03T05:30:00.000Z" });
  });

  it("clicking an empty future time starts a post at that time; past times do nothing", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    await card("p-linen");
    await user.click(day("Tuesday 29 September").querySelector('[data-row="10"]')!); // 05:00, past
    expect(callsTo(calls, "POST", /scheduled-posts$/)).toHaveLength(0);

    await user.click(day("Wednesday 30 September").querySelector('[data-row="36"]')!); // 18:00
    await waitFor(() => expect(callsTo(calls, "POST", /scheduled-posts$/)).toHaveLength(1));
    expect(callsTo(calls, "POST", /scheduled-posts$/)[0].body).toEqual({ caption: "", publish_at: "2026-09-30T12:30:00.000Z" });
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/w/maple/schedule/new1"));
  });

  it("New post and Add to queue open the composer on a new draft", async () => {
    const user = userEvent.setup();
    setup();
    await card("p-linen");
    await user.click(screen.getByRole("button", { name: "New post" }));
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/w/maple/schedule/new1"));
    await user.click(screen.getByRole("button", { name: "Add to queue" }));
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/w/maple/schedule/new1?when=queue"));
  });

  it("moves between weeks and back to today", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    await card("p-linen");
    await user.click(screen.getByRole("button", { name: "Next week" }));
    expect(await screen.findByText("5 – 11 Oct")).toBeInTheDocument();
    await waitFor(() =>
      expect(callsTo(calls, "GET", /\/calendar$/).some((c) => c.url.searchParams.get("from") === "2026-10-05")).toBe(true),
    );
    await user.click(screen.getByRole("button", { name: "Today" }));
    expect(await screen.findByText("28 Sep – 4 Oct")).toBeInTheDocument();
  });
});

describe("Schedule page: filters and layers (FR-PUB-08)", () => {
  it("toggles accounts, statuses, the Messages layer and free queue times", async () => {
    const user = userEvent.setup();
    setup();
    await card("p-linen");
    expect(screen.getByRole("link", { name: /^Lookbook/ })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "@maple.cakes", pressed: true }));
    expect(screen.queryByRole("link", { name: /^Lookbook/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "@maple.cakes", pressed: false })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Show" }));
    await user.click(await screen.findByRole("menuitemcheckbox", { name: "Published" }));
    expect(screen.queryByRole("link", { name: /^New arrivals/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole("menuitemcheckbox", { name: "Scheduled DMs" }));
    expect(screen.queryByTestId("dm-chip")).not.toBeInTheDocument();
    await user.click(screen.getByRole("menuitemcheckbox", { name: "Free queue times" }));
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("menu")).not.toBeInTheDocument());
    expect(screen.queryByRole("link", { name: /^New arrivals/ })).not.toBeInTheDocument();
    expect(screen.queryByTestId("dm-chip")).not.toBeInTheDocument();
    expect(screen.queryByTestId("queue-slot")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^Linen styles/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Show (3 hidden)" })).toBeInTheDocument();
  });
});

describe("Schedule page: Month (UX-SCR-04)", () => {
  it("shows six weeks, remembers the view, and a drag to another day keeps the time", async () => {
    mockLayout();
    const user = userEvent.setup();
    const { calls } = setup();
    await card("p-linen");
    await user.click(screen.getByRole("radio", { name: "Month" }));
    expect(await screen.findByText("September 2026")).toBeInTheDocument();
    await waitFor(() =>
      expect(
        callsTo(calls, "GET", /\/calendar$/).some(
          (c) => c.url.searchParams.get("from") === "2026-08-31" && c.url.searchParams.get("to") === "2026-10-11",
        ),
      ).toBe(true),
    );
    expect(window.localStorage.getItem("socialhood:schedule-view")).toBe("month");

    const chip = await waitFor(() => {
      const el = document.querySelector('[data-month-day="2026-09-29"] [data-post-id="p-linen"]');
      if (!el) throw new Error("no chip");
      return el;
    });
    drag(chip, monthPoint("2026-10-02"));
    await waitFor(() => expect(callsTo(calls, "POST", /p-linen\/reschedule$/)).toHaveLength(1));
    expect(callsTo(calls, "POST", /p-linen\/reschedule$/)[0].body).toEqual({ publish_at: "2026-10-02T06:30:00.000Z" });
  });

  it('keeps three posts a day and opens the rest from "+n more"', async () => {
    const user = userEvent.setup();
    window.localStorage.setItem("socialhood:schedule-view", "month");
    const busy = ["09:00", "11:00", "13:00", "15:00", "17:00"].map((time, i) =>
      scheduledPost({ id: `busy${i}`, caption: `Post ${i + 1}`, publish_at: ist("2026-10-05", time) }),
    );
    setup({ cal: () => calendar({ start: "2026-08-31", end: "2026-10-11", posts: busy }) });
    const cell = await screen.findByRole("group", { name: "Monday 5 October" });
    await waitFor(() => expect(within(cell).getAllByRole("link")).toHaveLength(2));
    await user.click(within(cell).getByRole("button", { name: "All 5 posts on Mon 5 Oct" }));
    const popover = await screen.findByRole("dialog");
    expect(within(popover).getAllByRole("link")).toHaveLength(5);
  });

  it("the day number opens that week", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem("socialhood:schedule-view", "month");
    setup();
    await user.click(await screen.findByRole("button", { name: "Show the week of Wed 7 Oct" }));
    expect(await screen.findByText("5 – 11 Oct")).toBeInTheDocument();
    expect(window.localStorage.getItem("socialhood:schedule-view")).toBe("week");
  });
});

describe("Schedule page: List (UX-SCR-04, FR-PUB-14)", () => {
  it("lists a tab's posts and shifts the selected ones", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ bulk: () => json({ updated: [linen, lookbook], deleted_ids: [], skipped: [] }) });
    await card("p-linen");
    await user.click(screen.getByRole("radio", { name: "List" }));
    const list = await screen.findByRole("list", { name: "Scheduled posts" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(2);
    expect(callsTo(calls, "GET", /scheduled-posts$/).some((c) => c.url.searchParams.get("view") === "scheduled")).toBe(true);

    await user.click(screen.getByRole("checkbox", { name: "Select Linen styles" }));
    await user.click(screen.getByRole("checkbox", { name: "Select Lookbook" }));
    expect(screen.getByText("2 selected")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Shift times" }));
    const dialog = await screen.findByRole("dialog", { name: "Shift times" });
    await user.clear(within(dialog).getByLabelText("Amount"));
    await user.type(within(dialog).getByLabelText("Amount"), "2");
    await user.click(within(dialog).getByRole("button", { name: "Shift 2 posts" }));
    await waitFor(() => expect(callsTo(calls, "POST", /bulk$/)).toHaveLength(1));
    expect(callsTo(calls, "POST", /bulk$/)[0].body).toEqual({ ids: ["p-linen", "p-lookbook"], action: "shift", shift_minutes: 120 });
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("2 posts moved."));
  });

  it("deletes the selected posts after confirming, and reports skipped ones", async () => {
    const user = userEvent.setup();
    const { calls } = setup({
      bulk: () =>
        json({ updated: [], deleted_ids: ["p-arrivals"], skipped: [{ id: "x", code: "conflict", message: "Publishing started." }] }),
    });
    await card("p-linen");
    await user.click(screen.getByRole("radio", { name: "List" }));
    await user.click(await screen.findByRole("tab", { name: "Published" }));
    const list = await screen.findByRole("list", { name: "Published posts" });
    expect(within(list).getByRole("link", { name: /^New arrivals, Published/ })).toBeInTheDocument();
    expect(callsTo(calls, "GET", /scheduled-posts$/).some((c) => c.url.searchParams.get("view") === "published")).toBe(true);
    await user.click(screen.getByRole("checkbox", { name: "Select all posts" }));
    // Shift and unschedule are for scheduled posts only.
    expect(screen.queryByRole("button", { name: "Shift times" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Delete" }));
    await user.click(await screen.findByRole("button", { name: "Delete" }));
    await waitFor(() => expect(callsTo(calls, "POST", /bulk$/)).toHaveLength(1));
    expect(callsTo(calls, "POST", /bulk$/)[0].body).toEqual({ ids: ["p-arrivals"], action: "delete" });
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("1 post deleted."));
    expect(toast).toHaveBeenCalledWith("1 post skipped. Publishing started.");
  });

  it("shows failed posts with Instagram's reason and an empty Scheduled tab's copy", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem("socialhood:schedule-view", "list");
    setup({ lists: { scheduled: [] } });
    expect(await screen.findByText("Plan your posts")).toBeInTheDocument();
    expect(screen.getByText("Drag drafts onto the calendar, or set posting times and add posts to your queue.")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Failed" }));
    expect(await screen.findByText("Instagram rejected this: aspect ratio")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Actions for Festive teaser" }));
    expect(await screen.findByRole("menuitem", { name: "Edit and retry" })).toHaveAttribute("href", "/w/maple/schedule/p-festive");
  });
});

describe("Schedule page: right rail (UX-SCR-04)", () => {
  it("shows drafts, posts published in 24 hours against the limit, and the queue", async () => {
    setup();
    await card("p-linen");
    const rail = screen.getByRole("complementary", { name: "Drafts and queue" });
    expect(within(rail).getByRole("list", { name: "Unscheduled drafts" })).toHaveTextContent("Diwali collection teaser");
    expect(within(rail).getByText("How we pack orders")).toBeInTheDocument();
    expect(within(rail).getByText("No media yet · drag onto the calendar")).toBeInTheDocument();
    expect(within(rail).getByRole("meter", { name: "@maple.bakery published in the last 24 hours" })).toHaveAttribute(
      "aria-valuenow",
      "1",
    );
    expect(within(rail).getAllByText("1 of 50")).toHaveLength(1);
    expect(within(rail).getAllByText("Tomorrow 18:00")).toHaveLength(1);
    await waitFor(() => expect(within(rail).getAllByText("Mon, Wed, Fri 18:00")).toHaveLength(2));
  });

  it("is a drawer below 1440 px", async () => {
    const user = userEvent.setup();
    setWidth(1280);
    setup();
    await card("p-linen");
    expect(screen.queryByRole("complementary", { name: "Drafts and queue" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Drafts and queue" }));
    const sheet = await screen.findByRole("dialog", { name: "Drafts and queue" });
    expect(within(sheet).getByText("Diwali collection teaser")).toBeInTheDocument();
    // The grid is covered, so drafts are scheduled from their menu instead of dragged.
    expect(within(sheet).queryByText(/drag onto the calendar/)).not.toBeInTheDocument();
  });
});

describe("Schedule page on phones (UX-SCR-04)", () => {
  it("the agenda view works at 375 px (T7.6)", async () => {
    const user = userEvent.setup();
    setWidth(375);
    const { calls } = setup();
    const agenda = await screen.findByTestId("agenda");
    expect(document.querySelector("[data-day]")).toBeNull(); // no week grid
    const today = within(agenda).getByRole("region", { name: "Today · Tue 29 Sep" });
    expect(within(today).getByRole("link", { name: /^Linen styles, Scheduled/ })).toBeInTheDocument();
    expect(within(agenda).getByRole("region", { name: "Thu 1 Oct" })).toHaveTextContent("DM to Priya Nair");

    // Moving uses "Move to…" (FR-PUB-08).
    const actions = within(today).getByRole("button", { name: "Actions for Linen styles" });
    expect(actions).toHaveClass("size-10");
    await user.click(actions);
    await user.click(await screen.findByRole("menuitem", { name: "Move to…" }));
    const dialog = await screen.findByRole("dialog", { name: "Move to…" });
    fireEvent.change(within(dialog).getByLabelText("Time"), { target: { value: "19:00" } });
    await user.click(within(dialog).getByRole("button", { name: "Move" }));
    await waitFor(() => expect(callsTo(calls, "POST", /p-linen\/reschedule$/)).toHaveLength(1));
    expect(callsTo(calls, "POST", /p-linen\/reschedule$/)[0].body).toEqual({ publish_at: "2026-09-29T13:30:00.000Z" });
  });

  it("does not drag on phones", async () => {
    mockLayout();
    setWidth(375);
    const { calls } = setup();
    await screen.findByTestId("agenda");
    const row = screen.getByRole("link", { name: /^Linen styles/ });
    drag(row, { clientX: 300, clientY: 300 });
    expect(calls.filter((call) => call.method === "POST")).toHaveLength(0);
    expect(toast.error).not.toHaveBeenCalled();
  });
});

describe("Schedule page access", () => {
  it("is for owners and admins", () => {
    setup({ role: "agent" });
    expect(screen.getByText("Schedule is for owners and admins")).toBeInTheDocument();
  });
});
