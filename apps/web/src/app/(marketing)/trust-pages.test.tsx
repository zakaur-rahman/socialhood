import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SiteFooter } from "@/components/marketing/SiteFooter";
import { CHANGELOG, CHANGELOG_AREAS, changelogByMonth, changelogUpdated } from "@/lib/marketing/changelog";
import { FAQ, FAQ_ALL } from "@/lib/marketing/faq";
import { uniqueFaq } from "@/lib/marketing/seo";
import { llmsText } from "@/lib/marketing/llms";
import { statusUrl } from "@/lib/marketing/site";
import { FOR_BUSINESSES, FOR_CREATORS } from "@/lib/marketing/solutions";
import { plansFetch, plansFixture } from "@/test/plans";

import AiInfoPage from "./ai-info/page";
import ChangelogPage from "./changelog/page";
import BusinessesPage from "./for-businesses/page";
import CreatorsPage from "./for-creators/page";
import PricingPage from "./pricing/page";
import SafetyPage from "./safety/page";
import SecurityPage from "./security/page";

function jsonLds(container: HTMLElement): Record<string, unknown>[] {
  return [...container.querySelectorAll('script[type="application/ld+json"]')].map(
    (script) => JSON.parse(script.textContent ?? "null") as Record<string, unknown>,
  );
}

/** Pro as the API reports it while billing is off (C-149): listed, not for sale. */
function proOffSale() {
  const fixture = plansFixture();
  return { items: fixture.items.map((item) => (item.plan === "pro" ? { ...item, available: false, price: null } : item)) };
}

describe("the footer (C-156)", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("has the five columns, the legal and trust links, and the business line", () => {
    render(<SiteFooter year={2026} status={null} />);
    const footer = screen.getByRole("contentinfo");
    for (const name of ["Product", "Solutions", "Compare", "Resources", "Legal and trust"]) {
      expect(within(footer).getByRole("heading", { level: 2, name })).toBeInTheDocument();
    }
    for (const [name, href] of [
      ["What's new", "/changelog"],
      ["For creators", "/for-creators"],
      ["For businesses", "/for-businesses"],
      ["All comparisons", "/compare"],
      ["AI info", "/ai-info"],
      ["Safety", "/safety"],
      ["Subprocessors", "/subprocessors"],
      ["Cookies", "/cookies"],
      ["DPA", "/dpa"],
      ["Accessibility", "/accessibility"],
    ]) {
      expect(within(footer).getByRole("link", { name })).toHaveAttribute("href", href);
    }
    expect(within(footer).queryByRole("link", { name: "Status" })).not.toBeInTheDocument();
    // C-161 (owner): the bar names the business without its location; the legal pages still state it.
    expect(footer).toHaveTextContent("© 2026 UNCHARTD. Amplychat is a product of UNCHARTD.");
    expect(footer).not.toHaveTextContent("Bihar");
    expect(footer).not.toHaveTextContent("India");
    // C-161 v2: no email in the footer; "Contact us" goes to the contact page. /shipping is labelled
    // "Delivery" (the page keeps its URL and its title).
    expect(footer.querySelector('a[href^="mailto:"]')).toBeNull();
    expect(within(footer).getByRole("link", { name: "Contact us" })).toHaveAttribute("href", "/contact");
    expect(within(footer).getByRole("link", { name: "Delivery" })).toHaveAttribute("href", "/shipping");
    expect(within(footer).queryByRole("link", { name: "Shipping" })).not.toBeInTheDocument();
    // The name at full width closes the page, decorative.
    expect(footer.querySelector(".foot-word")).toHaveAttribute("aria-hidden");
    expect(footer.querySelector("nav.foot-two")).toHaveAttribute("aria-labelledby", "footer-legal");
    expect(footer).toHaveTextContent("Amplychat isn't affiliated with or endorsed by Meta. Instagram and WhatsApp are trademarks of Meta Platforms, Inc.");
  });

  it("shows Status only when the status page is configured", () => {
    render(<SiteFooter year={2026} status="https://status.example.com/" />);
    expect(screen.getByRole("link", { name: "Status" })).toHaveAttribute("href", "https://status.example.com/");
  });

  it("reads NEXT_PUBLIC_STATUS_URL, ignoring anything that isn't an http(s) URL", () => {
    expect(statusUrl(undefined)).toBeNull();
    expect(statusUrl("  ")).toBeNull();
    expect(statusUrl("javascript:alert(1)")).toBeNull();
    expect(statusUrl("not a url")).toBeNull();
    expect(statusUrl("https://status.example.com")).toBe("https://status.example.com/");
    vi.stubEnv("NEXT_PUBLIC_STATUS_URL", "https://status.example.com");
    render(<SiteFooter year={2026} />);
    expect(screen.getByRole("link", { name: "Status" })).toBeInTheDocument();
  });
});

