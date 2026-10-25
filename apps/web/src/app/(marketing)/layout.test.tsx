import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/components/marketing/SiteHeader", () => ({ SiteHeader: () => <header>header</header> }));
vi.mock("@/components/marketing/SiteFooter", () => ({ SiteFooter: () => <footer>footer</footer> }));
vi.mock("@/components/theme/ThemePin", () => ({ ThemePin: () => null }));

import MarketingLayout from "./layout";

describe("the marketing layout (C-129)", () => {
  const html = renderToStaticMarkup(<MarketingLayout params={Promise.resolve({})}>{<main>page</main>}</MarketingLayout>);

  it("pins the dark scheme on its subtree, so the public site stays dark in a light app", () => {
    expect(html).toMatch(/<div class="scheme-dark [^"]*bg-canvas/);
  });

  it("renders no inline script (React won't run one on a client navigation; the root layout's head script pins <html> by route)", () => {
    expect(html).not.toContain("<script");
  });
});
