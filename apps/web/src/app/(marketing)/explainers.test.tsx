import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { BentoGrid } from "@/components/marketing/explainers/BentoGrid";
import { BENTO, DETAILS, STAGES } from "@/components/marketing/explainers/content";
import { HowItWorksStages } from "@/components/marketing/explainers/HowItWorksStages";
import { SiteFooter } from "@/components/marketing/SiteFooter";
import { GUIDES, guidePath } from "@/lib/marketing/guides";
import { llmsText } from "@/lib/marketing/llms";
import table from "@/lib/marketing/plan-table.json";
import { FEATURES_PATH, HOW_IT_WORKS_PATH, NAV_LINKS, PAGE_UPDATED, PUBLIC_PATHS } from "@/lib/marketing/site";
import sitemap from "@/app/sitemap";
import { plansFetch, plansFixture } from "@/test/plans";

import FeaturesPage from "./features/page";
import HowItWorksPage from "./how-it-works/page";

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

/** Every address a link on these pages may point at: a public page, a guide, or a section below. */
const PAGES = new Set<string>([...PUBLIC_PATHS, ...GUIDES.map((guide) => guidePath(guide.slug))]);
const DETAIL_IDS = new Set(DETAILS.map((group) => `#${group.id}`));

describe("navigation to the explainer pages (C-160)", () => {
  it("the header, the footer, the sitemap and llms.txt lead to /features and /how-it-works", () => {
    expect(NAV_LINKS.find((link) => link.label === "Features")?.href).toBe(FEATURES_PATH);
    expect(NAV_LINKS.find((link) => link.label === "How it works")?.href).toBe(HOW_IT_WORKS_PATH);
    render(<SiteFooter year={2026} status={null} />);
    const footer = screen.getByRole("contentinfo");
    expect(within(footer).getByRole("link", { name: "Features" })).toHaveAttribute("href", "/features");
    expect(within(footer).getByRole("link", { name: "How it works" })).toHaveAttribute("href", "/how-it-works");
    const urls = sitemap().map((entry) => entry.url);
    for (const path of [FEATURES_PATH, HOW_IT_WORKS_PATH] as const) {
      expect(PAGE_UPDATED[path]).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(urls.some((url) => url.endsWith(path))).toBe(true);
      expect(llmsText("https://socialhood.example")).toContain(`(https://socialhood.example${path})`);
    }
  });
});

