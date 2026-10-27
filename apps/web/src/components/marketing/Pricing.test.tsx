import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { buildPricing } from "@/lib/marketing/plans";
import { plansFixture } from "@/test/plans";

import { PRICE_AT_SIGN_UP, Pricing } from "./Pricing";

function card(name: string) {
  return screen.getByRole("heading", { level: 3, name }).closest("li") as HTMLElement;
}

/** jsdom has no IntersectionObserver; nothing is on screen, so Pro's moving glow stays idle. */
class IdleObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return [];
  }
}

describe("the pricing section", () => {
  beforeEach(() => vi.stubGlobal("IntersectionObserver", IdleObserver));
  afterEach(() => vi.unstubAllGlobals());

  it("shows the API's price in its currency, the trial and the entitlements", () => {
    render(<Pricing pricing={buildPricing(plansFixture().items)} />);
    const pro = within(card("Pro"));
    expect(pro.getByText("₹999").parentElement).toHaveTextContent(/^₹999 a month$/);
    expect(pro.getByText("7-day free trial")).toBeInTheDocument();
    expect(pro.getByText(/A card is required to start the trial/)).toBeInTheDocument();
    expect(pro.getByText("AI replies: Off, Suggest and Auto")).toBeInTheDocument();
    expect(pro.getByRole("link", { name: "Start free, then try Pro" })).toHaveAttribute("href", "/sign-up?redirect_url=%2Fapp%3Fplan%3Dpro");

    const free = within(card("Free"));
    expect(free.getByText("No card needed")).toBeInTheDocument();
    expect(free.getByText("90 days of message history")).toBeInTheDocument();
    expect(free.getByRole("link", { name: "Start free" })).toHaveAttribute("href", "/sign-up");

    const max = within(card("Max"));
    expect(max.getAllByText("Coming soon").length).toBeGreaterThan(0);
    expect(max.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.queryByText(PRICE_AT_SIGN_UP)).not.toBeInTheDocument();
  });

  it("the credits explainer uses each plan's allowance", () => {
    render(<Pricing pricing={buildPricing(plansFixture().items)} />);
    expect(screen.getByRole("heading", { name: "How AI credits work" })).toBeInTheDocument();
    expect(screen.getByText(/200 on Free and 5,000 on Pro/)).toBeInTheDocument();
    expect(screen.getByText("Suggesting a reply, or an Auto reply")).toBeInTheDocument();
  });

  it("when the API fails: features, 'See pricing when you sign up', and no price anywhere", () => {
    const { container } = render(<Pricing pricing={buildPricing(null)} />);
    expect(within(card("Pro")).getByText(PRICE_AT_SIGN_UP)).toBeInTheDocument();
    expect(within(card("Pro")).getByText("7-day free trial")).toBeInTheDocument();
    expect(within(card("Free")).getByText("3 active automations")).toBeInTheDocument();
    // Also the website deployed without the API: no "couldn't load" notice, no blanks or "null".
    expect(screen.queryByText(/couldn't be loaded/)).toBeNull();
    expect(container.textContent).not.toMatch(/[$₹€£]\s?\d/);
    expect(container.textContent).not.toMatch(/\bnull\b|undefined|NaN/);
  });

  it("only Pro, when it can be bought, gets the moving border (C-068)", () => {
    render(<Pricing pricing={buildPricing(plansFixture().items)} />);
    expect(card("Pro").querySelector("[data-frame=moving-border]")).not.toBeNull();
    expect(card("Free").querySelector("[data-frame=moving-border]")).toBeNull();
    expect(card("Max").querySelector("[data-frame=moving-border]")).toBeNull();
  });

  it("the fallback keeps the same cards: Pro framed, Max coming soon, no price", () => {
    render(<Pricing pricing={buildPricing(null)} />);
    expect(card("Pro").querySelector("[data-frame=moving-border]")).not.toBeNull();
    expect(within(card("Max")).getAllByText("Coming soon").length).toBeGreaterThan(0);
    expect(within(card("Max")).queryByRole("link")).not.toBeInTheDocument();
  });

  it("C-149: with no billing on the API yet, Pro is coming soon with its features and no trial or price", () => {
    const items = plansFixture().items.map((offer) =>
      offer.plan === "pro" ? { ...offer, available: false, price: null } : offer,
    );
    const { container } = render(<Pricing pricing={buildPricing(items)} />);
    const pro = within(card("Pro"));
    expect(pro.getAllByText("Coming soon").length).toBeGreaterThan(0);
    expect(pro.getByText(/Pro isn't available to buy yet/)).toBeInTheDocument();
    expect(pro.getByText("AI replies: Off, Suggest and Auto")).toBeInTheDocument();
    expect(pro.queryByText("7-day free trial")).not.toBeInTheDocument();
    expect(pro.queryByRole("link")).not.toBeInTheDocument();
    expect(card("Pro").querySelector("[data-frame=moving-border]")).toBeNull();
    expect(within(card("Free")).getByRole("link", { name: "Start free" })).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/[$₹€£]\s?\d/);
  });

  it("when Dodo gave no price, Pro says so instead of showing one", () => {
    render(<Pricing pricing={buildPricing(plansFixture({ proPrice: null }).items)} />);
    expect(within(card("Pro")).getByText(PRICE_AT_SIGN_UP)).toBeInTheDocument();
  });
});
