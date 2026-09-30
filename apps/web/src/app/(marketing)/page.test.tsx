import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FAQ } from "@/lib/marketing/faq";
import { plansFetch, plansFixture } from "@/test/plans";

import HomePage, { metadata, revalidate } from "./page";

function jsonLd(container: HTMLElement) {
  const script = container.querySelector('script[type="application/ld+json"]');
  return JSON.parse(script?.textContent ?? "null") as Record<string, unknown>;
}

describe("the landing page", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.socialhood.test");
    vi.stubEnv("NEXT_PUBLIC_SITE_URL", "https://socialhood.example");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("renders every section in order, with the plan list's prices", async () => {
    const fetcher = vi.fn(plansFetch(plansFixture()));
    vi.stubGlobal("fetch", fetcher);
    const { container } = render(await HomePage());

    expect(fetcher).toHaveBeenCalledOnce();
    expect(screen.getByRole("main")).toHaveAttribute("id", "main");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "The AI inbox for businesses that sell on Instagram and WhatsApp",
    );
    expect(screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent)).toEqual([
      "Everything your customer conversations need",
      "Set up in three steps",
      "Built on Meta's official APIs",
      "Your customers' messages, handled with care",
      "Start free, upgrade when you grow",
      "Common questions",
      "Bring every customer conversation into one inbox",
    ]);
    for (const id of ["features", "how-it-works", "pricing", "faq"]) {
      expect(container.querySelector(`section#${id}`)).not.toBeNull();
    }

    // Hero: the two ways in, and the illustration labelled as one.
    expect(screen.getAllByRole("link", { name: /Start free/ })[0]).toHaveAttribute("href", "/sign-up");
    expect(screen.getByRole("link", { name: "See how it works" })).toHaveAttribute("href", "#how-it-works");
    expect(screen.getByRole("img", { name: /Illustration of the Social Hood inbox/ })).toBeInTheDocument();
    expect(screen.getByText(/Illustration of the inbox\. The people, messages and prices are examples\./)).toBeInTheDocument();

    // Features and product rules.
    expect(screen.getByRole("heading", { name: "Ask Social Hood" })).toBeInTheDocument();
    expect(screen.getByText("Never sends, changes or deletes anything by itself")).toBeInTheDocument();
    expect(screen.getByText(/never a condition for getting the link/)).toBeInTheDocument();
    expect(screen.getByText("Coming later")).toBeInTheDocument();

    // Pricing from the API.
    const pricing = within(container.querySelector("section#pricing") as HTMLElement);
    expect(pricing.getByText("₹999")).toBeInTheDocument();

    // FAQ: every question, as a native disclosure.
    expect(container.querySelectorAll("section#faq details")).toHaveLength(FAQ.length);
    expect(screen.getByRole("heading", { level: 3, name: "Will the AI make things up?" })).toBeInTheDocument();

    // Structured data with only true fields.
    const data = jsonLd(container);
    expect(data).toMatchObject({ "@type": "SoftwareApplication", name: "Social Hood", url: "https://socialhood.example/" });
    expect(data.offers).toEqual([
      expect.objectContaining({ name: "Free", price: "0", priceCurrency: "INR" }),
      expect.objectContaining({ name: "Pro", price: "999.00", priceCurrency: "INR" }),
    ]);
    expect(data).not.toHaveProperty("aggregateRating");
    expect(data).not.toHaveProperty("review");
  });

  it("claims nothing we don't have: no testimonials, logos, user counts, ratings or certifications", async () => {
    vi.stubGlobal("fetch", vi.fn(plansFetch(plansFixture())));
    const { container } = render(await HomePage());
    const text = container.textContent ?? "";
    expect(text).not.toMatch(
      /trusted by|testimonial|customers love|\d+\+? (businesses|users|customers)|★|\bratings?\b|SOC ?2|ISO 27001|HIPAA|GDPR[- ]compliant|\bHSM\b|uptime|99\.9/i,
    );
  });

  it("when the plan list can't load: features without prices, and no offers in the structured data", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("fetch failed");
      }),
    );
    const { container } = render(await HomePage());
    const pricing = within(container.querySelector("section#pricing") as HTMLElement);
    expect(pricing.getByText("See pricing when you sign up")).toBeInTheDocument();
    expect(pricing.getByText("3 active automations")).toBeInTheDocument();
    expect(jsonLd(container)).not.toHaveProperty("offers");
  });

  it("is revalidated hourly and has its own title, description and canonical URL", () => {
    expect(revalidate).toBe(3600);
    expect(metadata.title).toEqual({ absolute: "Social Hood · AI inbox and automations for Instagram and WhatsApp" });
    expect(metadata.alternates?.canonical).toBe("/");
    expect(metadata.openGraph).toMatchObject({ url: "/", siteName: "Social Hood" });
    expect(metadata.twitter).toMatchObject({ card: "summary_large_image" });
  });
});
