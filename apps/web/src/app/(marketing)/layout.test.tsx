import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/components/marketing/SiteHeader", () => ({ SiteHeader: () => <header>header</header> }));
vi.mock("@/components/marketing/SiteFooter", () => ({ SiteFooter: () => <footer>footer</footer> }));
vi.mock("@/components/theme/ThemePin", () => ({ ThemePin: () => null }));
vi.mock("@/components/site/site.css", () => ({}));

import { colorValue } from "@/styles/token-values";

import MarketingLayout, { viewport } from "./layout";

describe("the marketing layout (C-155)", () => {
  const html = renderToStaticMarkup(<MarketingLayout params={Promise.resolve({})}>{<main>page</main>}</MarketingLayout>);

  it("wraps the page in the site frame, whatever the app's theme", () => {
    expect(html).toMatch(/<div class="site /);
    expect(html).not.toContain("scheme-dark");
  });

  it("puts the browser bar on the site's paper", () => {
    expect(viewport.themeColor).toBe(colorValue("paper"));
  });

  it("starts with a skip link to the page's main", () => {
    expect(html).toMatch(/<a href="#main"[^>]*>Skip to content<\/a>/);
  });

  it("keeps the sticky bar's containing block to the page, so the bar leaves before the footer (C-157)", () => {
    expect(html).toMatch(/<div class="[^"]*"><header>header<\/header><div class="[^"]*"><main>page<\/main><\/div><\/div><footer>footer<\/footer>/);
  });

  it("renders no inline script (React won't run one on a client navigation; the root layout's head script pins <html> by route)", () => {
    expect(html).not.toContain("<script");
  });
});
