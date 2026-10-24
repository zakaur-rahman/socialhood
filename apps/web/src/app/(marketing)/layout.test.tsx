import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { THEME_PIN_DARK_SCRIPT } from "@/lib/theme";

vi.mock("@/components/marketing/SiteHeader", () => ({ SiteHeader: () => <header>header</header> }));
vi.mock("@/components/marketing/SiteFooter", () => ({ SiteFooter: () => <footer>footer</footer> }));
vi.mock("@/components/theme/ThemePin", () => ({ ThemePin: () => null }));

import MarketingLayout from "./layout";

describe("the marketing layout (C-102)", () => {
  const html = renderToStaticMarkup(<MarketingLayout params={Promise.resolve({})}>{<main>page</main>}</MarketingLayout>);

  it("pins the dark scheme on its subtree, so the public site stays dark in a light app", () => {
    expect(html).toMatch(/<div class="scheme-dark [^"]*bg-canvas/);
  });

  it("pins <html> dark on a first load with an inline script", () => {
    expect(html).toContain(THEME_PIN_DARK_SCRIPT);
  });
});
