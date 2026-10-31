import { cleanup, render, screen, within } from "@testing-library/react";
import type { Metadata } from "next";
import { afterEach, describe, expect, it } from "vitest";

import { automationToc } from "@/components/marketing/automations/AutomationPageView";
import { BENTO, DETAILS, STAGES } from "@/components/marketing/explainers/content";
import { SiteFooter } from "@/components/marketing/SiteFooter";
import { AUTOMATIONS_PATH, AUTOMATION_PAGES, META, type AutomationPage } from "@/lib/marketing/automation-pages";
import { FAQ_ALL } from "@/lib/marketing/faq";
import { GUIDES, guidePath } from "@/lib/marketing/guides";
import { llmsText } from "@/lib/marketing/llms";
import { DESCRIPTION_MAX, TITLE_MAX } from "@/lib/marketing/seo";
import { PAGE_UPDATED, PUBLIC_PATHS, SITE_NAME } from "@/lib/marketing/site";
import sitemap from "@/app/sitemap";

import HubPage, { metadata as hubMetadata } from "./automations/page";
import CommentToDm, { metadata as commentToDm } from "./instagram/comment-to-dm/page";
import Starters, { metadata as starters } from "./instagram/conversation-starters/page";
import DmKeywords, { metadata as dmKeywords } from "./instagram/dm-keywords/page";
import StoryReplies, { metadata as storyReplies } from "./instagram/story-replies/page";
import WebsiteChat, { metadata as websiteChat } from "./website-chat/page";
import WhatsApp, { metadata as whatsapp } from "./whatsapp/auto-reply/page";

afterEach(cleanup);

/** Each page's route module, by path. */
const ROUTES: Record<string, { Page: () => React.ReactElement; metadata: Metadata }> = {
  "/instagram/comment-to-dm": { Page: CommentToDm, metadata: commentToDm },
  "/instagram/story-replies": { Page: StoryReplies, metadata: storyReplies },
  "/instagram/dm-keywords": { Page: DmKeywords, metadata: dmKeywords },
  "/instagram/conversation-starters": { Page: Starters, metadata: starters },
  "/whatsapp/auto-reply": { Page: WhatsApp, metadata: whatsapp },
  "/website-chat": { Page: WebsiteChat, metadata: websiteChat },
};

