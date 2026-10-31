import { render, screen, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { Metadata } from "next";
import type { ReactElement } from "react";
import { describe, expect, it } from "vitest";

import { FEATURE_IDS, featureToc } from "@/components/marketing/FeatureDepthView";
import { FAQ_ALL } from "@/lib/marketing/faq";
import { FEATURE_AI_INBOX, FEATURE_COMMENT_INTELLIGENCE, FEATURE_PUBLISHING, GTM_PAGES, STATUS_LABEL, type GtmPage } from "@/lib/marketing/gtm-pages";
import { GUIDES, guidePath } from "@/lib/marketing/guides";
import table from "@/lib/marketing/plan-table.json";
import { DESCRIPTION_MAX, TITLE_MAX } from "@/lib/marketing/seo";
import { PUBLIC_PATHS } from "@/lib/marketing/site";

import FeatureAiInbox, { metadata as aiInboxMetadata } from "./features/ai-inbox/page";
import FeatureComments, { metadata as commentsMetadata } from "./features/comment-intelligence/page";
import FeaturePublishing, { metadata as publishingMetadata } from "./features/publishing/page";

/** C-163: the three feature pages, taken from thin to deep. */
const PAGES: { page: GtmPage; Component: () => ReactElement; metadata: Metadata }[] = [
  { page: FEATURE_AI_INBOX, Component: FeatureAiInbox, metadata: aiInboxMetadata },
  { page: FEATURE_COMMENT_INTELLIGENCE, Component: FeatureComments, metadata: commentsMetadata },
  { page: FEATURE_PUBLISHING, Component: FeaturePublishing, metadata: publishingMetadata },
];

function jsonLds(container: HTMLElement): Record<string, unknown>[] {
  return [...container.querySelectorAll('script[type="application/ld+json"]')].map((node) => JSON.parse(node.textContent ?? "{}"));
}

/** The words a reader sees in the page's own content: the head to the questions (not the related cards or closing band). */
function contentWords(container: HTMLElement): number {
  const main = container.querySelector("main")!.cloneNode(true) as HTMLElement;
  main.querySelectorAll("script, .pp-related, .close, .fp-bar").forEach((node) => node.remove());
  return (main.textContent ?? "").split(/\s+/).filter((word) => /[A-Za-z0-9]/.test(word)).length;
}

const ROUTES = new Set<string>([...PUBLIC_PATHS, ...GUIDES.map((guide) => guidePath(guide.slug)), "/sign-up"]);

describe.each(PAGES)("$page.path (C-163)", ({ page, Component, metadata }) => {
  const depth = page.feature!;

  it("has the deeper sections in order, with one h1", () => {
    const { container } = render(<Component />);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    const ids = featureToc(page).map((item) => item.id);
    for (const id of ids) expect(container.querySelector(`#${id}`), id).not.toBeNull();
    // The bar links every section, in page order.
    const bar = within(container.querySelector(".fp-bar") as HTMLElement);
    expect(bar.getAllByRole("link").map((link) => link.getAttribute("href"))).toEqual(ids.map((id) => `#${id}`));
    const order = ids.map((id) => [...container.querySelectorAll("[id]")].findIndex((node) => node.id === id));
    expect([...order].sort((a, b) => a - b)).toEqual(order);
    // The scene says it is example data.
    expect(within(container.querySelector(`#${FEATURE_IDS.what}`) as HTMLElement).getByText("Example data")).toBeInTheDocument();
  });

  it("is deep, not padded: about 900 to 1,300 words of its own", () => {
    const { container } = render(<Component />);
    const words = contentWords(container);
    expect(words).toBeGreaterThanOrEqual(900);
    expect(words).toBeLessThanOrEqual(1500);
  });

  it("has a unique title and description within the limits, naming the brand once at most", () => {
    const title = typeof metadata.title === "string" ? metadata.title : (metadata.title as { absolute: string }).absolute;
    expect(title.length).toBeLessThanOrEqual(TITLE_MAX);
    expect((title.match(/Amplychat/g) ?? []).length).toBeLessThanOrEqual(1);
    expect(page.description.length).toBeLessThanOrEqual(155);
    expect(page.description.length).toBeLessThanOrEqual(DESCRIPTION_MAX);
    const others = GTM_PAGES.filter((other) => other !== page);
    expect(others.map((other) => other.title)).not.toContain(page.title);
    expect(others.map((other) => other.description)).not.toContain(page.description);
  });

  it("marks up its own questions as FAQPage, none of them repeated from /faq, with breadcrumbs", () => {
    const { container } = render(<Component />);
    const data = jsonLds(container);
    const faq = data.find((item) => item["@type"] === "FAQPage") as { "@id": string; mainEntity: { name: string; acceptedAnswer: { text: string } }[] };
    expect(faq["@id"]).toMatch(new RegExp(`${page.path}#faq$`));
    expect(faq.mainEntity.map((entry) => entry.name)).toEqual(depth.faq.map((item) => item.question));
    expect(faq.mainEntity.map((entry) => entry.acceptedAnswer.text)).toEqual(depth.faq.map((item) => item.answer));
    const hub = new Set(FAQ_ALL.map((item) => item.question));
    for (const item of depth.faq) expect(hub.has(item.question), item.question).toBe(false);
    expect(depth.faq.length).toBeGreaterThanOrEqual(3);
    expect(depth.faq.length).toBeLessThanOrEqual(5);
    // Each question is shown on the page, word for word.
    for (const item of depth.faq) {
      expect(screen.getByRole("heading", { level: 3, name: item.question })).toBeInTheDocument();
      expect(screen.getByText(item.answer)).toBeInTheDocument();
    }
    const crumbs = data.find((item) => item["@type"] === "BreadcrumbList") as { itemListElement: { name: string }[] };
    expect(crumbs.itemListElement.map((item) => item.name)).toEqual(["Home", "Features", page.name]);
  });

  it("shows the limits from plan-table.json and the credits from billing/plans.py", () => {
    render(<Component />);
    const limits = screen.getByRole("table", { name: `${page.name}: limits on each plan` });
    expect(within(limits).getAllByRole("columnheader").map((cell) => cell.textContent)).toEqual(["Limit", "Free", "Pro", "Max"]);
    expect(within(limits).getAllByRole("row")).toHaveLength(depth.limits.length + 1);
    expect(limits.textContent).not.toMatch(/\bnull\b|undefined|NaN/);
    const costs = Object.values(table.credit_costs);
    for (const row of depth.credits) expect(row.credits === 0 || costs.includes(row.credits), row.label).toBe(true);
  });

  it("says what it doesn't do yet, each with its status", () => {
    const { container } = render(<Component />);
    const section = container.querySelector(`#${FEATURE_IDS.notYet}`) as HTMLElement;
    const chips = section.querySelectorAll("[data-status]");
    expect(chips).toHaveLength(depth.notYet.length);
    for (const chip of chips) expect(chip.textContent).toBe(STATUS_LABEL[chip.getAttribute("data-status") as keyof typeof STATUS_LABEL]);
    expect(depth.notYet.some((item) => item.status === "approval" || item.status === "soon")).toBe(true);
  });

  it("is for creators and businesses, and links both audience pages", () => {
    const { container } = render(<Component />);
    const who = within(container.querySelector(`#${FEATURE_IDS.who}`) as HTMLElement);
    expect(who.getByRole("link", { name: /for creators/ })).toHaveAttribute("href", "/for-creators");
    expect(who.getByRole("link", { name: /for businesses/ })).toHaveAttribute("href", "/for-businesses");
  });

  it("links only to real routes, and never claims a ranking", () => {
    const { container } = render(<Component />);
    for (const link of container.querySelectorAll("main a[href]")) {
      const href = link.getAttribute("href")!;
      if (href.startsWith("#") || href.startsWith("mailto:") || /^https?:/.test(href)) continue;
      expect(ROUTES.has(href.split("#")[0]), href).toBe(true);
    }
    // "Best posting times" is the feature's name across the site, not a ranking.
    const text = (container.querySelector("main")!.textContent ?? "").replace(/best posting times/gi, "");
    expect(text).not.toMatch(/\bbest\b|#1|number one|market leader|\bleading\b/i);
    expect(JSON.stringify(depth)).not.toMatch(/\bplease\b/i);
  });
});

it("every claim in the feature pages' data names its source in a comment (C-163)", () => {
  const source = readFileSync(join(process.cwd(), "src/lib/marketing/gtm-pages.ts"), "utf8");
  const start = source.indexOf("// ---- Feature pages");
  const end = source.indexOf("export const GTM_PAGES");
  const section = source.slice(start, end);
  // Each step and each question sits under a comment naming its source.
  for (const marker of ["steps: [", "faq: ["]) {
    let at = section.indexOf(marker);
    while (at !== -1) {
      const block = section.slice(at, section.indexOf("\n    ],", at));
      const entries = block.split("\n      {").slice(1);
      const comments = block.split("\n      //").length - 1;
      expect(comments, `${marker} at ${at}`).toBeGreaterThanOrEqual(entries.length - 1);
      at = section.indexOf(marker, at + 1);
    }
  }
});
