import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CHIP_VIEWS } from "@/components/inbox/ListHeader";
import { checkSchedule, scheduleLimits } from "@/components/inbox/ScheduleFields";

import { PRODUCT_DEMO_TIMELINE, productDemo, startLandingMotion } from "./landing-motion";
import { PRODUCT_DEMO_CHIPS, PRODUCT_DEMO_LABEL, PRODUCT_DEMO_NOTE, PRODUCT_DEMO_PLAN_NOTE, PRODUCT_DEMO_STEPS, PRODUCT_DEMO_TITLE, ProductDemo } from "./ProductDemo";

/** An IntersectionObserver the test drives. */
class DrivenObserver {
  static last: DrivenObserver | null = null;
  constructor(private callback: IntersectionObserverCallback) {
    DrivenObserver.last = this;
  }
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return [];
  }
  fire(isIntersecting: boolean) {
    this.callback([{ isIntersecting } as IntersectionObserverEntry], this as unknown as IntersectionObserver);
  }
  /** First reported below the viewport, then scrolled into view (the story plays from its start). */
  arrive() {
    this.fire(false);
    this.fire(true);
  }
}

const reducedMotion = (reduce: boolean) =>
  vi.fn((query: string) => ({ matches: reduce && query.includes("reduce"), media: query, addEventListener() {}, removeEventListener() {} }));

const lit = (container: HTMLElement) => [...container.querySelectorAll<HTMLElement>("[data-p].on")].map((el) => el.dataset.p);
const litStep = (container: HTMLElement) => container.querySelector("[data-demo-steps] li.on")?.textContent;
const stepButton = (container: HTMLElement, step: number) => container.querySelectorAll<HTMLButtonElement>("[data-demo-steps] button")[step];
const beatAt = (test: (beat: (typeof PRODUCT_DEMO_TIMELINE)[number]) => boolean) => PRODUCT_DEMO_TIMELINE.find(test)!.at;