describe("the audience pages (C-156)", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.socialhood.test");
    vi.stubEnv("NEXT_PUBLIC_SITE_URL", "https://socialhood.example");
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it.each([
    ["/for-creators", CreatorsPage, FOR_CREATORS],
    ["/for-businesses", BusinessesPage, FOR_BUSINESSES],
  ] as const)("%s: one h1, Sounds familiar, tiers with Pro from the API, and the FAQ JSON-LD as written", async (path, Page, data) => {
    vi.stubGlobal("fetch", vi.fn(plansFetch(proOffSale())));
    const { container } = render(await Page());
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("heading", { level: 2, name: "Sounds familiar?" })).toBeInTheDocument();
    for (const tier of data.tiers) expect(screen.getByRole("heading", { level: 3, name: tier.name })).toBeInTheDocument();
    // Pro isn't for sale: it says so, and no price is shown.
    expect(screen.getAllByText("Coming soon").length).toBeGreaterThan(0);
    expect(container.textContent).not.toMatch(/₹|\$\d/);

    // Every question is shown; the FAQPage names only those /faq doesn't already mark up (C-162),
    // each word for word as shown.
    const shown = [...container.querySelectorAll("section#faq details")];
    expect(shown).toHaveLength(data.faq.length);
    const own = uniqueFaq(data.faq, FAQ_ALL);
    const faq = jsonLds(container).find((node) => node["@type"] === "FAQPage") as
      | { "@id": string; mainEntity: { name: string; acceptedAnswer: { text: string } }[] }
      | undefined;
    if (!own.length) expect(faq).toBeUndefined();
    else {
      expect(faq?.["@id"]).toBe(`https://socialhood.example${path}#faq`);
      expect(faq?.mainEntity.map((entity) => entity.name)).toEqual(own.map((item) => item.question));
      for (const entity of faq?.mainEntity ?? []) {
        const details = shown.find((node) => node.querySelector("summary")?.textContent === entity.name);
        expect(details?.querySelector("p")?.textContent).toBe(entity.acceptedAnswer.text);
      }
    }
    expect(jsonLds(container).some((data) => data["@type"] === "BreadcrumbList")).toBe(true);
  });

  it("shows Pro's price from the API once it is on sale", async () => {
    vi.stubGlobal("fetch", vi.fn(plansFetch(plansFixture())));
    render(await CreatorsPage());
    expect(screen.getAllByText(/a month$/).length).toBeGreaterThan(0);
  });

  it("the businesses page lists the integrations with their status", async () => {
    vi.stubGlobal("fetch", vi.fn(plansFetch(proOffSale())));
    render(await BusinessesPage());
    expect(screen.getByRole("heading", { level: 3, name: "Shopify" })).toBeInTheDocument();
    expect(screen.getByText("With our Shopify app listing")).toBeInTheDocument();
  });
});