const PAGES = AUTOMATION_PAGES.map((page) => [page.path, page] as const);
/** Every address an internal link may point at: a public page or a guide. */
const KNOWN = new Set<string>([...PUBLIC_PATHS, ...GUIDES.map((guide) => guidePath(guide.slug))]);
/** Claim words a page must not use about itself (no fake proof, C-163). */
const CLAIMS = /\b(best|#1|number one|leading|world-class|guaranteed?|trusted by|award)\b|#1/i;

function jsonLds(container: HTMLElement): Record<string, unknown>[] {
  return [...container.querySelectorAll('script[type="application/ld+json"]')].map(
    (script) => JSON.parse(script.textContent ?? "null") as Record<string, unknown>,
  );
}

function shownTitle(title: Metadata["title"]): string {
  if (typeof title === "string") return `${title} · ${SITE_NAME}`;
  if (title && typeof title === "object" && "absolute" in title) return title.absolute;
  throw new Error("unexpected title");
}

function words(text: string): number {
  return text.replace(/\s+/g, " ").split(" ").filter((word) => /\w/.test(word)).length;
}

/** Internal links in an element resolve to a real page, or to an id on the page. */
function expectLinksResolve(root: HTMLElement, page: HTMLElement) {
  for (const link of root.querySelectorAll<HTMLAnchorElement>("a[href]")) {
    const href = link.getAttribute("href")!;
    if (/^(https?:|mailto:)/.test(href)) continue;
    if (href.startsWith("#")) {
      expect(page.querySelector(`[id="${href.slice(1)}"]`), href).not.toBeNull();
      continue;
    }
    const path = href.split("#")[0];
    if (path === "/sign-up") continue;
    expect(KNOWN.has(path), href).toBe(true);
  }
}

describe("the automation pages (C-163)", () => {
  it("are listed: public paths, page dates, the sitemap and llms.txt", () => {
    const urls = sitemap().map((entry) => entry.url);
    const llms = llmsText("https://socialhood.example");
    for (const path of [AUTOMATIONS_PATH, ...AUTOMATION_PAGES.map((page) => page.path)]) {
      expect(PUBLIC_PATHS as readonly string[], path).toContain(path);
      expect(PAGE_UPDATED[path as keyof typeof PAGE_UPDATED], path).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(urls.some((url) => url.endsWith(path)), path).toBe(true);
      expect(llms, path).toContain(`(https://socialhood.example${path})`);
    }
  });

  it("have unique titles, descriptions and questions, none repeated from /faq or a guide", () => {
    const titles = Object.values(ROUTES).map(({ metadata }) => shownTitle(metadata.title));
    titles.push(shownTitle(hubMetadata.title));
    expect(new Set(titles).size).toBe(titles.length);
    const descriptions = AUTOMATION_PAGES.map((page) => page.description);
    expect(new Set(descriptions).size).toBe(descriptions.length);
    const elsewhere = new Set([...FAQ_ALL, ...GUIDES.flatMap((guide) => guide.faq ?? [])].map((item) => item.question));
    const questions = AUTOMATION_PAGES.flatMap((page) => page.faq.map((item) => item.question));
    expect(new Set(questions).size).toBe(questions.length);
    for (const question of questions) expect(elsewhere.has(question), question).toBe(false);
  });

  it.each(PAGES)("%s: metadata fits search results and names the brand once at most", (path, page) => {
    const { metadata } = ROUTES[path];
    const title = shownTitle(metadata.title);
    expect(title.length, title).toBeLessThanOrEqual(TITLE_MAX);
    expect(title.split(SITE_NAME).length - 1, title).toBeLessThanOrEqual(1);
    expect(page.description.length, page.description).toBeGreaterThanOrEqual(50);
    expect(page.description.length, page.description).toBeLessThanOrEqual(155);
    expect(page.description.length).toBeLessThanOrEqual(DESCRIPTION_MAX);
    expect(metadata.alternates?.canonical).toBe(path);
    expect(metadata.openGraph).toMatchObject({ url: path, type: "article" });
    expect(page.faq.length).toBeGreaterThanOrEqual(3);
    expect(page.faq.length).toBeLessThanOrEqual(4);
  });

  it.each(PAGES)("%s: one h1, the contents match the sections, an example and the limits", (path, page) => {
    const { Page } = ROUTES[path];
    const { container } = render(<Page />);
    const main = container.querySelector("main")!;
    expect(main.querySelectorAll("h1")).toHaveLength(1);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(page.h1);
    // The body's h2s are the page's sections, in order, then the template's.
    const body = main.querySelector("[data-guide-body]")!;
    const h2s = [...body.querySelectorAll("h2")].map((h2) => h2.id);
    const toc = automationToc(page).map((item) => item.id);
    expect(h2s).toEqual(toc.slice(0, h2s.length));
    for (const id of toc) expect(main.querySelector(`[id="${id}"]`), id).not.toBeNull();
    // A labelled example, and a scene captioned or built from the landing's own.
    expect(within(body as HTMLElement).getAllByText("Example data").length).toBeGreaterThan(0);
    expect(main.querySelector(".ap-scene")?.children.length).toBe(1);
    expect(main.querySelectorAll(".ap-lim tbody tr")).toHaveLength(page.limits.length);
    expect(main.querySelector(".close")).not.toBeNull();
  });

  it.each(PAGES)("%s: 800 to 1,200 words, no claim words, no please", (path) => {
    const { Page } = ROUTES[path];
    const { container } = render(<Page />);
    const article = container.querySelector("article.g-article") as HTMLElement;
    // The article as a reader sees it, without the contents (listed twice) and the scene's example data.
    const copy = article.cloneNode(true) as HTMLElement;
    copy.querySelectorAll("nav, .ap-scene, aside").forEach((node) => node.remove());
    const text = copy.textContent ?? "";
    const count = words(text);
    expect(count, `${count} words`).toBeGreaterThanOrEqual(800);
    expect(count, `${count} words`).toBeLessThanOrEqual(1200);
    expect(text).not.toMatch(CLAIMS);
    expect(text).not.toMatch(/\bplease\b/i);
  });

  it.each(PAGES)("%s: links in and out resolve; the guide, pricing, features and audience page are linked", (path, page) => {
    const { Page } = ROUTES[path];
    const { container } = render(<Page />);
    const main = container.querySelector("main")!;
    expectLinksResolve(main, main);
    const hrefs = [...main.querySelectorAll("a[href]")].map((link) => link.getAttribute("href"));
    for (const href of [page.guide.href, "/pricing", "/features", page.audience.href, AUTOMATIONS_PATH]) expect(hrefs, href).toContain(href);
    // Meta's sources open Meta's own pages, each with the day it was read.
    for (const source of page.sources) {
      expect(source.url).toMatch(/^https:\/\/(developers\.facebook\.com|business\.whatsapp\.com|help\.instagram\.com)\//);
      expect(hrefs).toContain(source.url);
    }
  });

  it.each(PAGES)("%s: structured data is an Article with this page's questions, and a three-level breadcrumb", (path, page) => {
    const { Page } = ROUTES[path];
    const { container } = render(<Page />);
    const data = jsonLds(container);
    const graph = data.find((item) => "@graph" in item)?.["@graph"] as Record<string, unknown>[];
    const article = graph.find((node) => node["@type"] === "Article")!;
    expect(article).toMatchObject({ headline: page.title, description: page.description, dateModified: page.updated });
    const faq = graph.find((node) => node["@type"] === "FAQPage") as { mainEntity: { name: string; acceptedAnswer: { text: string } }[] };
    expect(faq.mainEntity.map((item) => item.name)).toEqual(page.faq.map((item) => item.question));
    // The marked-up answers match the visible ones.
    for (const item of page.faq) expect(container.textContent).toContain(item.answer);
    const crumbs = data.find((item) => item["@type"] === "BreadcrumbList") as { itemListElement: { name: string; item: string }[] };
    expect(crumbs.itemListElement.map((item) => item.name)).toEqual(["Home", "Automations", page.name]);
    expect(crumbs.itemListElement[2].item.endsWith(path)).toBe(true);
  });

  it("states Meta's rules from Meta's own pages, read on a stated day", () => {
    for (const source of Object.values(META)) {
      expect(source.url).toMatch(/^https:\/\/developers\.facebook\.com\//);
      expect(source.read).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    }
    const comment = AUTOMATION_PAGES.find((page) => page.path === "/instagram/comment-to-dm") as AutomationPage;
    expect(comment.sources).toContain(META.privateReplies);
  });
});

describe("the automations hub (C-163)", () => {
  it("has one h1, a card for every page, the rules with their sources, and an ItemList", () => {
    const { container } = render(<HubPage />);
    const main = container.querySelector("main")!;
    expect(main.querySelectorAll("h1")).toHaveLength(1);
    for (const page of AUTOMATION_PAGES) expect(within(main).getByRole("link", { name: page.name })).toHaveAttribute("href", page.path);
    expectLinksResolve(main, main);
    const data = jsonLds(container);
    const list = data.find((item) => item["@type"] === "ItemList") as { itemListElement: { url: string; position: number }[] };
    expect(list.itemListElement.map((item) => new URL(item.url).pathname)).toEqual(AUTOMATION_PAGES.map((page) => page.path));
    const crumbs = data.find((item) => item["@type"] === "BreadcrumbList") as { itemListElement: { name: string }[] };
    expect(crumbs.itemListElement.map((item) => item.name)).toEqual(["Home", "Automations"]);
    expect(data.some((item) => item["@type"] === "FAQPage")).toBe(false);
    expect(main.textContent).not.toMatch(CLAIMS);
    const title = shownTitle(hubMetadata.title);
    expect(title.length).toBeLessThanOrEqual(TITLE_MAX);
  });
});

describe("links into the set (C-163)", () => {
  it("the footer's Product column, the features bento and details, and the how-it-works automations stage", () => {
    render(<SiteFooter year={2026} status={null} />);
    expect(within(screen.getByRole("contentinfo")).getByRole("link", { name: "Automations" })).toHaveAttribute("href", AUTOMATIONS_PATH);
    expect(BENTO.find((cell) => cell.id === "comments")?.href).toBe("/instagram/comment-to-dm");
    expect(BENTO.find((cell) => cell.id === "widget")?.href).toBe("/website-chat");
    expect(DETAILS.find((group) => group.id === "d-automations")?.links?.map((link) => link.href)).toContain(AUTOMATIONS_PATH);
    expect(STAGES.find((stage) => stage.id === "automations")?.link?.href).toBe(AUTOMATIONS_PATH);
  });
});