describe("the product demo (C-175)", () => {
  beforeEach(() => {
    DrivenObserver.last = null;
    vi.stubGlobal("IntersectionObserver", DrivenObserver);
    vi.stubGlobal("matchMedia", reducedMotion(false));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("has one h2, the example label, a pause control outside the picture, and the steps as plain captions", () => {
    const { container } = render(<ProductDemo />);
    expect(screen.getAllByRole("heading", { level: 2 })).toHaveLength(1);
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent(PRODUCT_DEMO_TITLE);
    expect(container.querySelector("figcaption")).toHaveTextContent(PRODUCT_DEMO_NOTE);
    // Two accounts on one platform are never implied on Free.
    expect(container.querySelector("figcaption")).toHaveTextContent(PRODUCT_DEMO_PLAN_NOTE);
    const picture = screen.getByRole("img", { name: PRODUCT_DEMO_LABEL });
    expect(within(picture).queryAllByRole("button")).toHaveLength(0);
    const toggle = container.querySelector("section[data-motion-scope] figcaption [data-motion-toggle]");
    expect(toggle).toHaveAttribute("aria-label", "Pause the example");
    expect(toggle).toHaveAttribute("hidden");
    const steps = [...container.querySelectorAll("[data-demo-steps] li")];
    expect(steps.map((step) => step.textContent)).toEqual(PRODUCT_DEMO_STEPS);
    // Plain captions until a script takes over (see below).
    expect(container.querySelectorAll("[data-demo-steps] :is(a, button)")).toHaveLength(0);
  });

  it("the server renders the whole story, finished, with the app's own labels", () => {
    const { container } = render(<ProductDemo />);
    const text = container.textContent ?? "";
    for (const line of [
      "Do you have oat milk?",
      "Product question",
      "Lead 72/100",
      "From: Menu",
      "You: Yes, oat milk is available",
      "Schedule message",
      "Window closes Tomorrow 17:26",
      "Times are in Asia/Kolkata.",
      "Scheduled for Today 18:30",
      "1 scheduled · Today 18:30",
      "All accounts",
      "@cafe_mumbai",
      "@cafe_pune",
      "Comment on your Reel",
      "Tap below and we'll send you the link.",
      "Send me the link",
      "Automation: Here's the new menu.",
      "Automation · New menu Reel",
      "Can I talk to a person?",
      "AI didn't reply: customer asked for a person",
      "Needs you: asked for a person",
      // The details panel, in the app's words.
      "Customer since",
      "Linked account",
      "Started from",
      "They wrote first",
      "Lead score",
      "72 of 100",
      "View contact",
      "Latest message",
      "Add answer",
      "Correct the AI",
      "No summary yet. It appears after a few messages, or ask for one now.",
      "Summarise",
      // Assigning, in the app's words.
      "Assigned to",
      "Nobody",
      "Alex R. (you)",
      "Priya S.",
      "Assigned",
    ]) {
      expect(text, line).toContain(line);
    }
    // The list's chips are the app's, in its order.
    expect(PRODUCT_DEMO_CHIPS).toEqual(CHIP_VIEWS.map((view) => view.label));
    // The strip offers connected platforms: All, Instagram, WhatsApp, Website.
    expect([...container.querySelectorAll("[data-seg]")].map((seg) => seg.textContent)).toEqual(["All", "Instagram", "WhatsApp", "Website"]);
    // Every row wears its real channel mark.
    expect(container.querySelectorAll(".pd-row .pd-mark svg")).toHaveLength(9);
    // Nothing is live or lit until a script says so, and every name the timeline uses exists in the markup.
    expect(container.querySelector("[data-live]")).toBeNull();
    expect(lit(container)).toEqual([]);
    const names = new Set([...container.querySelectorAll<HTMLElement>("[data-p]")].map((el) => el.dataset.p));
    const targets = new Set([...container.querySelectorAll<HTMLElement>("[data-at]")].map((el) => el.dataset.at));
    const rows = new Set([...container.querySelectorAll<HTMLElement>("[data-row]")].map((el) => el.dataset.row));
    for (const beat of PRODUCT_DEMO_TIMELINE) {
      for (const name of [...(beat.on ?? []), ...(beat.off ?? [])]) expect(names, name).toContain(name);
      for (const row of beat.list ?? []) expect(rows, row).toContain(row);
      if (beat.to) expect(targets, beat.to).toContain(beat.to);
    }
  });

  it("schedules inside the reply window: at least 1 minute away, and before it closes (checkSchedule)", () => {
    const { container } = render(<ProductDemo />);
    expect(container.querySelector(".pd-sched")).toHaveTextContent("Fri 6 Nov 2026");
    expect(container.querySelector(".pd-sched")).toHaveTextContent("18:30");
    expect(container.querySelector(".pd-sched")).toHaveTextContent("Window closes Tomorrow 17:26");
    // The app's own check, with the scene's clock: the 17:26 message opens a window to 17:26 tomorrow.
    const now = new Date("2026-11-06T11:56:00Z"); // 17:26 in Asia/Kolkata
    const closes = new Date(now.getTime() + 24 * 60 * 60_000).toISOString();
    const checked = checkSchedule({ date: "2026-11-06", time: "18:30" }, "Asia/Kolkata", scheduleLimits(now, closes), now);
    expect(checked).toEqual({ at: new Date("2026-11-06T13:00:00Z") });
  });

  it("claims nothing it can't back: no results, counts, or Facebook beyond its existing wording", () => {
    const { container } = render(<ProductDemo />);
    const text = `${container.textContent} ${PRODUCT_DEMO_LABEL}`;
    expect(text).not.toMatch(/\bonly\b|the first\b|first to|\bunique\b|exclusive|\bbest\b|#1|guarantee|\binstant|trusted by|\d+%|\d+x\b|faster|Facebook|TikTok|verified|official partner/i);
  });

  it("is about 22 s, with a short rest, and 23 s or less in all", () => {
    const total = PRODUCT_DEMO_TIMELINE.at(-1)!.at;
    const lastChange = PRODUCT_DEMO_TIMELINE.at(-2)!.at;
    expect(total).toBeLessThanOrEqual(23_000);
    expect(lastChange).toBeLessThanOrEqual(22_300);
    // In order, or a later beat would fire at once.
    const times = PRODUCT_DEMO_TIMELINE.map((beat) => beat.at);
    expect(times).toEqual([...times].sort((a, b) => a - b));
  });

  it("with reduced motion it holds still on the story's end, with no timer and no pause control, and a step shows its finished state", () => {
    vi.useFakeTimers();
    vi.stubGlobal("matchMedia", reducedMotion(true));
    const { container } = render(<ProductDemo />);
    const stop = startLandingMotion(container);
    expect(container.querySelector("[data-motion-toggle]")).toHaveAttribute("hidden");
    expect(DrivenObserver.last).toBeNull();
    expect(lit(container)).toContain("det-sam-who");
    // The brief "Assigned" toast is gone: it would cover the frame's key state.
    expect(lit(container)).not.toContain("assign-toast");
    const before = lit(container);
    vi.advanceTimersByTime(60_000);
    expect(lit(container)).toEqual(before);

    stepButton(container, 3).click();
    // The whole of "Schedule a message": sent, the chip, the tab back on Chats. And it stays there.
    expect(lit(container)).toEqual(expect.arrayContaining(["conv-maya", "maya-chip", "tab-count"]));
    expect(lit(container)).not.toContain("conv-sam");
    expect(stepButton(container, 3)).toHaveAttribute("aria-current", "step");
    const shown = lit(container);
    vi.advanceTimersByTime(60_000);
    expect(lit(container)).toEqual(shown);
    stop();
  });

  it("the captions are plain text until the script takes over, then real buttons, and plain again after", () => {
    const { container } = render(<ProductDemo />);
    expect(container.querySelectorAll("[data-demo-steps] button")).toHaveLength(0);
    expect(container.querySelectorAll("[data-demo-steps] span.pd-step")).toHaveLength(PRODUCT_DEMO_STEPS.length);
    const stop = productDemo(container);
    const buttons = screen.getAllByRole("button", { name: new RegExp(PRODUCT_DEMO_STEPS.join("|")) });
    expect(buttons.map((b) => b.textContent)).toEqual(PRODUCT_DEMO_STEPS);
    for (const button of buttons) expect(button.tagName).toBe("BUTTON");
    DrivenObserver.last!.arrive();
    expect(buttons[0]).toHaveAttribute("aria-current", "step");
    expect(buttons[1]).not.toHaveAttribute("aria-current");
    stop();
    expect(container.querySelectorAll("[data-demo-steps] button")).toHaveLength(0);
    expect(container.querySelectorAll("[data-demo-steps] span.pd-step")).toHaveLength(PRODUCT_DEMO_STEPS.length);
  });

  it("a jump gives exactly the state of playing up to that step, forwards and backwards", () => {
    vi.useFakeTimers();
    const snapshot = (container: HTMLElement) => ({
      lit: lit(container).sort(),
      data: { ...container.querySelector<HTMLElement>("[data-demo]")!.dataset, seek: undefined },
      rows: [...container.querySelectorAll<HTMLElement>("[data-row].on")].map((row) => [row.dataset.row, row.style.getPropertyValue("--y")]),
      step: litStep(container),
    });
    PRODUCT_DEMO_STEPS.forEach((_, step) => {
      const played = render(<ProductDemo />);
      const stopPlayed = productDemo(played.container);
      DrivenObserver.last!.arrive();
      vi.advanceTimersByTime(beatAt((b) => b.step === step));
      const expected = snapshot(played.container);
      stopPlayed();
      played.unmount();

      const jumped = render(<ProductDemo />);
      const stopJumped = productDemo(jumped.container);
      DrivenObserver.last!.arrive();
      // To the end, then back: nothing of the later state may survive.
      stepButton(jumped.container, PRODUCT_DEMO_STEPS.length - 1).click();
      stepButton(jumped.container, step).click();
      expect(snapshot(jumped.container)).toEqual(expected);
      stopJumped();
      jumped.unmount();
    });
  });

  it("a jump plays on from there, and paused it shows the step's finished state and stays paused", () => {
    vi.useFakeTimers();
    const { container } = render(<ProductDemo />);
    const stop = productDemo(container);
    const toggle = container.querySelector<HTMLButtonElement>("[data-motion-toggle]")!;
    DrivenObserver.last!.arrive();

    stepButton(container, 5).click();
    expect(litStep(container)).toBe(PRODUCT_DEMO_STEPS[5]);
    vi.advanceTimersByTime(beatAt((b) => b.on?.includes("ana-open") ?? false) - beatAt((b) => b.step === 5));
    expect(lit(container)).toContain("ana-open");

    toggle.click();
    stepButton(container, 2).click();
    expect(toggle).toHaveAttribute("aria-pressed", "true");
    expect(litStep(container)).toBe(PRODUCT_DEMO_STEPS[2]);
    expect(lit(container)).toContain("maya-sent");
    expect(lit(container)).not.toContain("ana-open");
    const shown = lit(container);
    vi.advanceTimersByTime(30_000);
    expect(lit(container)).toEqual(shown);
    stop();
  });

  it("assigning: the header's control opens the app's menu, and the header, the row and the panel show the teammate", () => {
    vi.useFakeTimers();
    const { container } = render(<ProductDemo />);
    const stop = productDemo(container);
    DrivenObserver.last!.arrive();
    vi.advanceTimersByTime(beatAt((b) => b.on?.includes("assign-menu") ?? false));
    expect(litStep(container)).toBe(PRODUCT_DEMO_STEPS[7]);
    expect(lit(container)).toEqual(expect.arrayContaining(["assign-menu", "sam-assign-none", "det-sam-nobody"]));
    expect(lit(container)).not.toContain("sam-row-who");
    vi.advanceTimersByTime(beatAt((b) => b.on?.includes("assign-toast") ?? false) - beatAt((b) => b.on?.includes("assign-menu") ?? false));
    expect(lit(container)).toEqual(expect.arrayContaining(["assign-toast", "sam-assign-who", "sam-row-who", "det-sam-who"]));
    expect(lit(container)).not.toContain("assign-menu");
    // Assigning doesn't clear Needs you (only a reply does).
    expect(lit(container)).toContain("sam-need");
    stop();
  });

  it("has no app sidebar, and the details panel follows the open conversation and the story", () => {
    vi.useFakeTimers();
    const { container } = render(<ProductDemo />);
    expect(container.querySelector(".pd-side")).toBeNull();
    // The panel's sections, in the app's order (DetailsPanel).
    const maya = container.querySelector<HTMLElement>('[data-p="det-maya"]')!;
    expect([...maya.querySelectorAll("h3")].map((h) => h.textContent)).toEqual(["Customer", "Assigned to", "Latest message", "Summary"]);
    const stop = productDemo(container);
    DrivenObserver.last!.arrive();
    const open = () => lit(container).filter((name) => name && /^det-(maya|theo|nina|ana|sam)$/.test(name));
    const goTo = (() => {
      let now = 0;
      return (name: string) => {
        const at = beatAt((b) => b.on?.includes(name) ?? false);
        vi.advanceTimersByTime(at - now);
        now = at;
      };
    })();

    goTo("det-maya");
    expect(open()).toEqual(["det-maya"]);
    // Opened: not analysed yet, no lead score.
    expect(lit(container)).toContain("det-maya-wait");
    expect(lit(container)).not.toContain("det-maya-lead");
    goTo("det-maya-lead");
    expect(lit(container)).toContain("det-maya-analysis");
    expect(lit(container)).not.toContain("det-maya-wait");

    goTo("det-ana");
    expect(open()).toEqual(["det-ana"]);
    goTo("det-sam");
    expect(open()).toEqual(["det-sam"]);
    expect(lit(container)).not.toContain("det-sam-need");
    goTo("det-sam-need");
    expect(lit(container)).toContain("det-sam-analysis");
    stop();
  });

  it("the list follows the filters: Instagram, each account, WhatsApp, then all", () => {
    vi.useFakeTimers();
    const { container } = render(<ProductDemo />);
    const stop = productDemo(container);
    const stage = container.querySelector<HTMLElement>("[data-demo]")!;
    const shown = () => [...container.querySelectorAll<HTMLElement>("[data-row].on")].map((row) => row.dataset.row).sort();
    DrivenObserver.last!.arrive();

    vi.advanceTimersByTime(beatAt((b) => b.state?.strip === "instagram"));
    expect(stage.dataset.strip).toBe("instagram");
    expect(shown()).toEqual(["lena", "maya", "ria", "theo"]);
    vi.advanceTimersByTime(beatAt((b) => b.state?.acct === "mumbai") - beatAt((b) => b.state?.strip === "instagram"));
    expect(stage.dataset.acct).toBe("mumbai");
    expect(shown()).toEqual(["maya", "ria"]);
    vi.advanceTimersByTime(beatAt((b) => b.state?.acct === "pune") - beatAt((b) => b.state?.acct === "mumbai"));
    expect(shown()).toEqual(["lena", "theo"]);
    // Whenever the list changes, its top conversation opens: the thread and the panel match the list.
    const openNow = () => lit(container).filter((name) => name && /^(conv|det|sel)-[a-z]+$/.test(name)).sort();
    expect(openNow()).toEqual(["conv-theo", "det-theo", "sel-theo"]);
    // Changing platform clears the account (InboxShell changePlatform).
    vi.advanceTimersByTime(beatAt((b) => b.state?.strip === "whatsapp") - beatAt((b) => b.state?.acct === "pune"));
    expect(stage.dataset.acct).toBe("all");
    expect(shown()).toEqual(["leo", "nina"]);
    expect(openNow()).toEqual(["conv-nina", "det-nina", "sel-nina"]);
    expect(lit(container)).not.toContain("nina-dot");
    vi.advanceTimersByTime(beatAt((b) => b.state?.strip === "all" && b.at > 0) - beatAt((b) => b.state?.strip === "whatsapp"));
    expect(openNow()).toEqual(["conv-maya", "det-maya", "sel-maya"]);
    stop();
    expect(stage.dataset.strip).toBe("all");
    expect(stage.dataset.view).toBe("list");
  });

  it("already on screen when the script arrives, it keeps the finished frame and plays on from the rest", () => {
    vi.useFakeTimers();
    const { container } = render(<ProductDemo />);
    const stop = productDemo(container);
    DrivenObserver.last!.fire(true);
    expect(litStep(container)).toBe(PRODUCT_DEMO_STEPS[7]);
    expect(lit(container)).toEqual(expect.arrayContaining(["conv-sam", "det-sam-who", "sam-row-who"]));
    expect(lit(container)).not.toContain("assign-toast");
    const last = PRODUCT_DEMO_TIMELINE.length - 2;
    vi.advanceTimersByTime(PRODUCT_DEMO_TIMELINE.at(-1)!.at - PRODUCT_DEMO_TIMELINE[last].at);
    expect(litStep(container)).toBe(PRODUCT_DEMO_STEPS[0]);
    expect(lit(container)).toContain("conv-theo");
    stop();
  });

  it("plays only on screen, stops on pause and off screen, loops after its rest, and restores the server's state", () => {
    vi.useFakeTimers();
    const { container } = render(<ProductDemo />);
    const stop = productDemo(container);
    const toggle = container.querySelector<HTMLButtonElement>("[data-motion-toggle]")!;
    const at = (index: number) => PRODUCT_DEMO_TIMELINE[index].at;

    // Reported off screen: armed in its start state, and the clock doesn't run.
    DrivenObserver.last!.fire(false);
    expect(container.querySelector("[data-live]")).not.toBeNull();
    // The start has a conversation open, never an empty pane.
    expect(lit(container)).toEqual(expect.arrayContaining(["conv-theo", "sel-theo", "det-theo", "row-nina", "row-visitor"]));
    expect(lit(container)).not.toContain("row-maya");
    vi.advanceTimersByTime(30_000);
    expect(lit(container)).not.toContain("row-maya");

    DrivenObserver.last!.fire(true);
    expect(litStep(container)).toBe(PRODUCT_DEMO_STEPS[0]);
    vi.advanceTimersByTime(at(1));
    expect(lit(container)).toContain("row-maya");

    // Pause holds the story; play picks up where it stopped.
    toggle.click();
    expect(toggle).toHaveAttribute("aria-pressed", "true");
    vi.advanceTimersByTime(30_000);
    expect(lit(container)).not.toContain("conv-maya");
    toggle.click();
    const opened = beatAt((b) => b.on?.includes("conv-maya") ?? false);
    vi.advanceTimersByTime(opened - at(1));
    expect(lit(container)).toContain("conv-maya");

    // Off screen, too.
    DrivenObserver.last!.fire(false);
    vi.advanceTimersByTime(30_000);
    expect(litStep(container)).toBe(PRODUCT_DEMO_STEPS[0]);
    DrivenObserver.last!.fire(true);

    // The last step, then the rest, then it starts again.
    const last = PRODUCT_DEMO_TIMELINE.length - 2;
    vi.advanceTimersByTime(at(last) - opened);
    expect(litStep(container)).toBe(PRODUCT_DEMO_STEPS[7]);
    expect(lit(container)).toContain("sam-banner");
    expect(lit(container)).not.toContain("conv-ana");
    vi.advanceTimersByTime(PRODUCT_DEMO_TIMELINE.at(-1)!.at - at(last));
    expect(litStep(container)).toBe(PRODUCT_DEMO_STEPS[0]);
    expect(lit(container)).not.toContain("sam-banner");

    stop();
    expect(container.querySelector("[data-live]")).toBeNull();
    expect(lit(container)).toEqual([]);
    expect(container.querySelector<HTMLElement>('[data-row="sam"]')?.style.getPropertyValue("--y")).toBe("0px");
    expect(container.querySelector<HTMLElement>('[data-row="ana"]')?.style.getPropertyValue("--y")).toBe("90px");
    expect(toggle).toHaveAttribute("hidden");
  });
});