describe("safety, what's new and AI info (C-156)", () => {
  beforeEach(() => vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.socialhood.test"));
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("/safety: one h1, the limits, no promise of no bans", () => {
    const { container } = render(<SafetyPage />);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(container).toHaveTextContent("At most 750 in any hour");
    expect(container.textContent).not.toMatch(/guarantee(d|s)? (that|your|no)/i);
  });

  it("/changelog: months newest first, every entry dated and shown", () => {
    render(<ChangelogPage />);
    const months = changelogByMonth();
    expect(screen.getAllByRole("heading", { level: 2 }).map((heading) => heading.textContent)).toEqual(months.map((month) => month.month));
    expect(months[0].month).toBe("October 2026");
    expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(CHANGELOG.length);
    for (const entry of CHANGELOG) expect(entry.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(changelogUpdated()).toBe(CHANGELOG.map((entry) => entry.date).sort().at(-1));
  });

  it("/changelog (C-159): a timeline card per entry with its full date, its area and Meta's tag where it applies", () => {
    const { container } = render(<ChangelogPage />);
    const cards = container.querySelectorAll("article.tl-card");
    expect(cards).toHaveLength(CHANGELOG.length);
    for (const entry of CHANGELOG) expect(Object.keys(CHANGELOG_AREAS)).toContain(entry.area);
    const first = cards[0];
    expect(first.querySelector("time")).toHaveAttribute("datetime", CHANGELOG[0].date);
    expect(first.textContent).toContain(CHANGELOG_AREAS[CHANGELOG[0].area]);
    expect(container.querySelectorAll(".tl-card .tag")).toHaveLength(CHANGELOG.filter((entry) => entry.status).length);
  });

  it("/safety (C-159): the pace as a list of terms and figures, the practices as cards, a night band to close", () => {
    const { container } = render(<SafetyPage />);
    const pace = container.querySelector("dl.pace")!;
    expect(within(pace as HTMLElement).getAllByRole("term")).toHaveLength(4);
    expect(within(pace as HTMLElement).getByText("At most 750 in any hour").tagName).toBe("DD");
    expect(screen.getByRole("heading", { level: 3, name: "No scraping." })).toBeInTheDocument();
    expect(container.querySelector("section.night")).toHaveAttribute("id", "no-guarantees");
    expect(jsonLds(container).some((data) => data["@type"] === "BreadcrumbList")).toBe(true);
  });

  it("/security (C-159): one h1, the email button, in and out of scope side by side, breadcrumbs", () => {
    const { container } = render(<SecurityPage />);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("heading", { level: 2, name: "What is in scope" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "What is out of scope" })).toBeInTheDocument();
    for (const link of screen.getAllByRole("link", { name: "support@amplychat.com" })) {
      expect(link).toHaveAttribute("href", "mailto:support@amplychat.com?subject=Security%20report");
    }
    expect(screen.getByRole("link", { name: "security.txt" })).toHaveAttribute("href", "/.well-known/security.txt");
    expect(jsonLds(container).some((data) => data["@type"] === "BreadcrumbList")).toBe(true);
  });

  it("/ai-info: the company, the honest limits and the claims to avoid; never a price while Pro isn't for sale", async () => {
    vi.stubGlobal("fetch", vi.fn(plansFetch(proOffSale())));
    const { container } = render(await AiInfoPage());
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(container).toHaveTextContent("UNCHARTD, Bihar, India");
    expect(container).toHaveTextContent("Meta App Review");
    expect(container).toHaveTextContent("No SOC 2");
    expect(screen.getByRole("heading", { level: 2, name: "Claims to avoid" })).toBeInTheDocument();
    expect(container).toHaveTextContent("coming soon, can't be bought yet");
    expect(container.textContent).not.toMatch(/₹|\$\d/);
  });

  it("llms.txt points AI assistants at /ai-info first", () => {
    const text = llmsText("https://socialhood.example");
    expect(text).toContain("(https://socialhood.example/ai-info)");
    expect(text.indexOf("/ai-info")).toBeLessThan(text.indexOf("## Product"));
  });
});

describe("pricing and the landing FAQ (C-156)", () => {
  beforeEach(() => vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.socialhood.test"));
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("the pricing page explains WhatsApp charges: paid to Meta directly, no markup, Meta's page linked", async () => {
    vi.stubGlobal("fetch", vi.fn(plansFetch(plansFixture())));
    render(await PricingPage());
    const block = screen.getByRole("region", { name: "WhatsApp message charges" });
    expect(block).toHaveTextContent("You pay Meta directly through your own WhatsApp Business account. Amplychat adds no markup.");
    expect(block).toHaveTextContent("24-hour window");
    expect(within(block).getByRole("link", { name: /Meta's WhatsApp pricing/ })).toHaveAttribute(
      "href",
      "https://developers.facebook.com/docs/whatsapp/pricing",
    );
  });

  it("the landing FAQ has the creator questions", () => {
    const questions = FAQ.map((item) => item.question);
    expect(questions).toContain("Can automations get my Instagram account banned?");
    expect(questions).toContain("Do I have to share my Instagram password?");
    expect(questions).toContain("Can I take over a conversation from the AI?");
  });
});
