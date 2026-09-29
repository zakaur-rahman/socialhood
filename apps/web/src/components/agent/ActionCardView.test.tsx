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
  const section = screen.getByRole("region");
  return { onOpen, section, summary: within(section).getByTestId("action-summary") };
}

beforeEach(() => {
  nav.push.mockReset();
  resetAgentHandoff();
  resetInboxStore();
});

describe("Action cards (FR-AGT-03): one light row with Open", () => {
  it("Schedule this message: one line of what it holds; Open takes the message and time to the conversation", async () => {
    const { onOpen, section, summary } = show(scheduleCard());
    expect(section).toHaveAccessibleName("Scheduled message");
    expect(within(section).getByText("Schedule this message")).toBeInTheDocument();
    expect(summary).toHaveTextContent(
      "“Hi Priya, your order ships Monday.” · Send Tomorrow 08:00 · Window closes Tomorrow 08:12 · Priya's window closes 8:12 AM.",
    );
    const open = within(section).getByRole("button", { name: "Open: Schedule this message" });
    expect(open).toHaveTextContent("Open");
    expect(open).toHaveAccessibleDescription(/Nothing is sent until you do/);

    await userEvent.click(open);
    expect(nav.push).toHaveBeenCalledWith("/w/maple/inbox/c1?schedule=1");
    expect(onOpen).toHaveBeenCalled();
    // The message waits in the conversation's composer; the time in the hand-off.
    expect(useInboxStore.getState().drafts.c1).toBe("Hi Priya, your order ships Monday.");
    expect(useAgentHandoff.getState().schedule.c1).toMatchObject({ sendAt: "2026-09-30T02:30:00Z" });
  });

  it("without a time that fits, the member picks it", () => {
    const { summary } = show(scheduleCard({ note: null, prefill: { ...scheduleCard().prefill, send_at: null, window_closes_at: null } }));
    expect(summary).toHaveTextContent("“Hi Priya, your order ships Monday.” · You pick the time");
  });

  it("Reply to this comment: the reply in one line; Open takes it to the post", async () => {
    const { section, summary } = show(replyCard());
    expect(section).toHaveAccessibleName("Comment reply");
    expect(summary).toHaveTextContent("Public reply · “Sorry about the wait! It ships today.”");
    await userEvent.click(within(section).getByRole("button", { name: "Open: Reply to this comment" }));
    expect(nav.push).toHaveBeenCalledWith("/w/maple/comments/po1");
    expect(useAgentHandoff.getState().commentReply).toMatchObject({ comment_id: "cm-kabir", text: "Sorry about the wait! It ships today." });
  });

  it("a private reply says it's a DM", () => {
    const { summary } = show(replyCard({ prefill: { ...replyCard().prefill, private: true } }));
    expect(summary).toHaveTextContent(/^Private reply \(a DM\)/);
  });

  it("Open the automation draft: name, trigger, keywords and action; Open takes it to the automations page", async () => {
    const { section, summary } = show(draftCard());
    expect(section).toHaveAccessibleName("Automation draft");
    expect(summary).toHaveTextContent("Price DM · DM keyword · price, cost · Send a message");
    await userEvent.click(within(section).getByRole("button", { name: "Open the automation draft" }));
    expect(nav.push).toHaveBeenCalledWith("/w/maple/automations/new");
    expect(useAgentHandoff.getState().automationDraft).toMatchObject({ name: "Price DM", trigger: "dm_keyword" });
  });

  it("an unsafe route falls back to the screen the prefill names", async () => {
    const { section } = show(scheduleCard({ route: "https://evil.example/inbox" }));
    await userEvent.click(within(section).getByRole("button", { name: "Open: Schedule this message" }));
    expect(nav.push).toHaveBeenCalledWith("/w/maple/inbox/c1?schedule=1");
  });

  it("is a 40 px target on phones", () => {
    const { section } = show(replyCard());
    expect(within(section).getByRole("button", { name: /^Open/ })).toHaveClass("min-h-10", "md:min-h-8");
  });
});