describe("/how-it-works (C-160)", () => {
  beforeEach(() => vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.socialhood.test"));
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("renders the eight stages in order, each a section with its heading, and a tracker that links them", () => {
    const { container } = render(<HowItWorksStages />);
    const stages = [...container.querySelectorAll("ol.xp-stages > li > section")];
    expect(stages.map((stage) => stage.id)).toEqual(["connect", "knowledge", "inbox", "reads", "replies", "handoff", "automations", "results"]);
    stages.forEach((stage, index) => {
      const heading = within(stage as HTMLElement).getByRole("heading", { level: 2 });
      expect(heading).toHaveTextContent(`Step ${index + 1}: ${STAGES[index].title}`);
      expect(stage.querySelector(".xp-mark")).toHaveTextContent(String(index + 1));
    });
    const tracker = screen.getByRole("navigation", { name: "The steps" });
    expect(tracker).toHaveAttribute("data-toc");
    expect(within(tracker).getAllByRole("link").map((link) => link.getAttribute("href"))).toEqual(STAGES.map((stage) => `#${stage.id}`));
  });

  it("reuses the landing's scenes: the inbox, the mode switch and the comment-to-DM machine", () => {
    const { container } = render(<HowItWorksStages />);
    expect(container.querySelector("#inbox [data-inbox]")).not.toBeNull();
    expect(container.querySelector("#replies [data-modes] [data-mode='auto']")).not.toBeNull();
    expect(container.querySelector("#automations [data-motion-scope] [data-machine]")).not.toBeNull();
    // The hero's pause control belongs to the hero's script; here the sort plays once, with no control.
    expect(container.querySelector("#inbox [data-motion-toggle]")).toBeNull();
  });

  it("states the limits from the plan table, Auto as Pro, and Ask as never acting by itself", () => {
    render(<HowItWorksStages />);
    const text = document.body.textContent ?? "";
    expect(text).toContain(`up to ${table.entitlements.crawl_pages.free} pages on Free and ${table.entitlements.crawl_pages.pro} on Pro`);
    expect(text).toContain("Auto replies by itself when it is confident, and is part of Pro.");
    expect(text).toContain("Ask Amplychat never sends, changes or deletes anything by itself.");
    expect(text).toContain("never a condition for getting it");
    expect(text).toContain("every Monday at 9:00 AM your time");
  });

  it("has one h1, breadcrumbs JSON-LD, the questions, related pages and the closing band", async () => {
    vi.stubGlobal("fetch", vi.fn(plansFetch(proOffSale())));
    const { container } = render(await HowItWorksPage());
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    const crumbs = jsonLds(container).find((data) => data["@type"] === "BreadcrumbList") as { itemListElement: { name: string }[] };
    expect(crumbs.itemListElement.map((item) => item.name)).toEqual(["Home", "How it works"]);
    expect(screen.getByRole("heading", { level: 2, name: "Common questions" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Keep reading" })).toBeInTheDocument();
    // Pro isn't on sale, so the closing band claims no trial.
    expect(container.querySelector(".close")).not.toHaveTextContent("Try Pro free");
  });
});

describe("/features (C-160)", () => {
  beforeEach(() => vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.socialhood.test"));
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("every bento cell has an icon, a title, a line and a link to a page or a detail that exists", () => {
    const { container } = render(<BentoGrid />);
    const cells = [...container.querySelectorAll("ul.bento > li")];
    expect(cells).toHaveLength(BENTO.length);
    cells.forEach((cell, index) => {
      const data = BENTO[index];
      expect(cell.querySelector(".ico svg"), data.id).not.toBeNull();
      const link = within(cell as HTMLElement).getByRole("link");
      expect(link).toHaveTextContent(data.title);
      const href = link.getAttribute("href")!;
      expect(href.startsWith("#") ? DETAIL_IDS.has(href) : PAGES.has(href), `${data.id}: ${href}`).toBe(true);
      expect(cell.querySelector(".bx-b")?.textContent?.length).toBeGreaterThan(20);
    });
  });

  it("the headline cells are large with a scene, and statuses show where a feature isn't live", () => {
    const { container } = render(<BentoGrid />);
    for (const id of ["inbox", "replies"]) expect(container.querySelector(`#f-${id}.bx-xl .bx-vis [data-ui]`), id).not.toBeNull();
    expect(container.querySelector("#f-comments.bx-l .bx-vis")).not.toBeNull();
    expect(container.querySelector("#f-facebook [data-status='approval']")).toHaveTextContent("With Meta's approval");
    expect(container.querySelector("#f-sequences [data-status='soon']")).toHaveTextContent("Coming soon");
    expect(container.querySelector("#f-catalogue [data-status='pro']")).toHaveTextContent("Pro");
  });

  it("has one h1, breadcrumbs JSON-LD, the details with plan limits, the side nav and the comparison teaser", async () => {
    vi.stubGlobal("fetch", vi.fn(plansFetch(proOffSale())));
    const { container } = render(await FeaturesPage());
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    const crumbs = jsonLds(container).find((data) => data["@type"] === "BreadcrumbList") as { itemListElement: { name: string }[] };
    expect(crumbs.itemListElement.map((item) => item.name)).toEqual(["Home", "Features"]);
    const nav = screen.getByRole("navigation", { name: "Feature groups" });
    expect(within(nav).getAllByRole("link").map((link) => link.getAttribute("href"))).toEqual(DETAILS.map((group) => `#${group.id}`));
    for (const group of DETAILS) expect(container.querySelector(`section#${group.id} h3`), group.id).not.toBeNull();
    // Limits come from the plan table.
    const ai = container.querySelector("section#d-ai") as HTMLElement;
    const credits = within(ai).getByRole("row", { name: /AI credits a month/ });
    expect(credits).toHaveTextContent(`${table.entitlements.ai_credits_monthly.free}`);
    expect(credits).toHaveTextContent("5,000");
    // Pro's state is the plans API's.
    expect(container.querySelector(".xp-plans-note")).toHaveTextContent("Pro is coming soon");
    expect(screen.getByRole("link", { name: /All comparisons/ })).toHaveAttribute("href", "/compare");
  });

  it("says nothing about Pro's state when the plans API can't be reached", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("down", { status: 503 })));
    const { container } = render(await FeaturesPage());
    const note = container.querySelector(".xp-plans-note")!;
    expect(note).toHaveTextContent("Free is available now");
    expect(note).not.toHaveTextContent("Pro is");
  });
});
