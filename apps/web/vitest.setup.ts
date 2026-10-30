import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => cleanup());

// next/font only works inside Next's compiler: the Google fonts the app loads are stand-ins with its variable's
// name, so a module that loads one (the public site's fonts, C-155) can be imported in a test.
vi.mock("next/font/google", () => {
  const font = (options?: { variable?: string }) => ({ className: "font", variable: options?.variable ?? "font", style: { fontFamily: "font" } });
  return { Geist: font, Geist_Mono: font, Funnel_Display: font, Funnel_Sans: font };
});

// jsdom lacks these; Radix and the media-query hook use them.
if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: true,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList;
}
if (!("ResizeObserver" in window)) {
  (window as unknown as { ResizeObserver: unknown }).ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}
