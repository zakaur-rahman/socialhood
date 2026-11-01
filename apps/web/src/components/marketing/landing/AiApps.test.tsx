import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PUBLIC_PATHS } from "@/lib/marketing/site";

import { AI_APPS_SCENE, AI_APPS_TITLE, AiApps } from "./AiApps";
import { AI_APPS_TIMELINE, aiApps, startLandingMotion } from "./landing-motion";

/** An IntersectionObserver the test drives: `fire(top, intersecting)` reports its target. */
class DrivenObserver {
  static last: DrivenObserver | null = null;
  static all: DrivenObserver[] = [];
  target: Element | null = null;
  disconnected = false;
  constructor(private callback: IntersectionObserverCallback) {
    DrivenObserver.last = this;
    DrivenObserver.all.push(this);
  }
  observe(target: Element) {
    this.target = target;
  }
  unobserve() {}
  disconnect() {
    this.disconnected = true;
  }
  takeRecords() {
    return [];
  }
  fire(top: number, isIntersecting: boolean) {
    const entry = { isIntersecting, boundingClientRect: { top } as DOMRectReadOnly, target: this.target } as IntersectionObserverEntry;
    this.callback([entry], this as unknown as IntersectionObserver);
  }
}

/** aiApps makes two: the player (the scene) first, then the one that watches the band. */
const bandObserver = () => DrivenObserver.all[1];
const sceneObserver = () => DrivenObserver.all[0];

const reducedMotion = (reduce: boolean) =>
  vi.fn((query: string) => ({ matches: reduce && query.includes("reduce"), media: query, addEventListener() {}, removeEventListener() {} }));

/** The final state: every step shown (no data-live), the button on Confirmed. */
function expectFinal(scene: HTMLElement) {
  expect(scene).not.toHaveAttribute("data-live");
  expect(scene.querySelectorAll(".mh-step")).toHaveLength(5);
  expect(scene).toHaveTextContent(AI_APPS_SCENE.done);
  expect(scene).toHaveTextContent(AI_APPS_SCENE.summaryNote);
}

describe("the AI assistant band (C-168)", () => {
  beforeEach(() => {
    DrivenObserver.last = null;
    DrivenObserver.all = [];
    vi.stubGlobal("IntersectionObserver", DrivenObserver);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("has one h2, an example chat labelled as one picture, and links that resolve", () => {
    const { container } = render(<AiApps />);
    expect(screen.getAllByRole("heading", { level: 2 })).toHaveLength(1);
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent(AI_APPS_TITLE);
    const scene = screen.getByRole("img", { name: /^Example:/ });
    expect(scene.closest("figure")?.querySelector("figcaption")).toHaveTextContent("Example. Works in Claude, ChatGPT and Codex.");
    // The chat is a picture: its parts are hidden from assistive tech, and it has no controls.
    expect(within(scene).queryAllByRole("button")).toHaveLength(0);
    // The apps are plain names; no logos or images.
    expect(container.querySelectorAll("img, svg image")).toHaveLength(0);
    const links = [...container.querySelectorAll("a")].map((a) => a.getAttribute("href"));
    expect(links).toEqual(["/mcp", "/developers/mcp"]);
    for (const href of links) expect(PUBLIC_PATHS, href ?? "").toContain(href);
  });

  it("claims nothing it can't back: no 'only', 'first to', counts of users, or things AI apps can't do", () => {
    const { container } = render(<AiApps />);
    const text = container.textContent ?? "";
    expect(text).not.toMatch(/\bonly\b|the first\b|first to|\bunique\b|exclusive|\bfew\b|no other|\bbest\b|#1|official partner|verified|TikTok/i);
    // Never says the AI sends messages (C-169: it can set up an automation, which sends once on).
    expect(text).not.toMatch(/sends? (a |the )?(DM|message|reply)/i);
    expect(text).toMatch(/doesn't message your customers itself/);
    expect(text).toMatch(/does nothing until you confirm it and it's on/);
    expect(text).toMatch(/Keep approvals on in your AI app/);
    expect(text).toMatch(/waits for your yes/);
  });

  it("with reduced motion the script leaves the final state as rendered", () => {
    vi.stubGlobal("matchMedia", reducedMotion(true));
    const { container } = render(<AiApps />);
    const stop = startLandingMotion(container);
    const scene = container.querySelector<HTMLElement>("[data-mh]")!;
    expectFinal(scene);
    // The scene's script never even watches it.
    expect(DrivenObserver.last).toBeNull();
    stop();
  });

  it("a scene already on screen when the script arrives is never touched", () => {
    const { container } = render(<AiApps />);
    const scene = container.querySelector<HTMLElement>("[data-mh]")!;
    const stop = aiApps(container);
    expect(bandObserver().target).toBe(container.querySelector("section#ai-apps"));
    bandObserver().fire(200, true);
    expectFinal(scene);
    expect(bandObserver().disconnected).toBe(true);
    expect(sceneObserver().target).toBeNull();
    stop();
  });

  it("a scene below the viewport waits hidden in place, then plays once to the final state", () => {
    vi.useFakeTimers();
    const { container } = render(<AiApps />);
    const scene = container.querySelector<HTMLElement>("[data-mh]")!;
    const stop = aiApps(container);
    bandObserver().fire(1600, false);
    expect(scene).toHaveAttribute("data-live");
    expect(scene).not.toHaveAttribute("data-mh-ok");
    expect(scene.querySelectorAll(".mh-step.on")).toHaveLength(0);

    expect(sceneObserver().target).toBe(scene);
    sceneObserver().fire(400, true);
    vi.advanceTimersByTime(AI_APPS_TIMELINE[1].at);
    expect([...scene.querySelectorAll<HTMLElement>(".mh-step.on")].map((el) => el.dataset.s)).toEqual(["0", "1"]);
    vi.advanceTimersByTime(AI_APPS_TIMELINE[2].at - AI_APPS_TIMELINE[1].at);
    expect(scene.querySelector("[data-mh-btn]")).toHaveClass("press");
    vi.advanceTimersByTime(AI_APPS_TIMELINE.at(-1)!.at);
    expect(scene).toHaveAttribute("data-mh-ok");
    expect(scene.querySelector("[data-mh-btn]")).not.toHaveClass("press");
    expect(scene.querySelectorAll(".mh-step.on")).toHaveLength(5);
    // Under 5 seconds in all (WCAG 2.2.2), so it needs no pause control.
    expect(AI_APPS_TIMELINE.at(-1)!.at).toBeLessThan(5000);

    // Stopping the script restores the server's final state.
    stop();
    expectFinal(scene);
  });

  it("a scene scrolled past (above the viewport) stays as rendered", () => {
    const { container } = render(<AiApps />);
    const scene = container.querySelector<HTMLElement>("[data-mh]")!;
    const stop = aiApps(container);
    bandObserver().fire(-900, false);
    expectFinal(scene);
    stop();
  });
});
