import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Callout } from "./Callout";
import { TocNav } from "./TocNav";
import { startTocSpy } from "./toc-spy";

type Entry = { target: Element; isIntersecting: boolean; boundingClientRect: { top: number }; rootBounds: { bottom: number } };

/** A stand-in IntersectionObserver the test drives by hand. */
let report: (entries: Entry[]) => void = () => {};
let observed: Element[] = [];
class FakeObserver {
  constructor(callback: (entries: Entry[]) => void) {
    report = callback;
  }
  observe(target: Element) {
    observed.push(target);
  }
  disconnect() {
    observed = [];
  }
}

function page() {
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

const entry = (id: string, top: number, isIntersecting = false): Entry => ({
  target: document.getElementById(id)!,
  isIntersecting,
  boundingClientRect: { top },
  rootBounds: { bottom: 300 },
});

afterEach(() => {
  vi.unstubAllGlobals();
  observed = [];
});

describe("the table of contents (C-159)", () => {
  it("links each section by id", () => {
    page();
    expect(screen.getByRole("navigation", { name: "On this page" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Two" }).getAttribute("href")).toBe("#two");
  });

  it("marks the last section that has reached the top band, and steps the progress without scroll timelines", () => {
    vi.stubGlobal("IntersectionObserver", FakeObserver);
    vi.stubGlobal("CSS", { supports: () => false });
    page();
    const stop = startTocSpy();
    expect(observed.map((el) => el.id)).toEqual(["one", "two"]);

    report([entry("one", 800), entry("two", 1600)]);
    expect(document.querySelector("[aria-current]")).toBeNull();

    report([entry("one", 100, true)]);
    expect(screen.getByRole("link", { name: "One" }).getAttribute("aria-current")).toBe("location");
    expect((document.querySelector("[data-toc-progress]") as HTMLElement).style.getPropertyValue("--toc-p")).toBe("0.5");

    report([entry("one", -400, true), entry("two", 120, true)]);
    expect(screen.getByRole("link", { name: "Two" }).getAttribute("aria-current")).toBe("location");
    expect(screen.getByRole("link", { name: "One" }).getAttribute("aria-current")).toBeNull();
    expect((document.querySelector("[data-toc-progress]") as HTMLElement).style.getPropertyValue("--toc-p")).toBe("1");

    stop();
    expect(observed).toEqual([]);
  });

  it("leaves the progress to CSS where the browser has scroll timelines", () => {
    vi.stubGlobal("IntersectionObserver", FakeObserver);
    vi.stubGlobal("CSS", { supports: () => true });
    page();
    startTocSpy();
    report([entry("one", 100, true), entry("two", 900)]);
    expect((document.querySelector("[data-toc-progress]") as HTMLElement).style.getPropertyValue("--toc-p")).toBe("");
  });
});

describe("callouts (C-159)", () => {
  it("name their kind, or the given title", () => {
    render(
      <>
        <Callout tone="tip">
          <p>A</p>
        </Callout>
        <Callout tone="means">
          <p>B</p>
        </Callout>
        <Callout title="Two mistakes to avoid">
          <p>C</p>
        </Callout>
      </>,
    );
    expect(screen.getByRole("complementary", { name: "Tip" })).toBeTruthy();
    expect(screen.getByRole("complementary", { name: "What this means for you" })).toBeTruthy();
    expect(screen.getByRole("complementary", { name: "Two mistakes to avoid" })).toBeTruthy();
  });
});
