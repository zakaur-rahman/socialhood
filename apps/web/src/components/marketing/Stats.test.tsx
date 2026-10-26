import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import table from "@/lib/marketing/plan-table.json";
import { CUSTOMER_LOGOS, TESTIMONIALS } from "@/lib/marketing/social-proof";

import { SocialProof } from "./SocialProof";
import { SiteFooter } from "./SiteFooter";
import { FREE, STATS, Stats } from "./Stats";

describe("the stats band", () => {
  it("reads the Free plan's allowances from the plan table", () => {
    expect(FREE.aiCredits).toBe(table.entitlements.ai_credits_monthly.free);
    expect(FREE.automations).toBe(table.entitlements.active_automations.free);
    render(<Stats />);
    const band = screen.getByRole("region", { name: "The product in numbers" });
    for (const stat of STATS) expect(band).toHaveTextContent(stat.label);
    expect(band).toHaveTextContent(String(table.entitlements.ai_credits_monthly.free));
  });
});

describe("social proof", () => {
  it("has no data yet, and renders nothing then", () => {
    expect(TESTIMONIALS).toEqual([]);
    expect(CUSTOMER_LOGOS).toEqual([]);
    const { container } = render(<SocialProof />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows a quote and a logo when there is real data", () => {
    render(
      <SocialProof
        testimonials={[{ quote: "A real quote.", name: "A. Person", role: "Owner, A Shop" }]}
        logos={[{ name: "A Shop", src: "/marketing/a-shop.svg", width: 80, height: 32 }]}
      />,
    );
    expect(screen.getByText("A real quote.")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "A Shop" })).toBeInTheDocument();
  });
});

describe("the footer wordmark", () => {
  it("is decorative: the product name from the constant, hidden from assistive technology", () => {
    const { container } = render(<SiteFooter year={2026} />);
    const mark = container.querySelector("[data-footer-wordmark]");
    expect(mark).toHaveAttribute("aria-hidden", "true");
    expect(mark?.textContent).toBe("Amplychat");
  });
});
