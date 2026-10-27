import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  DEFAULT_THEME,
  THEME_COOKIE,
  THEME_INIT_SCRIPT,
  THEMED_ROUTE,
  applyThemeAttribute,
  applyThemeColor,
  parseTheme,
  readThemeCookie,
  resolveChoice,
  writeThemeCookie,
} from "./theme";

function clearCookie() {
  document.cookie = `${THEME_COOKIE}=; path=/; max-age=0`;
}

beforeEach(() => {
  clearCookie();
  document.documentElement.removeAttribute("data-theme");
});
afterEach(() => {
  clearCookie();
  document.head.querySelectorAll('meta[name="theme-color"]').forEach((meta) => meta.remove());
});

describe("the theme choice (C-129)", () => {
  it("is Dark unless a known value says otherwise", () => {
    expect(DEFAULT_THEME).toBe("dark");
    expect(parseTheme(undefined)).toBe("dark");
    expect(parseTheme(null)).toBe("dark");
    expect(parseTheme("purple")).toBe("dark");
    expect(parseTheme("light")).toBe("light");
    expect(parseTheme("system")).toBe("system");
  });

  it("resolves System by the OS preference and the others as chosen", () => {
    expect(resolveChoice("system", true)).toBe("light");
    expect(resolveChoice("system", false)).toBe("dark");
    expect(resolveChoice("dark", true)).toBe("dark");
    expect(resolveChoice("light", false)).toBe("light");
  });

  it("reads the choice from a cookie string", () => {
    expect(readThemeCookie("")).toBe("dark");
    expect(readThemeCookie("a=1; sh_theme=light; b=2")).toBe("light");
    expect(readThemeCookie("sh_theme=system")).toBe("system");
    expect(readThemeCookie("sh_theme=nonsense")).toBe("dark");
    expect(readThemeCookie("not_sh_theme=light")).toBe("dark");
  });

  it("writes the cookie site-wide for a year, readable by the script", () => {
    writeThemeCookie("light");
    expect(document.cookie).toContain("sh_theme=light");
    expect(readThemeCookie(document.cookie)).toBe("light");
  });

  it("applies the choice as data-theme", () => {
    applyThemeAttribute("light");
    expect(document.documentElement).toHaveAttribute("data-theme", "light");
  });

  it("points every theme-color meta at the canvas of the theme, dropping its media query", () => {
    const meta = document.createElement("meta");
    meta.name = "theme-color";
    meta.content = "#131520";
    meta.media = "(prefers-color-scheme: dark)";
    document.head.append(meta);
    applyThemeColor("light");
    expect(meta.content).toBe("#F5F6FB");
    expect(meta.hasAttribute("media")).toBe(false);
    applyThemeColor("dark");
    expect(meta.content).toBe("#131520");
  });
});

describe("the head script (runs before first paint)", () => {
  const run = (script: string, path = "/w/maple") => {
    window.history.replaceState(null, "", path);
    new Function(script)();
  };

  it("is plain text with no import, built from the cookie name", () => {
    expect(THEME_INIT_SCRIPT).toContain(THEME_COOKIE);
    expect(THEME_INIT_SCRIPT).not.toMatch(/import|require/);
    expect(THEME_INIT_SCRIPT.length).toBeLessThan(400);
  });

  it.each(["light", "system", "dark"] as const)("copies the %s cookie to data-theme", (choice) => {
    document.cookie = `${THEME_COOKIE}=${choice}; path=/`;
    run(THEME_INIT_SCRIPT);
    expect(document.documentElement).toHaveAttribute("data-theme", choice);
  });

  it("finds the cookie when other cookies come before it (C-150: Clerk's do, in production)", () => {
    // The browser joins cookies with "; " in the order it holds them.
    const cookie = vi
      .spyOn(document, "cookie", "get")
      .mockReturnValue(`__client_uat=1700000000; __session=abc; ${THEME_COOKIE}=light`);
    run(THEME_INIT_SCRIPT);
    expect(document.documentElement).toHaveAttribute("data-theme", "light");
    cookie.mockRestore();
  });

  it("leaves the page as rendered (Dark) with no cookie or a bad one", () => {
    run(THEME_INIT_SCRIPT);
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
    document.cookie = `${THEME_COOKIE}=sepia; path=/`;
    run(THEME_INIT_SCRIPT);
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
  });

  it.each(["/", "/pricing", "/compare/manychat", "/an-unknown-page"])(
    "pins %s dark whatever the cookie says (the public site and its 404)",
    (path) => {
      document.cookie = `${THEME_COOKIE}=light; path=/`;
      run(THEME_INIT_SCRIPT, path);
      expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    },
  );

  it.each(["/app", "/w/maple/inbox", "/sign-in", "/sign-up/verify", "/dev/tokens"])(
    "lets %s follow the cookie",
    (path) => {
      document.cookie = `${THEME_COOKIE}=light; path=/`;
      run(THEME_INIT_SCRIPT, path);
      expect(document.documentElement).toHaveAttribute("data-theme", "light");
    },
  );

  it("doesn't mistake a public path that starts like an app one", () => {
    expect(THEMED_ROUTE.test("/apple")).toBe(false);
    expect(THEMED_ROUTE.test("/websites")).toBe(false);
  });
});
