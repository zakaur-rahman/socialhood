import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PRODUCT_DEMO_TIMELINE, productDemo, startLandingMotion } from "./landing-motion";
import { PRODUCT_DEMO_LABEL, PRODUCT_DEMO_NOTE, PRODUCT_DEMO_STEPS, PRODUCT_DEMO_TITLE, ProductDemo } from "./ProductDemo";

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
    const picture = screen.getByRole("img", { name: PRODUCT_DEMO_LABEL });
    expect(within(picture).queryAllByRole("button")).toHaveLength(0);
    const toggle = container.querySelector("section[data-motion-scope] figcaption [data-motion-toggle]");
    expect(toggle).toHaveAttribute("aria-label", "Pause the example");
    expect(toggle).toHaveAttribute("hidden");
    const steps = [...container.querySelectorAll("[data-demo-steps] li")];
    expect(steps.map((step) => step.textContent)).toEqual(PRODUCT_DEMO_STEPS);
    expect(container.querySelectorAll("[data-demo-steps] :is(a, button)")).toHaveLength(0);
  });

  it("the server renders the whole story, finished", () => {
    const { container } = render(<ProductDemo />);
    const text = container.textContent ?? "";
    for (const line of [
      "Is the linen shirt in M?",
      "Product question",
      "Lead 72/100",
      "From: Price list",
      "You: Yes, the linen shirt comes in S to XL",
      "Comment on your Reel",
      "Tap below and we'll send you the link.",
      "Send me the link",
      "Automation: Here's the new linen collection.",
      "Automation · Linen Reel",
      "Can I talk to a person?",
      "AI didn't reply: customer asked for a person",
      "Needs you: asked for a person",
    ]) {
      expect(text, line).toContain(line);
    }
    // The channels in the list wear their real marks: Instagram, WhatsApp and website chat.
    expect(container.querySelectorAll(".pd-row .pd-mark svg")).toHaveLength(5);
    // Nothing is live or lit until a script says so, and every timeline part exists in the markup.
    expect(container.querySelector("[data-live]")).toBeNull();
    expect(lit(container)).toEqual([]);
    const names = new Set([...container.querySelectorAll<HTMLElement>("[data-p]")].map((el) => el.dataset.p));
    for (const beat of PRODUCT_DEMO_TIMELINE) for (const name of [...(beat.on ?? []), ...(beat.off ?? [])]) expect(names, name).toContain(name);
  });

  it("claims nothing it can't back: no results, counts, or Facebook beyond its existing wording", () => {
    const { container } = render(<ProductDemo />);
    const text = `${container.textContent} ${PRODUCT_DEMO_LABEL}`;
    expect(text).not.toMatch(/\bonly\b|the first\b|first to|\bunique\b|exclusive|\bbest\b|#1|guarantee|\binstant|trusted by|\d+%|\d+x\b|faster|Facebook|TikTok|verified|official partner/i);
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
    vi.advanceTimersByTime(at(2) - at(1));
    expect(lit(container)).toContain("conv-maya");

    // Off screen, too.
    DrivenObserver.last!.fire(false);
    vi.advanceTimersByTime(30_000);
    expect(litStep(container)).toBe(PRODUCT_DEMO_STEPS[0]);
    DrivenObserver.last!.fire(true);

    // The last step, then the rest, then it starts again.
    vi.advanceTimersByTime(at(PRODUCT_DEMO_TIMELINE.length - 2) - at(2));
    expect(litStep(container)).toBe(PRODUCT_DEMO_STEPS[5]);
    expect(lit(container)).toContain("sam-banner");
    expect(lit(container)).not.toContain("conv-ana");
    vi.advanceTimersByTime(PRODUCT_DEMO_TIMELINE.at(-1)!.at - at(PRODUCT_DEMO_TIMELINE.length - 2));
    expect(litStep(container)).toBe(PRODUCT_DEMO_STEPS[0]);
    expect(lit(container)).not.toContain("sam-banner");

    stop();
    expect(container.querySelector("[data-live]")).toBeNull();
    expect(lit(container)).toEqual([]);
    expect(container.querySelector<HTMLElement>('[data-row="sam"]')?.style.getPropertyValue("--slot")).toBe("0");
    expect(container.querySelector<HTMLElement>('[data-row="visitor"]')?.style.getPropertyValue("--slot")).toBe("4");
    expect(toggle).toHaveAttribute("hidden");
  });
});
