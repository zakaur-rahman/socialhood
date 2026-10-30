import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LegalContents } from "@/components/marketing/legal/LegalPage";

import { TocNav } from "./TocNav";
import { startTocSpy } from "./toc-spy";

type Entry = { target: Element; isIntersecting: boolean };

/** A stand-in IntersectionObserver the test drives by hand. */
let report: (entries: Entry[]) => void = () => {};
let observed: Element[] = [];
let options: IntersectionObserverInit | undefined;
class FakeObserver {
  constructor(callback: (entries: Entry[]) => void, init?: IntersectionObserverInit) {
    report = callback;
    options = init;
  }
  observe(target: Element) {
    observed.push(target);
  }
  disconnect() {
    observed = [];
  }
}

function stubWide(wide: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: wide, media: query, addEventListener() {}, removeEventListener() {} }));
}

/** A guide: a progress bar, the contents and two headings. */
function guide() {
  render(
    <div>
      <div data-toc-progress="" />
      <TocNav
        items={[
          { id: "one", label: "One" },
          { id: "two", label: "Two" },
        ]}
      />
      <h2 id="one">One</h2>
      <h2 id="two">Two</h2>
    </div>,
  );
}

const SECTIONS = [
  { id: "first", title: "First" },
  { id: "second", title: "Second" },
];

/** A legal page: the numbered, collapsible contents and its sections. */
function legal() {
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

const entry = (id: string, isIntersecting = false): Entry => ({ target: document.getElementById(id)!, isIntersecting });

afterEach(() => {
  vi.unstubAllGlobals();
  observed = [];
  options = undefined;
});

describe("the table of contents (C-159)", () => {
  it("links each section by id", () => {
    guide();
    expect(screen.getByRole("navigation", { name: "On this page" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Two" }).getAttribute("href")).toBe("#two");
  });

  it("numbered and collapsible (the legal pages): a disclosure named Contents, each entry with its number", () => {
    const { container } = legal();
    const nav = screen.getByRole("navigation", { name: "Contents" });
    expect(nav).toHaveClass("toc", "toc-num");
    expect(nav.querySelector("details summary")).toHaveTextContent("Contents");
    expect([...container.querySelectorAll(".toc-n")].map((n) => n.textContent)).toEqual(["1", "2"]);
    expect(screen.getByRole("link", { name: /Second/ }).getAttribute("href")).toBe("#second");
  });
});

describe("TocSpy (C-159)", () => {
  it("marks the last section that has reached the top band, and steps the progress without scroll timelines", () => {
    vi.stubGlobal("IntersectionObserver", FakeObserver);
    vi.stubGlobal("CSS", { supports: () => false });
    guide();
    const stop = startTocSpy();
    expect(observed.map((el) => el.id)).toEqual(["one", "two"]);
    expect(options?.rootMargin).toBe("100000px 0px -65% 0px");

    report([entry("one"), entry("two")]);
    expect(document.querySelector("[aria-current]")).toBeNull();

    report([entry("one", true)]);
    expect(screen.getByRole("link", { name: "One" }).getAttribute("aria-current")).toBe("location");
    expect((document.querySelector("[data-toc-progress]") as HTMLElement).style.getPropertyValue("--toc-p")).toBe("0.5");

    report([entry("one", true), entry("two", true)]);
    expect(screen.getByRole("link", { name: "Two" }).getAttribute("aria-current")).toBe("location");
    expect(screen.getByRole("link", { name: "One" }).getAttribute("aria-current")).toBeNull();
    expect((document.querySelector("[data-toc-progress]") as HTMLElement).style.getPropertyValue("--toc-p")).toBe("1");

    stop();
    expect(observed).toEqual([]);
  });

  it("leaves the progress to CSS where the browser has scroll timelines", () => {
    vi.stubGlobal("IntersectionObserver", FakeObserver);
    vi.stubGlobal("CSS", { supports: () => true });
    guide();
    startTocSpy();
    report([entry("one", true), entry("two")]);
    expect((document.querySelector("[data-toc-progress]") as HTMLElement).style.getPropertyValue("--toc-p")).toBe("");
  });

  it("marks every nav's link to the section, as the guide's two contents both show it", () => {
    vi.stubGlobal("IntersectionObserver", FakeObserver);
    render(
      <div>
        <TocNav items={[{ id: "a", label: "A" }]} label="In this guide" />
        <TocNav items={[{ id: "a", label: "A" }]} />
        <h2 id="a">A</h2>
      </div>,
    );
    startTocSpy();
    expect(observed).toHaveLength(1);
    report([entry("a", true)]);
    expect(screen.getAllByRole("link", { name: "A" }).map((link) => link.getAttribute("aria-current"))).toEqual(["location", "location"]);
  });

  it("on a legal page: watches each listed heading and marks the section being read", () => {
    vi.stubGlobal("IntersectionObserver", FakeObserver);
    stubWide(false);
    const { container } = legal();
    const stop = startTocSpy(container);
    const headings = [...container.querySelectorAll("h2")];
    expect(observed).toEqual(headings);

    const links = [...container.querySelectorAll("[data-toc] a")];
    report([entry("first", true), entry("second", true)]);
    expect(links[1]).toHaveAttribute("aria-current", "location");
    expect(links[0]).not.toHaveAttribute("aria-current");

    // Scrolled back up: the second heading is below the line again.
    report([entry("second", false)]);
    expect(links[0]).toHaveAttribute("aria-current", "location");
    expect(links[1]).not.toHaveAttribute("aria-current");
    stop();
  });

  it("opens a collapsible contents on a wide screen and leaves it closed on a narrow one", () => {
    vi.stubGlobal("IntersectionObserver", FakeObserver);
    stubWide(true);
    const wide = legal();
    startTocSpy(wide.container)();
    expect(wide.container.querySelector("details")).toHaveProperty("open", true);
    wide.unmount();

    stubWide(false);
    const narrow = legal();
    startTocSpy(narrow.container)();
    expect(narrow.container.querySelector("details")).toHaveProperty("open", false);
  });

  it("does nothing without a contents nav", () => {
    const { container } = render(<p>No contents</p>);
    expect(() => startTocSpy(container)()).not.toThrow();
  });
});
