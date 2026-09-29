import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Route } from "next";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { PostingSlots } from "@/lib/api/types";
import { accountColors } from "@/lib/schedule/format";
import { account, json, renderWithApi, type Call } from "@/test/api";
import { ist, NOW, postingSlots } from "@/test/schedule";

import { PostingTimesDrawer } from "./PostingTimesDrawer";
import { ScheduleProvider, type ScheduleContextValue } from "./schedule-context";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

const accounts = [account({ id: "a1", username: "maple.bakery" }), account({ id: "a2", username: "maple.cakes" })];

const context: ScheduleContextValue = {
  wid: "w1",
  slug: "maple",
  timeZone: "Asia/Kolkata",
  now: NOW,
  accounts: new Map(accounts.map((a) => [a.id, a])),
  colors: accountColors(accounts),
  actions: {
    moveTo: vi.fn(),
    queue: vi.fn(),
    unschedule: vi.fn(),
    duplicate: vi.fn(),
    remove: vi.fn(),
    newPostAt: vi.fn(),
  },
  composerHref: (post) => `/w/maple/schedule/${post.id}` as Route,
  busyIds: new Set(),
};

function setup(put?: (call: Call) => Response) {
  const slots: Record<string, PostingSlots> = {
    a1: postingSlots(),
    a2: postingSlots({ social_account_id: "a2", slots: [], next_free_at: [] }),
  };
  return renderWithApi(
    <ScheduleProvider value={context}>
      <PostingTimesDrawer open onOpenChange={() => {}} accounts={accounts} />
    </ScheduleProvider>,
    {
      handlers: {
        "GET /v1/w/:wid/social-accounts/:id/posting-slots": (_, p) => json(slots[p.id]),
        "PUT /v1/w/:wid/social-accounts/:id/posting-slots": (call, p) => {
          if (put) return put(call);
          const body = call.body as { slots: { weekday: number; local_time: string }[] };
          slots[p.id] = postingSlots({
            social_account_id: p.id,
            slots: body.slots.map((s) => ({ ...s, local_time: `${s.local_time}:00` })),
            next_free_at: [ist("2026-09-30", "09:30")],
          });
          return json(slots[p.id]);
        },
      },
    },
  );
}

function dayRow(name: string): HTMLElement {
  return screen.getByRole("list", { name: `${name} times` }).closest("li")!;
}

beforeEach(() => {
  toast.success.mockReset();
});

describe("PostingTimesDrawer (UX-SCR-14, FR-PUB-09)", () => {
  it("shows each account's weekly times and the next 5 free times", async () => {
    setup();
    const drawer = await screen.findByRole("dialog", { name: "Posting times" });
    expect(within(drawer).getAllByRole("tab").map((tab) => tab.textContent)).toEqual(["@maple.bakery", "@maple.cakes"]);
    expect(await within(drawer).findByRole("list", { name: "Monday times" })).toHaveTextContent("18:00");
    expect(within(drawer).getByRole("list", { name: "Tuesday times" })).toHaveTextContent("No times");
    expect(within(drawer).getByText("Times in Asia/Kolkata")).toBeInTheDocument();
    expect(within(drawer).getByTestId("next-free-times")).toHaveTextContent(
      "Tomorrow 18:00 · Fri 2 Oct 18:00 · Mon 5 Oct 18:00",
    );
    expect(within(drawer).getByRole("button", { name: "Save posting times" })).toBeDisabled();
  });

  it("adds and removes times, copies a day to other days, and saves", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    await screen.findByRole("list", { name: "Monday times" });

    fireEvent.change(screen.getByLabelText("New time on Tuesday"), { target: { value: "09:30" } });
    await user.click(screen.getByRole("button", { name: "Add time on Tuesday" }));
    expect(screen.getByRole("list", { name: "Tuesday times" })).toHaveTextContent("09:30");

    await user.click(screen.getByRole("button", { name: "Remove 18:00 on Friday" }));
    expect(screen.getByRole("list", { name: "Friday times" })).toHaveTextContent("No times");

    await user.click(within(dayRow("Monday")).getByRole("button", { name: "Copy Monday to other days" }));
    const popover = (await screen.findByText("Copy Monday's times to")).closest<HTMLElement>('[role="dialog"]')!;
    await user.click(within(popover).getByRole("checkbox", { name: "Saturday" }));
    await user.click(within(popover).getByRole("checkbox", { name: "Sunday" }));
    await user.click(within(popover).getByRole("button", { name: "Copy" }));
    expect(screen.getByRole("list", { name: "Sunday times" })).toHaveTextContent("18:00");

    await user.click(screen.getByRole("button", { name: "Save posting times" }));
    await waitFor(() => expect(calls.filter((c) => c.method === "PUT")).toHaveLength(1));
    expect(calls.find((c) => c.method === "PUT")?.body).toEqual({
      slots: [
        { weekday: 0, local_time: "18:00" },
        { weekday: 1, local_time: "09:30" },
        { weekday: 2, local_time: "18:00" },
        { weekday: 5, local_time: "18:00" },
        { weekday: 6, local_time: "18:00" },
      ],
    });
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Posting times saved for @maple.bakery"));
    expect(await screen.findByTestId("next-free-times")).toHaveTextContent("Tomorrow 09:30");
    expect(screen.getByRole("button", { name: "Save posting times" })).toBeDisabled();
  });

  it("keeps unsaved changes while switching accounts", async () => {
    const user = userEvent.setup();
    setup();
    await screen.findByRole("list", { name: "Monday times" });
    fireEvent.change(screen.getByLabelText("New time on Sunday"), { target: { value: "11:00" } });
    await user.click(screen.getByRole("button", { name: "Add time on Sunday" }));
    await user.click(screen.getByRole("tab", { name: "@maple.cakes" }));
    await waitFor(() => expect(screen.getByRole("list", { name: "Monday times" })).toHaveTextContent("No times"));
    expect(screen.getByTestId("next-free-times")).toHaveTextContent("No free times yet. Add a posting time.");
    await user.click(screen.getByRole("tab", { name: "@maple.bakery" }));
    expect(await screen.findByRole("list", { name: "Sunday times" })).toHaveTextContent("11:00");
    expect(screen.getByRole("button", { name: "Save posting times" })).toBeEnabled();
  });

  it("shows the API's field error", async () => {
    const user = userEvent.setup();
    setup(
      () =>
        new Response(
          JSON.stringify({
            type: "about:blank",
            title: "validation_error",
            status: 422,
            code: "validation_error",
            errors: [{ field: "slots.0.local_time", message: "Use whole minutes." }],
          }),
          { status: 422, headers: { "Content-Type": "application/problem+json" } },
        ),
    );
    await screen.findByRole("list", { name: "Monday times" });
    await user.click(screen.getByRole("button", { name: "Remove 18:00 on Monday" }));
    await user.click(screen.getByRole("button", { name: "Save posting times" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Use whole minutes.");
  });
});
