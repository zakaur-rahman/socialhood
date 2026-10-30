import { render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LegalContents } from "@/components/marketing/legal/LegalPage";

import { startTocSpy } from "./TocSpy";

type Callback = (entries: { target: Element; isIntersecting: boolean }[]) => void;

/** An IntersectionObserver the test drives by hand. */
function stubObserver() {
  const observers: { callback: Callback; targets: Element[]; options?: IntersectionObserverInit }[] = [];
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      targets: Element[] = [];
      constructor(callback: Callback, options?: IntersectionObserverInit) {
        observers.push({ callback, targets: this.targets, options });
      }
      observe(target: Element) {
        this.targets.push(target);
      }
      disconnect() {}
    },
  );
  return observers;
}

function stubWide(wide: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: wide, media: query, addEventListener() {}, removeEventListener() {} }));
}

const SECTIONS = [
  { id: "one", title: "First" },
  { id: "two", title: "Second" },
];

function page() {
  return render(
    <>
      <LegalContents sections={SECTIONS} />
      {SECTIONS.map((section) => (
        <section key={section.id}>
          <h2 id={section.id}>{section.title}</h2>
        </section>
      ))}
    </>,
  );
}

describe("TocSpy (C-159)", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("watches each listed section and marks the one crossing the reading band", () => {
    const observers = stubObserver();
    stubWide(false);
    const { container } = page();
    const stop = startTocSpy(container);
    const [observer] = observers;
    const sections = [...container.querySelectorAll("section")];
    expect(observer.targets).toEqual(sections);
    expect(observer.options?.rootMargin).toBe("-25% 0px -60% 0px");

    const links = [...container.querySelectorAll("[data-toc] a")];
    observer.callback([{ target: sections[1], isIntersecting: true }]);
    expect(links[1]).toHaveAttribute("aria-current", "location");
    expect(links[0]).not.toHaveAttribute("aria-current");

    // Both in the band: the earlier section wins.
    observer.callback([{ target: sections[0], isIntersecting: true }]);
    expect(links[0]).toHaveAttribute("aria-current", "location");
    expect(links[1]).not.toHaveAttribute("aria-current");
    stop();
  });

  it("opens the contents on a wide screen and leaves them closed on a narrow one", () => {
    stubObserver();
    stubWide(true);
    const wide = page();
    startTocSpy(wide.container)();
    expect(wide.container.querySelector("details")).toHaveProperty("open", true);
    wide.unmount();

    stubWide(false);
    const narrow = page();
    startTocSpy(narrow.container)();
    expect(narrow.container.querySelector("details")).toHaveProperty("open", false);
  });

  it("does nothing without a contents nav", () => {
    const { container } = render(<p>No contents</p>);
    expect(() => startTocSpy(container)()).not.toThrow();
  });
});
