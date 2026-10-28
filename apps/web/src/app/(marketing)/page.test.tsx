import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { HERO_SCENE_LABEL, HERO_TITLE } from "@/components/marketing/landing/Hero";
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
    // One h1, the headline.
    const h1 = screen.getByRole("heading", { level: 1 });
    expect(h1).toHaveAccessibleName(HERO_TITLE);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent)).toEqual([
      "AI replies from your own knowledge",
      "Comment LINK, get the link in a DM",
      "Let the AI draft or reply",
      "Everything your customer conversations need",
      "Connects to where your customers are",
      "Your customers' messages, handled with care",
      "Start free, upgrade when you grow",
      "Common questions",
      "Bring every customer conversation into one inbox",
    ]);
    for (const id of ["how-it-works", "automations", "modes", "features", "integrations", "pricing", "faq"]) {
      expect(container.querySelector(`section#${id}`)).not.toBeNull();
    }

    // Hero: the two ways in, the facts, and the scene as one labelled picture of example data.
    expect(screen.getAllByRole("link", { name: /Start free/ })[0]).toHaveAttribute("href", "/sign-up");
    expect(screen.getByRole("link", { name: "See how it works" })).toHaveAttribute("href", "#how-it-works");
    expect(screen.getByText("Official Meta APIs", { selector: "li" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: HERO_SCENE_LABEL })).toBeInTheDocument();
    // The server renders the sorted inbox: what needs a person comes first.
    const tags = [...container.querySelectorAll(".note .tag")].map((tag) => tag.textContent);
    expect(tags.slice(0, 2)).toEqual(["Needs you", "Needs you"]);

    // The strip's numbers come from the plan table.
    expect(screen.getByRole("region", { name: "The product in numbers" })).toHaveTextContent("200 AI credits");

    // How it works: the draft cites the knowledge it used, and a gap goes to a person.
    const how = within(container.querySelector("section#how-it-works") as HTMLElement);
    expect(how.getByText("Price list, line 1")).toBeInTheDocument();
    expect(how.getByText(/the AI doesn't guess/)).toBeInTheDocument();
    expect(how.getByText("Knowledge gap: bulk orders")).toBeInTheDocument();

    // Automations: tap first, and the follow nudge is never a condition; the keyword is editable.
    const automations = within(container.querySelector("section#automations") as HTMLElement);
    expect(automations.getByText("Tap first")).toBeInTheDocument();
    expect(automations.getByText(/Never a condition for getting the link/)).toBeInTheDocument();
    expect(automations.getByRole("textbox", { name: "The keyword is yours" })).toHaveValue("LINK");

    // Modes: a pressed Suggest, with Auto marked Pro, and the three setup steps.
    const modes = within(container.querySelector("section#modes") as HTMLElement);
    expect(modes.getByRole("button", { name: "Suggest" })).toHaveAttribute("aria-pressed", "true");
    expect(modes.getByRole("button", { name: /Auto/ })).toHaveTextContent("Pro");
    expect(modes.getAllByRole("heading", { level: 3 }).map((h) => h.textContent)).toEqual([
      "Connect your accounts",
      "Add your knowledge",
      "Let the AI draft or reply",
    ]);

    // Features and product rules.
    expect(screen.getByRole("heading", { name: "Ask Amplychat" })).toBeInTheDocument();
    expect(screen.getByText("Never sends, changes or deletes anything by itself")).toBeInTheDocument();
    // Integrations: each with an honest status.
    const integrations = within(container.querySelector("section#integrations") as HTMLElement);
    expect(integrations.getAllByRole("heading", { level: 3 }).map((h) => h.textContent)).toEqual([
      "Instagram",
      "WhatsApp",
      "Website chat",
      "Facebook Pages",
      "Live comments and ad replies",
      "Shopify",
      "Razorpay and UPI",
      "Google Sheets",
      "Zapier and the public API",
    ]);
    expect(integrations.getByText("With our Shopify app listing")).toBeInTheDocument();
    expect(integrations.getAllByText("With Meta's approval")).toHaveLength(2);
    expect(integrations.getAllByText("Official API")).toHaveLength(2);
    // Insights wait for a permission production doesn't ask for yet.
    expect(integrations.getByText(/Post insights follow Meta's approval/)).toBeInTheDocument();

    // No language marketing (C-155).
    expect(container.textContent).not.toMatch(/Hindi|Hinglish/);

    // Pricing from the API.
    const pricing = within(container.querySelector("section#pricing") as HTMLElement);
    expect(pricing.getByText("₹999")).toBeInTheDocument();

    // FAQ: every question, as a native disclosure.
    expect(container.querySelectorAll("section#faq details")).toHaveLength(FAQ.length);
    expect(screen.getByRole("heading", { level: 3, name: "Will the AI make things up?" })).toBeInTheDocument();

    // The closing claims Pro's trial only while Pro is on sale.
    expect(screen.getByText("7-day trial of Pro")).toBeInTheDocument();

    // Structured data with only true fields, and the FAQ exactly as written on the page.
    const graph = jsonLd(container)["@graph"] as Record<string, unknown>[];
    expect(graph.map((node) => node["@type"])).toEqual(["Organization", "WebSite", "SoftwareApplication", "FAQPage"]);
    expect(graph[0]).toMatchObject({
      name: "Amplychat",
      url: "https://socialhood.example/",
      logo: "https://socialhood.example/icons/icon-512.png",
      email: "support@amplychat.com",
    });
    expect(graph[0]).not.toHaveProperty("sameAs");
    expect(graph[1]).toMatchObject({ url: "https://socialhood.example/", publisher: { "@id": "https://socialhood.example/#organization" } });
    const faq = container.querySelectorAll("section#faq details");
    const entities = graph[3].mainEntity as { name: string; acceptedAnswer: { text: string } }[];
    expect(entities).toHaveLength(FAQ.length);
    entities.forEach((entity, index) => {
      expect(faq[index].querySelector("summary")?.textContent).toBe(entity.name);
      expect(faq[index].querySelector("p")?.textContent).toBe(entity.acceptedAnswer.text);
    });
    const data = graph[2];
    expect(data).toMatchObject({ "@type": "SoftwareApplication", name: "Amplychat", url: "https://socialhood.example/" });
    expect(data.offers).toEqual([
      expect.objectContaining({ name: "Free", price: "0", priceCurrency: "INR" }),
      expect.objectContaining({ name: "Pro", price: "999.00", priceCurrency: "INR" }),
    ]);
    expect(data).not.toHaveProperty("aggregateRating");
    expect(data).not.toHaveProperty("review");
  });

  it("C-149: with Pro not on sale, the closing makes no trial claim and Free is the plan to start on", async () => {
    const items = plansFixture().items.map((offer) => (offer.plan === "pro" ? { ...offer, available: false, price: null } : offer));
    vi.stubGlobal("fetch", vi.fn(plansFetch({ items })));
    const { container } = render(await HomePage());
    expect(screen.queryByText(/trial of Pro/)).toBeNull();
    expect(container.querySelector("section#pricing .plan.main h3")?.textContent).toBe("Free");
  });

  it("claims nothing we don't have: no testimonials, logos, user counts, ratings, made-up metrics or certifications", async () => {
    vi.stubGlobal("fetch", vi.fn(plansFetch(plansFixture())));
    const { container } = render(await HomePage());
    const text = container.textContent ?? "";
    expect(text).not.toMatch(
      /trusted by|testimonial|customers love|loved by|as seen (on|in)|\d[\d,.]*\+?\s?k?\+? (businesses|users|customers|brands|sellers|shops|creators|teams)|★|⭐|\bratings?\b|\d+ reviews?|customer reviews|SOC ?2|ISO 27001|HIPAA|GDPR[- ]compliant|\bHSM\b|uptime|99\.9|\d+(\.\d+)?\s?[x×] (faster|more)|\d+% (faster|more|increase|higher|of (businesses|customers|users))|(save|saves) \d+ hours?|#1\b|best[- ]in[- ]class|award/i,
    );
    // No customer logos: the page has no images at all; its scenes are markup.
    expect(container.querySelectorAll("img")).toHaveLength(0);
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
    // A site deployed without the API reads the same: no "couldn't load" notice, no blanks or "null".
    expect(pricing.queryByText(/couldn't be loaded/)).toBeNull();
    expect(container.querySelector("section#pricing")?.textContent).not.toMatch(/\bnull\b|undefined|NaN/);
    expect(container.querySelector("section#pricing")?.textContent).not.toMatch(/[$₹€£]\s?\d/);
    const graph = jsonLd(container)["@graph"] as Record<string, unknown>[];
    expect(graph.find((node) => node["@type"] === "SoftwareApplication")).not.toHaveProperty("offers");
  });

  it("without an API address it doesn't call out at all, and still lists the plans", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "");
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    const { container } = render(await HomePage());
    expect(fetcher).not.toHaveBeenCalled();
    const pricing = within(container.querySelector("section#pricing") as HTMLElement);
    expect(pricing.getByRole("heading", { level: 3, name: "Pro" })).toBeInTheDocument();
    expect(pricing.getByText(/Max:/).closest("p")).toHaveTextContent("isn't available to buy yet");
  });

  it("is revalidated hourly and has its own title, description and canonical URL", () => {
    expect(revalidate).toBe(3600);
    expect(metadata.title).toEqual({ absolute: "Amplychat · AI inbox for Instagram and WhatsApp" });
    expect(metadata.alternates?.canonical).toBe("/");
    expect(metadata.openGraph).toMatchObject({ url: "/", siteName: "Amplychat" });
    expect(metadata.twitter).toMatchObject({ card: "summary_large_image" });
  });
});
