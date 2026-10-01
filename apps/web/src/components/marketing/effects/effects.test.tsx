import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// A prefers-reduced-motion the tests can switch, read by motion ("(prefers-reduced-motion)") and
// by ScrollReveal ("(prefers-reduced-motion: reduce)"); and an IntersectionObserver that reports
// what each test says is on screen.
const env = vi.hoisted(() => {
  const state = { reduce: true, onScreen: true, listeners: [] as (() => void)[], observers: [] as { callback: IntersectionObserverCallback; targets: Element[] }[] };
  const reducedMotionQuery = {
    get matches() {
      return state.reduce;
    },
    media: "(prefers-reduced-motion)",
    onchange: null,
    addEventListener: (_: string, listener: () => void) => state.listeners.push(listener),
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  };
  window.matchMedia = ((query: string) =>
    query.includes("prefers-reduced-motion")
      ? reducedMotionQuery
      : { ...reducedMotionQuery, media: query, matches: false }) as unknown as typeof window.matchMedia;

  class FakeIntersectionObserver {
    targets: Element[] = [];
    constructor(private callback: IntersectionObserverCallback) {
      state.observers.push({ callback, targets: this.targets });
    }
    observe(target: Element) {
      this.targets.push(target);
      if (state.onScreen) {
        this.callback([{ target, isIntersecting: true, intersectionRatio: 1 } as unknown as IntersectionObserverEntry], this as unknown as IntersectionObserver);
      }
    }
    unobserve() {}
    disconnect() {}
    takeRecords() {
      return [];
    }
    root = null;
    rootMargin = "";
    thresholds = [];
  }
  (window as unknown as { IntersectionObserver: unknown }).IntersectionObserver = FakeIntersectionObserver;

  return {
    state,
    setReduce(value: boolean) {
      state.reduce = value;
      for (const listener of state.listeners) listener();
    },
  };
});

import { FlipWords } from "./flip-words";
import { LampGlow } from "./lamp";
import { MovingBorderFrame } from "./moving-border";
import { NavBody, Navbar } from "./resizable-navbar";
import { ScrollReveal } from "./ScrollReveal";
import { Spotlight } from "./spotlight-new";
import { TextGenerateEffect } from "./text-generate-effect";

const WORDS = ["DMs", "comments", "leads"];

/** The word FlipWords shows (the others are invisible spacers that keep its width). */
function shownWords(container: HTMLElement) {
  return [...container.querySelectorAll("[data-flip-words] > span:not(.invisible)")].map((el) => el.textContent);
}

beforeEach(() => {
  env.state.onScreen = true;
  env.state.observers.length = 0;
});

afterEach(() => {
  vi.useRealTimers();
  env.setReduce(true);
  delete document.documentElement.dataset.revealArmed;
});

describe("FlipWords", () => {
  it("server-renders the first word, hidden from screen readers, with room for the longest", () => {
    const { container } = render(<FlipWords words={WORDS} />);
    const root = container.querySelector("[data-flip-words]") as HTMLElement;
    expect(root).toHaveAttribute("aria-hidden", "true");
    expect(shownWords(container)).toEqual(["DMs"]);
    expect(root.querySelectorAll(".invisible")).toHaveLength(3);
  });

  it("with reduced motion it never changes word", () => {
    vi.useFakeTimers();
    const { container } = render(<FlipWords words={WORDS} interval={1000} />);
    act(() => vi.advanceTimersByTime(10_000));
    expect(shownWords(container)).toEqual(["DMs"]);
  });

  it("otherwise it moves to the next word while on screen", () => {
    env.setReduce(false);
    vi.useFakeTimers();
    const { container } = render(<FlipWords words={WORDS} interval={1000} firstDelay={3000} />);
    act(() => vi.advanceTimersByTime(2900));
    expect(shownWords(container)).toEqual(["DMs"]);
    act(() => vi.advanceTimersByTime(200));
    expect(shownWords(container)).toContain("comments");
  });

  it("and stays put while off screen", () => {
    env.setReduce(false);
    env.state.onScreen = false;
    vi.useFakeTimers();
    const { container } = render(<FlipWords words={WORDS} interval={1000} />);
    act(() => vi.advanceTimersByTime(5000));
    expect(shownWords(container)).toEqual(["DMs"]);
  });
});

describe("TextGenerateEffect", () => {
  it("with reduced motion the whole text is simply there", () => {
    const { container } = render(<TextGenerateEffect words="Yes, it's in stock in M." />);
    expect(screen.getByText("Yes, it's in stock in M.")).toBeInTheDocument();
    expect(container.querySelectorAll("span")).toHaveLength(0);
  });

  it("otherwise it builds the text word by word", () => {
    env.setReduce(false);
    const { container } = render(<TextGenerateEffect words="Yes, it's in stock" />);
    const words = [...container.querySelectorAll("p > span:not([aria-hidden])")].map((el) => el.textContent?.trim());
    expect(words).toEqual(["Yes,", "it's", "in", "stock"]);
  });
});

