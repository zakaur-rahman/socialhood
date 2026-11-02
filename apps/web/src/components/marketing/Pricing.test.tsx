import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { buildPricing } from "@/lib/marketing/plans";
import { softwareApplicationJsonLd } from "@/lib/marketing/seo";
import { plansFixture } from "@/test/plans";

import { PRICE_AT_SIGN_UP, Pricing } from "./Pricing";

function card(name: string) {
  return screen.getByRole("heading", { level: 3, name }).closest("li") as HTMLElement;
}

/** The API's plan list with billing off: Creator can't be bought and Dodo gave it no price. */
function billingOff() {
  return plansFixture().items.map((offer) => (offer.plan === "pro" ? { ...offer, available: false, price: null } : offer));
}

describe("the pricing section (C-155 layout)", () => {
  it("shows the API's price in its currency, the trial and the entitlements", () => {
    render(<Pricing pricing={buildPricing(plansFixture().items)} />);
    const pro = within(card("Creator"));
    expect(pro.getByText("₹999")).toHaveTextContent(/^₹999 a month$/);
    expect(pro.queryByText(/when we launch/)).toBeNull();
    expect(pro.getByText("7-day free trial")).toBeInTheDocument();
    expect(pro.getByText(/A card is required to start the trial/)).toBeInTheDocument();
    expect(pro.getByText("AI Auto mode and suggestions")).toBeInTheDocument();
    expect(pro.getByText("1 each of Instagram, WhatsApp, Facebook and web chat")).toBeInTheDocument();
    expect(pro.getByRole("link", { name: "Start free, then try Creator" })).toHaveAttribute(
      "href",
      "/sign-up?redirect_url=%2Fapp%3Fplan%3Dpro",
    );

    const free = within(card("Free"));
    expect(free.getByText("No card needed")).toBeInTheDocument();
    expect(free.getByText("₹0")).toBeInTheDocument();
    expect(free.getByText("2 channels in total (Instagram, Facebook, web chat)")).toBeInTheDocument();
    expect(free.queryByText(/WhatsApp/)).toBeNull();
    expect(free.getByRole("link", { name: "Start free" })).toHaveAttribute("href", "/sign-up");

    // Business can't be bought yet: its card shows the planned price, with no link.
    const business = within(card("Business"));
    expect(business.getByTestId("planned-price-max")).toHaveTextContent(/^\$30 a month$/);
    expect(business.getByText(/Planned price, when we launch\. Business isn't available to buy yet/)).toBeInTheDocument();
    expect(business.queryByRole("link")).toBeNull();
    expect(screen.queryByText(PRICE_AT_SIGN_UP)).not.toBeInTheDocument();
  });

  it("the credits explainer uses each plan's allowance", () => {
    render(<Pricing pricing={buildPricing(plansFixture().items)} />);
    expect(screen.getByRole("heading", { name: "How AI credits work" })).toBeInTheDocument();
    expect(screen.getByText(/200 on Free, 1,500 on Creator, 5,000 on Business and 12,000 on Agency \(coming soon\)/)).toBeInTheDocument();
    expect(screen.getByText("Suggesting a reply, or an Auto reply")).toBeInTheDocument();
  });

  it("when the API fails: features, the planned prices, and no real price anywhere", () => {
    const { container } = render(<Pricing pricing={buildPricing(null)} />);
    expect(within(card("Creator")).getByTestId("planned-price-pro")).toHaveTextContent(/^\$15 a month$/);
    expect(within(card("Business")).getByTestId("planned-price-max")).toHaveTextContent(/^\$30 a month$/);
    expect(within(card("Free")).getByText("3 active automations")).toBeInTheDocument();
    // Also the website deployed without the API: no "couldn't load" notice, no blanks or "null".
    expect(screen.queryByText(/couldn't be loaded/)).toBeNull();
    expect(container.textContent).not.toMatch(/[₹€£]\s?\d/);
    // Every dollar figure on the page is a planned price or Agency's $70.
    const dollars = container.textContent?.match(/\$\d+/g) ?? [];
    expect([...dollars].sort()).toEqual(["$15", "$30", "$70"]);
    expect(container.textContent).not.toMatch(/\bnull\b|undefined|NaN/);
  });

  it("outlines the plan to start on: Creator when it can be bought", () => {
    const { container } = render(<Pricing pricing={buildPricing(plansFixture().items)} />);
    expect(container.querySelector(".plan.main h3")?.textContent).toBe("Creator");
  });

  it("C-149: with no billing on the API yet, Creator is coming soon with its features and no trial", () => {
    const { container } = render(<Pricing pricing={buildPricing(billingOff())} />);
    const pro = within(card("Creator"));
    expect(pro.getAllByText("Coming soon").length).toBeGreaterThan(0);
    expect(pro.getByText(/Creator isn't available to buy yet/)).toBeInTheDocument();
    expect(pro.getByText("AI Auto mode and suggestions")).toBeInTheDocument();
    expect(pro.queryByText("7-day free trial")).not.toBeInTheDocument();
    expect(pro.queryByRole("link")).not.toBeInTheDocument();
    expect(container.querySelector(".plan.main h3")?.textContent).toBe("Free");
    expect(within(card("Free")).getByRole("link", { name: "Start free" })).toBeInTheDocument();
  });

  it("when Dodo gave no price for a plan on sale, Creator says so instead of showing one", () => {
    render(<Pricing pricing={buildPricing(plansFixture({ proPrice: null }).items)} />);
    expect(within(card("Creator")).getByText(PRICE_AT_SIGN_UP)).toBeInTheDocument();
  });
});

describe("C-172, C-173: planned prices and the Agency card", () => {
  it("billing off: Creator shows $15 and Business $30 'a month', never as a JSON-LD offer", () => {
    const pricing = buildPricing(billingOff());
    render(<Pricing pricing={pricing} />);
    expect(screen.getByTestId("planned-price-pro")).toHaveTextContent(/^\$15 a month$/);
    expect(screen.getByTestId("planned-price-max")).toHaveTextContent(/^\$30 a month$/);
    expect(within(card("Creator")).queryByText(PRICE_AT_SIGN_UP)).toBeNull();

    const json = JSON.stringify(softwareApplicationJsonLd(pricing));
    expect(json).not.toContain('"offers"');
    expect(json).not.toMatch(/\b15\b|\b30\b|\b70\b|"price"/);
  });

  it("billing on with a Dodo price: the real price replaces the planned one", () => {
    const pricing = buildPricing(plansFixture().items);
    render(<Pricing pricing={pricing} />);
    expect(screen.queryByTestId("planned-price-pro")).toBeNull();
    expect(within(card("Creator")).getByText("₹999")).toBeInTheDocument();
    expect(within(card("Creator")).queryByText(/when we launch/)).toBeNull();
    // The real offer reaches the structured data, for Creator only; the planned Business price does not.
    const json = JSON.stringify(softwareApplicationJsonLd(pricing));
    expect(json).toContain('"price":"999.00"');
    expect(json).not.toMatch(/\b30\b|\b15\b/);
  });

  it("the Agency card: $70 a month, Coming soon, Contact us mails support, and has no checkout", () => {
    render(<Pricing pricing={buildPricing(billingOff())} />);
    const agency = within(screen.getByTestId("plan-agency"));
    expect(agency.getByRole("heading", { level: 3, name: "Agency" })).toBeInTheDocument();
    expect(agency.getByText("Coming soon")).toBeInTheDocument();
    expect(agency.getByTestId("price-agency")).toHaveTextContent(/^\$70 a month$/);
    const links = agency.getAllByRole("link");
    expect(links).toHaveLength(1);
    expect(links[0]).toHaveTextContent("Contact us");
    expect(links[0]).toHaveAttribute("href", "mailto:support@amplychat.com");
    expect(agency.queryByRole("link", { name: /start/i })).toBeNull();
    expect(agency.queryByRole("button")).toBeNull();
    expect(agency.queryByText(/free trial|a card is required/i)).toBeNull();
    expect(links[0].getAttribute("href")).not.toMatch(/sign-up|checkout|plan=/);
  });

  it("four cards with six or seven lines each, and a quiet 'Need more? Contact us.' under them", () => {
    const { container } = render(<Pricing pricing={buildPricing(billingOff())} />);
    const plans = within(screen.getByRole("list", { name: "Plans" })).getAllByRole("heading", { level: 3 });
    expect(plans.map((h) => h.textContent)).toEqual(["Free", "Creator", "Business", "Agency"]);
    const lists = container.querySelectorAll("ul.limits");
    expect(lists).toHaveLength(4);
    for (const list of lists) {
      const lines = list.querySelectorAll("li").length;
      expect(lines).toBeGreaterThanOrEqual(6);
      expect(lines).toBeLessThanOrEqual(7);
    }
    const more = screen.getByTestId("need-more");
    expect(more).toHaveTextContent("Need more? Contact us.");
    expect(within(more).getByRole("link", { name: "Contact us" })).toHaveAttribute("href", "mailto:support@amplychat.com");
  });

  it("no 'from $99', no Enterprise, no claim words, nothing about uptime, SSO or dedicated support", () => {
    const { container } = render(<Pricing pricing={buildPricing(billingOff())} />);
    const text = container.textContent ?? "";
    expect(text).not.toMatch(/from \$99|Enterprise|cheapest|\bbest\b|#1|six-month|6-month/i);
    expect(text).not.toMatch(/uptime|SSO|dedicated support/i);
  });
});
