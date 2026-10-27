import { readdirSync } from "node:fs";
import { join } from "node:path";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { THEME_INIT_SCRIPT, THEMED_ROUTE } from "@/lib/theme";

vi.mock("next/font/google", () => ({
  Geist: () => ({ variable: "geist-sans" }),
  Geist_Mono: () => ({ variable: "geist-mono" }),
}));
vi.mock("@clerk/nextjs", () => ({
  ClerkProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useAuth: () => ({ isLoaded: false, isSignedIn: undefined }),
}));
vi.mock("@/components/ui/sonner", () => ({ Toaster: () => null }));
vi.mock("@/components/ui/tooltip", () => ({ TooltipProvider: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/components/theme/ThemeSync", () => ({ ThemeSync: () => null }));
vi.mock("@/styles/globals.css", () => ({}));

import RootLayout, { viewport } from "./layout";

describe("the root layout (C-129)", () => {
  const html = renderToStaticMarkup(<RootLayout params={Promise.resolve({})}>{<main>page</main>}</RootLayout>);

  it("renders Dark by default and carries no dark class, so a light choice isn't fought by one", () => {
    expect(html).toContain('data-theme="dark"');
    expect(html).not.toMatch(/<html[^>]*class="[^"]*\bdark\b/);
  });

  it("sets the saved choice before first paint with a script in <head>, without reading cookies on the server", () => {
    const head = html.slice(html.indexOf("<head>"), html.indexOf("</head>"));
    expect(head).toContain(THEME_INIT_SCRIPT);
    // The layout is shared with the static marketing pages; cookies() would make them dynamic.
    expect(RootLayout.toString()).not.toContain("cookies");
  });

  it("starts the browser bar on the dark canvas; ThemeSync moves it for Light", () => {
    expect(viewport.themeColor).toBe("#131520");
  });
});

describe("which routes follow the member's theme (C-129)", () => {
  const segments = (group: string) =>
    readdirSync(join(__dirname, group), { withFileTypes: true })
      .filter((entry) => entry.isDirectory() && !entry.name.startsWith("[") && !entry.name.startsWith("("))
      .map((entry) => `/${entry.name}`);

  it.each(["(clerk)/(app)", "(clerk)/(auth)", "(dev)"])("every top-level route in %s follows the cookie", (group) => {
    for (const path of segments(group)) expect(THEMED_ROUTE.test(path), path).toBe(true);
  });

  it("no public page does (the marketing site stays dark)", () => {
    for (const path of segments("(marketing)")) expect(THEMED_ROUTE.test(path), path).toBe(false);
    expect(THEMED_ROUTE.test("/")).toBe(false);
  });
});
