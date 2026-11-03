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
}

const reducedMotion = (reduce: boolean) =>
  vi.fn((query: string) => ({ matches: reduce && query.includes("reduce"), media: query, addEventListener() {}, removeEventListener() {} }));

const lit = (container: HTMLElement) => [...container.querySelectorAll<HTMLElement>("[data-p].on")].map((el) => el.dataset.p);
const litStep = (container: HTMLElement) => container.querySelector("[data-demo-steps] li.on")?.textContent;
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

  it("schedules inside the reply window: at least 2 minutes away, and before it closes (checkSchedule)", () => {
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

  it("is about 21 s, with a short rest, and under 25 s in all", () => {
    const total = PRODUCT_DEMO_TIMELINE.at(-1)!.at;
    const lastChange = PRODUCT_DEMO_TIMELINE.at(-2)!.at;
    expect(total).toBeLessThan(25_000);
    expect(lastChange).toBeLessThanOrEqual(21_000);
    // In order, or a later beat would fire at once.
    const times = PRODUCT_DEMO_TIMELINE.map((beat) => beat.at);
    expect(times).toEqual([...times].sort((a, b) => a - b));
  });

  it("with reduced motion the script leaves it as rendered", () => {
    vi.stubGlobal("matchMedia", reducedMotion(true));
    const { container } = render(<ProductDemo />);
    const stop = startLandingMotion(container);
    expect(container.querySelector("[data-live]")).toBeNull();
    expect(container.querySelector("[data-motion-toggle]")).toHaveAttribute("hidden");
    expect(DrivenObserver.last).toBeNull();
    stop();
  });

  it("the list follows the filters: Instagram, each account, WhatsApp, then all", () => {
    vi.useFakeTimers();
    const { container } = render(<ProductDemo />);
    const stop = productDemo(container);
    const stage = container.querySelector<HTMLElement>("[data-demo]")!;
    const shown = () => [...container.querySelectorAll<HTMLElement>("[data-row].on")].map((row) => row.dataset.row).sort();
    DrivenObserver.last!.fire(true);

    vi.advanceTimersByTime(beatAt((b) => b.state?.strip === "instagram"));
    expect(stage.dataset.strip).toBe("instagram");
    expect(shown()).toEqual(["lena", "maya", "ria", "theo"]);
    vi.advanceTimersByTime(beatAt((b) => b.state?.acct === "mumbai") - beatAt((b) => b.state?.strip === "instagram"));
    expect(stage.dataset.acct).toBe("mumbai");
    expect(shown()).toEqual(["maya", "ria"]);
    vi.advanceTimersByTime(beatAt((b) => b.state?.acct === "pune") - beatAt((b) => b.state?.acct === "mumbai"));
    expect(shown()).toEqual(["lena", "theo"]);
    // Changing platform clears the account (InboxShell changePlatform).
    vi.advanceTimersByTime(beatAt((b) => b.state?.strip === "whatsapp") - beatAt((b) => b.state?.acct === "pune"));
    expect(stage.dataset.acct).toBe("all");
    expect(shown()).toEqual(["leo", "nina"]);
    stop();
    expect(stage.dataset.strip).toBe("all");
    expect(stage.dataset.view).toBe("list");
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
    expect(lit(container)).toEqual(expect.arrayContaining(["pick", "row-nina", "row-visitor"]));
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
    expect(litStep(container)).toBe(PRODUCT_DEMO_STEPS[6]);
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