describe("MovingBorderFrame", () => {
  it("with reduced motion: a still brand edge, no moving glow", () => {
    const { container } = render(<MovingBorderFrame>Pro</MovingBorderFrame>);
    expect(screen.getByText("Pro")).toBeInTheDocument();
    expect(container.querySelector("[data-effect=moving-border]")).toBeNull();
    expect(container.firstElementChild).toHaveClass("bg-brand-line");
  });

  it("otherwise the glow runs only while the card is on screen", () => {
    env.setReduce(false);
    const shown = render(<MovingBorderFrame>Pro</MovingBorderFrame>);
    expect(shown.container.querySelector("[data-effect=moving-border]")).toHaveAttribute("aria-hidden", "true");
    shown.unmount();

    env.state.onScreen = false;
    const hidden = render(<MovingBorderFrame>Pro</MovingBorderFrame>);
    expect(hidden.container.querySelector("[data-effect=moving-border]")).toBeNull();
  });
});

describe("ScrollReveal", () => {
  function place(element: HTMLElement, top: number) {
    element.getBoundingClientRect = () => ({ top, bottom: top + 100, left: 0, right: 100, width: 100, height: 100, x: 0, y: top, toJSON: () => ({}) });
  }

  const at = (top: number) => (element: HTMLDivElement | null) => {
    if (element) place(element, top);
  };

  // ScrollReveal last: its layout effect then runs after the elements' refs have placed them.
  function page() {
    return render(
      <>
        <div data-reveal data-testid="above" ref={at(10)} />
        <div data-reveal data-testid="below" ref={at(5000)} />
        <ScrollReveal />
      </>,
    );
  }

  it("with reduced motion nothing is ever hidden", () => {
    page();
    expect(document.documentElement.dataset.revealArmed).toBeUndefined();
  });

  it("shows what is on screen at once and the rest when it scrolls into view", () => {
    env.setReduce(false);
    env.state.onScreen = false;
    page();
    expect(document.documentElement).toHaveAttribute("data-reveal-armed");
    expect(screen.getByTestId("above")).toHaveAttribute("data-revealed");
    const below = screen.getByTestId("below");
    expect(below).not.toHaveAttribute("data-revealed");

    const observer = env.state.observers.at(-1);
    act(() => observer?.callback([{ target: below, isIntersecting: true } as unknown as IntersectionObserverEntry], {} as IntersectionObserver));
    expect(below).toHaveAttribute("data-revealed");
  });

  it("disarms when the page goes", () => {
    env.setReduce(false);
    const view = page();
    view.unmount();
    expect(document.documentElement.dataset.revealArmed).toBeUndefined();
  });
});

describe("the resizable navbar", () => {
  it("floats once the page has scrolled past the threshold", () => {
    render(
      <Navbar threshold={64}>
        <NavBody>links</NavBody>
      </Navbar>,
    );
    const header = screen.getByRole("banner");
    expect(header).not.toHaveAttribute("data-floating");
    act(() => {
      Object.defineProperty(window, "scrollY", { value: 200, configurable: true });
      window.dispatchEvent(new Event("scroll"));
    });
    expect(header).toHaveAttribute("data-floating");
    act(() => {
      Object.defineProperty(window, "scrollY", { value: 0, configurable: true });
      window.dispatchEvent(new Event("scroll"));
    });
    expect(header).not.toHaveAttribute("data-floating");
  });

  it("changes instantly with reduced motion (CSS)", () => {
    render(
      <Navbar>
        <NavBody>links</NavBody>
      </Navbar>,
    );
    expect(screen.getByText("links")).toHaveClass("motion-reduce:transition-none");
  });
});

describe("decorative effects", () => {
  it("are hidden from assistive technology and animate only without reduced motion", () => {
    const spotlight = render(<Spotlight />).container.firstElementChild as HTMLElement;
    expect(spotlight).toHaveAttribute("aria-hidden", "true");
    expect(spotlight.innerHTML).toMatch(/motion-safe:animate-\[sh-drift/);
    expect(spotlight.innerHTML).not.toMatch(/(?<!motion-safe:)animate-\[/);

    const lamp = render(<LampGlow />).container.firstElementChild as HTMLElement;
    expect(lamp).toHaveAttribute("aria-hidden", "true");
    expect(lamp).toHaveClass("pointer-events-none");
  });
});
