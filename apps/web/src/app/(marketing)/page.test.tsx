import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { HERO_SCENE_LABEL, HERO_TITLE } from "@/components/marketing/landing/Hero";
import { FAQ, FAQ_ALL } from "@/lib/marketing/faq";
import { SITE_DESCRIPTION } from "@/lib/marketing/site";
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
      "Off, Suggest or Auto, for each account",
      "Your customers' messages, handled with care",
      "Who it's for",
      "Everything your customer conversations need",
      "Set up in three steps",
      "Start free, upgrade when you grow",
      "Common questions",
      "Ready to take control of every conversation?",
    ]);
    // C-157: the order, with a night band every two or three sections; the connections sit inside Features.
    expect([...container.querySelectorAll("main > section")].map((section) => section.id || section.className)).toEqual([
      "hero",
      "how-it-works",
      "automations",
      "modes",
      "security",
      "who-its-for",
      "features",
      "setup",
      "pricing",
      "faq",
      "night close",
    ]);
    expect(container.querySelector("section#features #integrations")).not.toBeNull();
    // No labels over the headings (C-157).
    expect(container.querySelectorAll("main .kicker")).toHaveLength(0);

    // Hero: the two ways in, the facts, and the scene as one labelled picture of example data.
    expect(screen.getAllByRole("link", { name: /Start free/ })[0]).toHaveAttribute("href", "/sign-up");
    expect(within(container.querySelector("section.hero") as HTMLElement).getByRole("link", { name: "See how it works" })).toHaveAttribute("href", "#how-it-works");
    expect(screen.getByText("Official Meta APIs", { selector: "li" })).toBeInTheDocument();
    expect(screen.getByText("For small businesses and creators:")).toBeInTheDocument();
    expect(screen.getByText(/AI inbox and automations for Instagram, WhatsApp and website chat/)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: HERO_SCENE_LABEL })).toBeInTheDocument();
    // The server renders the sorted inbox: what needs a person comes first.
    const tags = [...container.querySelectorAll(".note .tag")].map((tag) => tag.textContent);
    expect(tags.slice(0, 2)).toEqual(["Needs you", "Needs you"]);

    // The strip's numbers come from the plan table, and no fact repeats the hero's (C-157).
    const strip = screen.getByRole("region", { name: "The product in numbers" });
    // It is the hero's last part (C-157 hero spacing), so a wide screen can pin it with the first screen.
    expect(container.querySelector("section.hero > section.strip:last-child")).toBe(strip);
    expect(strip).toHaveTextContent("200 AI credits");
    expect(strip).toHaveTextContent("50 website chats");
    expect(strip).not.toHaveTextContent("Official Meta APIs");

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

    // Modes: a pressed Suggest, with Auto marked Pro; the three setup steps have their own band.
    const modes = within(container.querySelector("section#modes") as HTMLElement);
    expect(modes.getByRole("button", { name: "Suggest" })).toHaveAttribute("aria-pressed", "true");
    expect(modes.getByRole("button", { name: /Auto/ })).toHaveTextContent("Pro");
    const setup = within(container.querySelector("section#setup") as HTMLElement);
    expect(setup.getAllByRole("heading", { level: 3 }).map((h) => h.textContent)).toEqual([
      "Connect your accounts",
      "Add your knowledge",
      "Let the AI draft or reply",
    ]);

    // Features and product rules: Ask Amplychat leads, the rest under three outcomes (C-157 organize).
    expect(screen.getByRole("heading", { name: "Ask Amplychat" })).toBeInTheDocument();
    expect(screen.getByText("Never sends, changes or deletes anything by itself")).toBeInTheDocument();
    const features = container.querySelector("section#features") as HTMLElement;
    const groups = [...features.querySelectorAll(".fgroup")].map((group) => ({
      title: group.querySelector("h3")?.textContent,
      items: [...group.querySelectorAll("h4")].map((h) => h.textContent?.replace(/ · Pro$/, "")),
    }));
    expect(groups).toEqual([
      { title: "Manage every conversation", items: ["Team roles and assignment", "Notifications, on your phone too"] },
      { title: "Automate the repetitive work", items: ["Scheduling, Reels and Stories", "Sequences, and broadcasts soon"] },
      {
        title: "Understand and grow",
        items: ["Analytics and the weekly report", "Comment intelligence", "Product catalogue, orders and payment links"],
      },
    ]);
    // A feature with its own page is one whole-card link; one "Go deeper" line in the section.
    expect(within(features).getByRole("link", { name: "Scheduling, Reels and Stories" })).toHaveAttribute("href", "/features/publishing");
    expect(features.querySelectorAll(".fcard-link")).toHaveLength(2);
    expect(features.querySelectorAll(".more-links")).toHaveLength(1);
    // Who it's for: the two audience pages.
    const audience = within(container.querySelector("section#who-its-for") as HTMLElement);
    expect(audience.getByRole("link", { name: "For creators" })).toHaveAttribute("href", "/for-creators");
    expect(audience.getByRole("link", { name: "For businesses" })).toHaveAttribute("href", "/for-businesses");
    // Deep links to the feature pages, the guides and the comparisons (LP-4.10).
    for (const href of [
      "/features/ai-inbox",
      "/features/comment-intelligence",
      "/features/publishing",
      "/compare",
      "/guides/comment-to-dm-automations",
      "/guides/whatsapp-business-api-vs-app",
      "/security",
    ]) {
      expect(container.querySelector(`main a[href="${href}"]`), href).not.toBeNull();
    }
    // Integrations: each with an honest status; payments are one line, not a headline item.
    const integrations = within(container.querySelector("#integrations") as HTMLElement);
    expect(integrations.getAllByRole("heading", { level: 4 }).map((h) => h.textContent)).toEqual([
      "Instagram",
      "WhatsApp",
      "Website chat",
      "Facebook Pages",
      "Live comments and ads",
      "Shopify",
      "Google Sheets",
      "Zapier and the public API",
    ]);
    expect(integrations.getByText("With our Shopify app listing")).toBeInTheDocument();
    expect(integrations.getAllByText("With Meta's approval")).toHaveLength(2);
    expect(integrations.getAllByText("Official API")).toHaveLength(2);
    // Insights wait for a permission production doesn't ask for yet.
    expect(integrations.getByText(/Post insights follow Meta's approval/)).toBeInTheDocument();
    expect(integrations.getByText(/Razorpay payment links and UPI requests/)).toBeInTheDocument();
    // The guide sits in its card's own link row, not inside the description.
    expect(integrations.getByRole("link", { name: "The WhatsApp Business API, explained" }).closest(".crow-g")).not.toBeNull();

    // No language marketing (C-155).
    expect(container.textContent).not.toMatch(/Hindi|Hinglish/);

    // Pricing from the API.
    const pricing = within(container.querySelector("section#pricing") as HTMLElement);
    expect(pricing.getByText("₹999")).toBeInTheDocument();

    // FAQ: the eight most asked, as native disclosures, and a link to every question on /faq.
    expect(FAQ.length).toBeGreaterThanOrEqual(6);
    expect(FAQ.length).toBeLessThanOrEqual(8);
    expect(FAQ_ALL.length).toBeGreaterThan(FAQ.length);
    expect(container.querySelectorAll("section#faq details")).toHaveLength(FAQ.length);
    expect(screen.getByRole("heading", { level: 3, name: "Will the AI make things up?" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "See all questions" })).toHaveAttribute("href", "/faq");

    // The closing claims Pro's trial only while Pro is on sale; two actions, no email (C-161 v2).
    expect(screen.getByText("Try Pro free for 7 days")).toBeInTheDocument();
    const close = container.querySelector("section.close") as HTMLElement;
    expect(within(close).getAllByRole("link").map((link) => link.getAttribute("href"))).toEqual(["/sign-up", "/how-it-works"]);
    expect(close.querySelector(".falling")).toBeNull();
    // C-161 v2: a still iris arc behind the heading, hidden from assistive tech; no channel line and
    // no convergence picture any more.
    expect(close.querySelector(".close-arc")).toHaveAttribute("aria-hidden");
    expect(within(close).getByRole("heading", { level: 2, name: "Ready to take control of every conversation?" })).toBeInTheDocument();
    expect(close.querySelector(".close-line")).toBeNull();
    expect(close.querySelector(".converge")).toBeNull();
    expect(close.querySelector(".mini")).toBeNull();

    // Structured data with only true fields. No FAQPage (C-162): /faq marks up these questions once.
    const graph = jsonLd(container)["@graph"] as Record<string, unknown>[];
    expect(graph.map((node) => node["@type"])).toEqual(["Organization", "WebSite", "SoftwareApplication"]);
    expect(graph[0]).toMatchObject({
      name: "Amplychat",
      url: "https://socialhood.example/",
      logo: expect.objectContaining({ url: "https://socialhood.example/icons/icon-512.png" }),
      email: "support@amplychat.com",
    });
    expect(graph[0].sameAs).toEqual(["https://www.instagram.com/amplychat_67/", "https://www.facebook.com/profile.php?id=61595928331470"]);
    expect(graph[1]).toMatchObject({ url: "https://socialhood.example/", publisher: { "@id": "https://socialhood.example/#organization" } });
    // The FAQ is still on the page, as written.
    const faq = container.querySelectorAll("section#faq details");
    expect(faq).toHaveLength(FAQ.length);
    FAQ.forEach((item, index) => {
      expect(faq[index].querySelector("summary")?.textContent).toBe(item.question);
      expect(faq[index].querySelector("p")?.textContent).toBe(item.answer);
    });
    const data = graph[2];
    expect(data).toMatchObject({ "@type": "SoftwareApplication", name: "Amplychat", url: "https://socialhood.example/" });
    expect(data.description).toBe(SITE_DESCRIPTION);
    expect(data.description).toMatch(/website chat/);
    expect(data.offers).toEqual([
      expect.objectContaining({ name: "Free", price: "0", priceCurrency: "INR" }),
      expect.objectContaining({ name: "Pro", price: "999.00", priceCurrency: "INR" }),
    ]);
    expect(data).not.toHaveProperty("aggregateRating");
    expect(data).not.toHaveProperty("review");
  });

  it("C-157 motion: the hero draws its scattered pile on the server, and the cards carry hidden icons", async () => {
    vi.stubGlobal("fetch", vi.fn(plansFetch(plansFixture())));
    const { container } = render(await HomePage());

    // The scroll-scrubbed hero is back: the pin's box, and every message placed in the pile by the server
    // (site.css draws the pile from these, so nothing jumps when the script arrives).
    const hero = container.querySelector("section.hero")!;
    expect(hero.querySelector("[data-hero-scrub] .hero-sticky h1")).not.toBeNull();
    const notes = [...hero.querySelectorAll<HTMLElement>("[data-notes] .note")];
    expect(notes).toHaveLength(8);
    for (const [i, note] of notes.entries()) {
      expect(note.style.getPropertyValue("--i")).toBe(String(i));
      for (const prop of ["--sx", "--sy", "--sr"]) expect(note.style.getPropertyValue(prop)).not.toBe("");
    }
    // Its pause control (phones) lives in the scene's own motion scope, hidden until a script binds it.
    const scope = hero.querySelector("[data-stage][data-motion-scope]")!;
    const toggle = scope.querySelector("[data-motion-toggle]");
    expect(toggle).toHaveAttribute("aria-label", "Pause the inbox animation");
    expect(toggle).toHaveAttribute("hidden");

    // Icons: server-rendered SVG in a tile, hidden from assistive tech, on every card the brief names.
    for (const selector of [".feat-lead", "#features .fgroup > h3", ".fcard", ".spec-row", ".steps > li", ".aud-card", ".crow", ".pay"]) {
      const cards = [...container.querySelectorAll(selector)];
      expect(cards.length, selector).toBeGreaterThan(0);
      for (const card of cards) {
        const tile = card.querySelector(".ico");
        expect(tile, selector).not.toBeNull();
        expect(tile).toHaveAttribute("aria-hidden");
      }
    }
    // A channel shows its own glyph in its colour (the motif); the others get an icon.
    for (const name of ["Instagram", "WhatsApp", "Website chat", "Facebook Pages"]) {
      const row = [...container.querySelectorAll(".crow")].find((c) => c.querySelector("h4")?.textContent === name)!;
      expect(row.querySelector(".ico-mark svg")).not.toBeNull();
      expect((row.querySelector(".ico-mark") as HTMLElement).style.getPropertyValue("--c")).not.toBe("");
    }
    const shopify = [...container.querySelectorAll(".crow")].find((c) => c.querySelector("h4")?.textContent === "Shopify")!;
    expect(shopify.querySelector(".ico svg")).not.toBeNull();
    // Only the AI's card wears iris.
    expect([...container.querySelectorAll(".ico-ai")].map((tile) => tile.closest(".feat-lead") !== null)).toEqual([true]);

    // The FAQ's plus is two bars (it folds into a minus as it opens); the questions stay native details.
    const faq = container.querySelector("section#faq")!;
    for (const pm of faq.querySelectorAll(".qa .pm")) expect(pm.querySelectorAll("i")).toHaveLength(2);
    expect(faq.querySelectorAll("details.qa > summary")).toHaveLength(faq.querySelectorAll("details.qa").length);
  });

  it("C-149: with Pro not on sale, the closing makes no trial claim and Free is the plan to start on", async () => {
    const items = plansFixture().items.map((offer) => (offer.plan === "pro" ? { ...offer, available: false, price: null } : offer));
    vi.stubGlobal("fetch", vi.fn(plansFetch({ items })));
    const { container } = render(await HomePage());
    expect(screen.queryByText(/Try Pro free/)).toBeNull();
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
    expect(metadata.title).toEqual({ absolute: "Amplychat · AI inbox for Instagram, WhatsApp and web chat" });
    expect(metadata.alternates?.canonical).toBe("/");
    expect(metadata.openGraph).toMatchObject({ url: "/", siteName: "Amplychat" });
    expect(metadata.twitter).toMatchObject({ card: "summary_large_image" });
  });
});
