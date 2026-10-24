import { render, screen, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GTM_PAGES, PRICING_PATH, type GtmPage } from "@/lib/marketing/gtm-pages";
import { PUBLIC_PATHS } from "@/lib/marketing/site";
import { plansFetch, plansFixture } from "@/test/plans";

import ComparisonInterakt, { metadata as interaktMetadata } from "./compare/interakt/page";
import ComparisonManychat, { metadata as manychatMetadata } from "./compare/manychat/page";
import FeatureAiInbox, { metadata as aiInboxMetadata } from "./features/ai-inbox/page";
import FeatureComments, { metadata as commentsMetadata } from "./features/comment-intelligence/page";
import FeaturePublishing, { metadata as publishingMetadata } from "./features/publishing/page";
import PricingPage, { metadata as pricingMetadata, revalidate } from "./pricing/page";
import SwitchPage, { metadata as switchMetadata } from "./switch-from-manychat/page";

class IdleObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return [];
  }
}

type Meta = { title?: unknown; description?: unknown; alternates?: { canonical?: unknown } };
const PAGES: { page: GtmPage; Component: () => ReactElement; metadata: Meta }[] = [
  { page: GTM_PAGES[0], Component: SwitchPage, metadata: switchMetadata },
  { page: GTM_PAGES[1], Component: ComparisonManychat, metadata: manychatMetadata },
  { page: GTM_PAGES[2], Component: ComparisonInterakt, metadata: interaktMetadata },
  { page: GTM_PAGES[3], Component: FeatureComments, metadata: commentsMetadata },
  { page: GTM_PAGES[4], Component: FeatureAiInbox, metadata: aiInboxMetadata },
  { page: GTM_PAGES[5], Component: FeaturePublishing, metadata: publishingMetadata },
];

describe.each(PAGES)("$page.path", ({ page, Component, metadata }) => {
  it("has its metadata, Open Graph and a sitemap entry", () => {
    expect(metadata.title).toBe(page.title);
    expect(metadata.description).toBe(page.description);
    expect(metadata.alternates?.canonical).toBe(page.path);
    expect(metadata).toMatchObject({
      openGraph: { url: page.path, title: `${page.title} · Social Hood`, images: [expect.objectContaining({ url: "/og.png" })] },
      twitter: { card: "summary_large_image" },
    });
    expect(PUBLIC_PATHS).toContain(page.path);
    expect(page.description.length).toBeLessThanOrEqual(300);
  });

  it("has one h1, h2 sections, a sign-up and internal links", () => {
    render(<Component />);
    expect(screen.getByRole("main")).toHaveAttribute("id", "main");
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(page.h1);
    expect(screen.getAllByRole("heading", { level: 2 }).length).toBeGreaterThanOrEqual(3);
    expect(screen.getAllByRole("link", { name: /Start free/ })[0]).toHaveAttribute("href", "/sign-up");
    expect(screen.getByRole("link", { name: "See plans and limits" })).toHaveAttribute("href", PRICING_PATH);
    const keepReading = within(screen.getByRole("region", { name: "Keep reading" }));
    for (const link of page.related) expect(keepReading.getByRole("link", { name: link.label })).toHaveAttribute("href", link.href);
    expect(page.related.every((link) => (PUBLIC_PATHS as readonly string[]).includes(link.href))).toBe(true);
  });
});

