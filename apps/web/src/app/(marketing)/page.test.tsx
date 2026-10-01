import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { HERO_TITLE } from "@/components/marketing/Hero";
import { SHOTS } from "@/components/marketing/shots";
import { FAQ } from "@/lib/marketing/faq";
import { plansFetch, plansFixture } from "@/test/plans";

import HomePage, { metadata, revalidate } from "./page";

function jsonLd(container: HTMLElement) {
  const script = container.querySelector('script[type="application/ld+json"]');
  return JSON.parse(script?.textContent ?? "null") as Record<string, unknown>;
}

/** jsdom has no IntersectionObserver; nothing is ever on screen here, so effects stay idle. */
class IdleObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return [];
  }
}

describe("the landing page", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.socialhood.test");
    vi.stubEnv("NEXT_PUBLIC_SITE_URL", "https://socialhood.example");
    vi.stubGlobal("IntersectionObserver", IdleObserver);
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
    // One h1, named in full for screen readers; the cycling word is decorative.
    const h1 = screen.getByRole("heading", { level: 1 });
    expect(h1).toHaveAccessibleName(HERO_TITLE);
    expect(h1.querySelector("[data-flip-words]")).toHaveAttribute("aria-hidden", "true");
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent)).toEqual([
      "Built on Meta's official APIs",
      "Everything your customer conversations need",
      "Set up in three steps",
      "Comment LINK, get the link in a DM",
      "Replies in English, Hindi and Hinglish",
      "Start free, upgrade when you grow",
      "Your customers' messages, handled with care",
      "Common questions",
      "Bring every customer conversation into one inbox",
    ]);
    for (const id of ["features", "how-it-works", "pricing", "faq"]) {
      expect(container.querySelector(`section#${id}`)).not.toBeNull();
    }

    // Hero: the two ways in, and the real product, labelled as example data.
    expect(screen.getAllByRole("link", { name: /Start free/ })[0]).toHaveAttribute("href", "/sign-up");
    expect(screen.getByRole("link", { name: "See how it works" })).toHaveAttribute("href", "#how-it-works");
    expect(screen.getByRole("img", { name: SHOTS.inbox.alt })).toBeInTheDocument();
    expect(screen.getByText(/The Social Hood inbox with example data\. The shop, people and messages are made up\./)).toBeInTheDocument();
    expect(screen.getByText("Official Meta APIs", { selector: "li" })).toBeInTheDocument();

    // Features and product rules.
    expect(screen.getByRole("heading", { name: "Ask Social Hood" })).toBeInTheDocument();
    expect(screen.getByText("Never sends, changes or deletes anything by itself")).toBeInTheDocument();
    expect(screen.getByText("Illustrations with example data.")).toBeInTheDocument();
    expect(screen.getByText("Coming later")).toBeInTheDocument();

    // How it works: three steps, each with a real screen.
    const how = within(container.querySelector("section#how-it-works") as HTMLElement);
    expect(how.getAllByRole("heading", { level: 3 }).map((h) => h.textContent)).toEqual([
      "Step 1: Connect your accounts",
      "Step 2: Add your knowledge",
      "Step 3: Let the AI draft or reply",
    ]);
    for (const shot of [SHOTS.connect, SHOTS.knowledge, SHOTS.aiDraft]) expect(how.getByRole("img", { name: shot.alt })).toBeInTheDocument();

    // The automation showcase: tap first, and the follow nudge is never a condition.
    expect(screen.getByRole("heading", { name: "Step 3: Tap first" })).toBeInTheDocument();
    expect(screen.getByText(/never a condition for getting the link/)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: SHOTS.automationPreview.alt })).toBeInTheDocument();

    // Languages: the examples carry their language for screen readers.
    expect(container.querySelector('[lang="hi"]')?.textContent).toMatch(/[ऀ-ॿ]/);
    expect(container.querySelector('[lang="hi-Latn"]')).not.toBeNull();
    expect(screen.getByText(/Example replies for a made-up shop/)).toBeInTheDocument();

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

  it("claims nothing we don't have: no testimonials, logos, user counts, ratings, made-up metrics or certifications", async () => {
    vi.stubGlobal("fetch", vi.fn(plansFetch(plansFixture())));
    const { container } = render(await HomePage());
    const text = container.textContent ?? "";
    expect(text).not.toMatch(
      /trusted by|testimonial|customers love|loved by|as seen (on|in)|\d[\d,.]*\+?\s?k?\+? (businesses|users|customers|brands|sellers|shops|creators|teams)|★|⭐|\bratings?\b|\d+ reviews?|customer reviews|SOC ?2|ISO 27001|HIPAA|GDPR[- ]compliant|\bHSM\b|uptime|99\.9|\d+(\.\d+)?\s?[x×] (faster|more)|\d+% (faster|more|increase|higher|of (businesses|customers|users))|(save|saves) \d+ hours?|#1\b|best[- ]in[- ]class|award/i,
    );
    // Logos are only the platforms we connect to; no customer logos.
    for (const image of container.querySelectorAll("img")) expect(image.getAttribute("src")).toMatch(/marketing%2F|\/marketing\//);
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
    expect(pricing.getByText(/Prices couldn't be loaded just now/)).toBeInTheDocument();
    expect(container.querySelector("section#pricing")?.textContent).not.toMatch(/[$₹€£]\s?\d/);
    expect(jsonLd(container)).not.toHaveProperty("offers");
  });

  it("without an API address it doesn't call out at all, and still lists the plans", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "");
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    const { container } = render(await HomePage());
    expect(fetcher).not.toHaveBeenCalled();
    const pricing = within(container.querySelector("section#pricing") as HTMLElement);
    expect(pricing.getByRole("heading", { level: 3, name: "Pro" })).toBeInTheDocument();
    expect(pricing.getAllByText("Coming soon").length).toBeGreaterThan(0);
  });

  it("is revalidated hourly and has its own title, description and canonical URL", () => {
    expect(revalidate).toBe(3600);
    expect(metadata.title).toEqual({ absolute: "Social Hood · AI inbox and automations for Instagram and WhatsApp" });
    expect(metadata.alternates?.canonical).toBe("/");
    expect(metadata.openGraph).toMatchObject({ url: "/", siteName: "Social Hood" });
    expect(metadata.twitter).toMatchObject({ card: "summary_large_image" });
  });
});
