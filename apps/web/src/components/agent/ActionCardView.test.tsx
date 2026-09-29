import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { resetAgentHandoff, useAgentHandoff } from "@/lib/agent/handoff";
import { resetInboxStore, useInboxStore } from "@/lib/inbox/store";
import { renderWithApi } from "@/test/api";
import { draftCard, replyCard, scheduleCard } from "@/test/agent";

import { ActionCardView } from "./ActionCardView";

const nav = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: nav.push, replace: vi.fn() }),
  usePathname: () => "/w/maple/home",
}));

const now = new Date("2026-09-29T12:00:00Z");

function show(card: Parameters<typeof ActionCardView>[0]["card"]) {
  const onOpen = vi.fn();
  renderWithApi(<ActionCardView card={card} slug="maple" timeZone="Asia/Kolkata" now={now} onOpen={onOpen} />);
  return { onOpen, section: screen.getByRole("region") };
}

beforeEach(() => {
  nav.push.mockReset();
  resetAgentHandoff();
  resetInboxStore();
});

describe("Action cards (FR-AGT-03)", () => {
  it("Schedule this message: shows the message and time; opens the conversation's schedule popover with them", async () => {
    const { onOpen, section } = show(scheduleCard());
    expect(section).toHaveAccessibleName("Scheduled message");
    expect(within(section).getByText("Hi Priya, your order ships Monday.")).toBeInTheDocument();
    expect(within(section).getByText("Send Tomorrow 08:00 · Window closes Tomorrow 08:12")).toBeInTheDocument();
    expect(within(section).getByText("Priya's window closes 8:12 AM.")).toBeInTheDocument();
    expect(within(section).getByText(/Nothing is sent until you do/)).toBeInTheDocument();

    await userEvent.click(within(section).getByRole("button", { name: "Schedule this message" }));
    expect(nav.push).toHaveBeenCalledWith("/w/maple/inbox/c1?schedule=1");
    expect(onOpen).toHaveBeenCalled();
    // The message waits in the conversation's composer; the time in the hand-off.
    expect(useInboxStore.getState().drafts.c1).toBe("Hi Priya, your order ships Monday.");
    expect(useAgentHandoff.getState().schedule.c1).toMatchObject({ sendAt: "2026-09-30T02:30:00Z" });
  });

  it("without a time that fits, the member picks it", () => {
    const { section } = show(scheduleCard({ prefill: { ...scheduleCard().prefill, send_at: null, window_closes_at: null } }));
    expect(within(section).getByText("You pick the time")).toBeInTheDocument();
  });

  it("Reply to this comment: shows the reply; opens the post with the reply ready", async () => {
    const { section } = show(replyCard());
    expect(section).toHaveAccessibleName("Comment reply");
    expect(within(section).getByText("Public reply")).toBeInTheDocument();
    expect(within(section).getByText("Sorry about the wait! It ships today.")).toBeInTheDocument();
    await userEvent.click(within(section).getByRole("button", { name: "Reply to this comment" }));
    expect(nav.push).toHaveBeenCalledWith("/w/maple/comments/po1");
    expect(useAgentHandoff.getState().commentReply).toMatchObject({ comment_id: "cm-kabir", text: "Sorry about the wait! It ships today." });
  });

  it("a private reply says it's a DM", () => {
    const { section } = show(replyCard({ prefill: { ...replyCard().prefill, private: true } }));
    expect(within(section).getByText("Private reply (a DM)")).toBeInTheDocument();
  });

  it("Open the automation draft: shows its trigger, keywords and message; opens the automations page with it", async () => {
    const { section } = show(draftCard());
    expect(section).toHaveAccessibleName("Automation draft");
    expect(within(section).getByText("Price DM")).toBeInTheDocument();
    expect(within(section).getByText("DM keyword · Send a message")).toBeInTheDocument();
    expect(within(within(section).getByRole("list", { name: "Keywords" })).getAllByRole("listitem").map((li) => li.textContent)).toEqual([
      "price",
      "cost",
    ]);
    await userEvent.click(within(section).getByRole("button", { name: "Open the automation draft" }));
    expect(nav.push).toHaveBeenCalledWith("/w/maple/automations/new");
    expect(useAgentHandoff.getState().automationDraft).toMatchObject({ name: "Price DM", trigger: "dm_keyword" });
  });

  it("an unsafe route falls back to the screen the prefill names", async () => {
    const { section } = show(scheduleCard({ route: "https://evil.example/inbox" }));
    await userEvent.click(within(section).getByRole("button", { name: "Schedule this message" }));
    expect(nav.push).toHaveBeenCalledWith("/w/maple/inbox/c1?schedule=1");
  });
});
