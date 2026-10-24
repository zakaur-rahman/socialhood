import { act, render, renderHook, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { THEME_COOKIE, readThemeCookie } from "@/lib/theme";
import { useTheme } from "@/lib/use-theme";

import { ThemePin } from "./ThemePin";
import { ThemeSwitch } from "./ThemeSwitch";

type Listener = () => void;
let prefersLight = false;
let listeners: Listener[] = [];

function installMatchMedia() {
  window.matchMedia = ((query: string) => ({
    matches: query.includes("prefers-color-scheme: light") ? prefersLight : false,
    media: query,
    onchange: null,
    addEventListener: (_: string, listener: Listener) => listeners.push(listener),
    removeEventListener: (_: string, listener: Listener) => {
      listeners = listeners.filter((l) => l !== listener);
    },
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}

beforeEach(() => {
  prefersLight = false;
  listeners = [];
  installMatchMedia();
  document.cookie = `${THEME_COOKIE}=; path=/; max-age=0`;
  document.documentElement.setAttribute("data-theme", "dark");
});
afterEach(() => {
  document.cookie = `${THEME_COOKIE}=; path=/; max-age=0`;
});

describe("ThemeSwitch (C-129)", () => {
  it("offers Dark, Light and System, with Dark chosen by default", () => {
    render(<ThemeSwitch />);
    const group = screen.getByRole("radiogroup", { name: "Theme" });
    expect(group).toBeInTheDocument();
    expect(screen.getAllByRole("radio").map((radio) => radio.textContent)).toEqual(["Dark", "Light", "System"]);
    expect(screen.getByRole("radio", { name: "Dark" })).toHaveAttribute("aria-checked", "true");
  });

  it("writes the cookie and sets the attribute when a choice is made, without a reload", async () => {
    render(<ThemeSwitch />);
    await userEvent.click(screen.getByRole("radio", { name: "Light" }));
    expect(document.documentElement).toHaveAttribute("data-theme", "light");
    expect(readThemeCookie(document.cookie)).toBe("light");
    expect(screen.getByRole("radio", { name: "Light" })).toHaveAttribute("aria-checked", "true");
    await userEvent.click(screen.getByRole("radio", { name: "System" }));
    expect(document.documentElement).toHaveAttribute("data-theme", "system");
    expect(readThemeCookie(document.cookie)).toBe("system");
  });

  it("starts from the choice the head script applied", () => {
    document.documentElement.setAttribute("data-theme", "system");
    render(<ThemeSwitch />);
    expect(screen.getByRole("radio", { name: "System" })).toHaveAttribute("aria-checked", "true");
  });
});

describe("useTheme (C-129)", () => {
  it("resolves System by matchMedia and follows a change of the OS setting", () => {
    document.documentElement.setAttribute("data-theme", "system");
    const { result } = renderHook(() => useTheme());
    expect(result.current.choice).toBe("system");
    expect(result.current.resolved).toBe("dark");
    prefersLight = true;
    act(() => listeners.forEach((listener) => listener()));
    expect(result.current.resolved).toBe("light");
  });

  it("resolves Dark and Light as chosen whatever the OS says", () => {
    prefersLight = true;
    const { result } = renderHook(() => useTheme());
    expect(result.current.resolved).toBe("dark");
    act(() => result.current.setChoice("light"));
    expect(result.current.resolved).toBe("light");
    prefersLight = false;
    act(() => result.current.setChoice("dark"));
    expect(result.current.resolved).toBe("dark");
  });
});

describe("ThemePin", () => {
  it("pins <html> dark while mounted and gives the user's choice back on unmount", () => {
    document.cookie = `${THEME_COOKIE}=light; path=/`;
    document.documentElement.setAttribute("data-theme", "light");
    const view = render(<ThemePin />);
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    view.unmount();
    expect(document.documentElement).toHaveAttribute("data-theme", "light");
  });
});