describe("the content rules (GR-37)", () => {
  it("never claims a ranking, and never puts a price of ours on a page", () => {
    for (const page of GTM_PAGES) {
      expect(JSON.stringify(page)).not.toMatch(/\bthe best\b|#1|number one|market leader|\bleading\b|best[- ]in[- ]class/i);
      for (const row of page.compare?.rows ?? []) expect(row.ours.text ?? "").not.toMatch(/[$₹€£]\s?\d/);
    }
  });

  it("every competitor cell has a source comment right above it, naming a date", () => {
    const lines = readFileSync(join(process.cwd(), "src/lib/marketing/gtm-pages.ts"), "utf8").split("\n");
    const theirs = lines.flatMap((line, index) => (/^\s+theirs: \{/.test(line) ? [index] : []));
    expect(theirs.length).toBe(GTM_PAGES.flatMap((page) => page.compare?.rows ?? []).length);
    for (const index of theirs) {
      expect(lines[index - 1]).toMatch(/\/\/ source: .*\b2026-10-\d\d\b/);
    }
  });

  it("never says a competitor lacks something: only 'not found'", () => {
    for (const page of GTM_PAGES) {
      for (const row of page.compare?.rows ?? []) expect(row.theirs.status).not.toBe("no");
    }
  });

  it("describes what waits on the owner honestly", () => {
    const status = (page: GtmPage, feature: string) => page.compare?.rows.find((row) => row.feature === feature)?.ours;
    expect(status(GTM_PAGES[1], "Broadcasts")?.status).toBe("soon");
    expect(status(GTM_PAGES[1], "Live comments, ads, entry links and QR codes")?.status).toBe("approval");
    expect(status(GTM_PAGES[2], "Bulk WhatsApp campaigns")?.status).toBe("soon");
    expect(status(GTM_PAGES[2], "Product catalogue")?.text).toMatch(/Shopify sync is coming soon/);
  });
});

describe("Switch from Manychat", () => {
  it("lists what can be rebuilt, what is added and what differs, and cites its sources", () => {
    render(<SwitchPage />);
    expect(screen.getByRole("heading", { level: 2, name: "What you can rebuild here" })).toBeInTheDocument();
    expect(screen.getByText(/no one-click import from Manychat/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: "Flat plans" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "What is different, so you can decide" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Social Hood vs Manychat" })).toHaveAttribute("href", "/compare/manychat");
    expect(screen.getByRole("link", { name: /Kanal/ })).toHaveAttribute("href", "https://getkanal.com/blog/manychat-instagram");
    expect(screen.getByRole("img", { name: /automation editor's preview/ })).toBeInTheDocument();
  });
});

describe("Social Hood vs Manychat", () => {
  it("is a table with row headers, a status for each side and the sources with dates", () => {
    render(<ComparisonManychat />);
    const table = screen.getByRole("table", { name: "Social Hood and Manychat feature by feature" });
    expect(within(table).getAllByRole("columnheader").map((cell) => cell.textContent)).toEqual(["Feature", "Social Hood", "Manychat"]);
    const row = within(table).getByRole("row", { name: /^Broadcasts/ });
    expect(within(row).getAllByText("Coming soon")).toHaveLength(1);
    expect(within(table).getByRole("row", { name: /^Publishing posts/ })).toHaveTextContent("Not found");
    expect(screen.getByText(/third-party guides written in 2026/)).toBeInTheDocument();
    expect(screen.getAllByText(/read 2026-10-22/).length).toBeGreaterThan(3);
  });
});

describe("Social Hood vs Interakt", () => {
  it("cites Interakt's pricing page with the date read and says its prices change", () => {
    render(<ComparisonInterakt />);
    expect(screen.getByRole("link", { name: "Interakt pricing" })).toHaveAttribute("href", "https://www.interakt.shop/pricing/");
    expect(screen.getByText(/read 2026-10-25/)).toBeInTheDocument();
    expect(screen.getByText(/check interakt.shop before you decide/)).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /^Payments and checkout in chat/ })).toHaveTextContent("Not offered");
  });
});

describe("the feature pages", () => {
  it("comment intelligence names what is analysed and its limits", () => {
    render(<FeatureComments />);
    expect(screen.getByRole("heading", { level: 3, name: "Reads every comment" })).toBeInTheDocument();
    expect(screen.getByText(/Free reads the comments on your latest posts/)).toBeInTheDocument();
  });

  it("the AI inbox explains the three modes and escalation", () => {
    render(<FeatureAiInbox />);
    expect(screen.getByText(/Off, Suggest or Auto for each account/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: "Escalation you can rely on" })).toBeInTheDocument();
  });

  it("publishing says Facebook is coming soon", () => {
    render(<FeaturePublishing />);
    expect(screen.getByRole("heading", { level: 3, name: "Facebook Pages are coming soon" })).toBeInTheDocument();
  });
});

describe("the pricing page", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.socialhood.test");
    vi.stubGlobal("IntersectionObserver", IdleObserver);
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("has metadata and a literal hourly revalidate", () => {
    expect(pricingMetadata.title).toBe("Pricing");
    expect(pricingMetadata.alternates?.canonical).toBe("/pricing");
    expect(PUBLIC_PATHS).toContain("/pricing");
    expect(revalidate).toBe(3600);
    expect(readFileSync(join(__dirname, "pricing", "page.tsx"), "utf8")).toMatch(/export const revalidate = 3600;/);
  });

  it("shows Dodo's price with the new entitlements and the full limits table", async () => {
    vi.stubGlobal("fetch", vi.fn(plansFetch(plansFixture())));
    render(await PricingPage());
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("heading", { level: 1, name: "Start free, upgrade when you grow" })).toBeInTheDocument();
    const pro = within(screen.getByRole("heading", { level: 3, name: "Pro" }).closest("li") as HTMLElement);
    expect(pro.getByText("₹999")).toBeInTheDocument();
    expect(pro.getByText("3 team members")).toBeInTheDocument();
    expect(pro.getByText("Public API and Zapier app")).toBeInTheDocument();
    expect(pro.getByText("Product catalogue")).toBeInTheDocument();

    const broadcasts = screen.getByRole("row", { name: /WhatsApp broadcast recipients a month/ });
    expect(broadcasts).toHaveTextContent("Not included");
    expect(broadcasts).toHaveTextContent("2,500");
    expect(broadcasts).toHaveTextContent("25,000");
    expect(broadcasts).toHaveTextContent(/Coming soon: broadcasts open after our review of India's consent rules/);
    expect(screen.getByRole("row", { name: /Remove Powered by Social Hood/ })).toHaveTextContent("Not included");
    expect(screen.getByText(/Catalogue and sequence limits are our current proposals and may change/)).toBeInTheDocument();
  });

  it("without the API it still lists the limits and no price", async () => {
    vi.stubGlobal("fetch", vi.fn(plansFetch({ detail: "down" }, 503)));
    const { container } = render(await PricingPage());
    expect(screen.getByText("See pricing when you sign up")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Accounts and team" })).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/₹\s?\d/);
  });
});
