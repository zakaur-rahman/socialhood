import { render, screen, within } from "@testing-library/react";
import type { Metadata } from "next";
import { describe, expect, it } from "vitest";

import { SUPPORT_EMAIL } from "@/lib/copy";
import { ALTERNATIVES, ALTERNATIVES_PATH } from "@/lib/marketing/alternatives";
import { COMPARE_MANYCHAT, COMPARE_PATH, GTM_PAGES, SWITCH_PAGE } from "@/lib/marketing/gtm-pages";
import { GLOSSARY, GLOSSARY_PATH, glossaryPath } from "@/lib/marketing/glossary";
import { GUIDES, guidePath } from "@/lib/marketing/guides";
import { PAGE_UPDATED, PUBLIC_PATHS, footerColumns } from "@/lib/marketing/site";

import ManychatAlternatives, { metadata as alternativesMetadata } from "./compare/manychat-alternatives/page";
import CompareHub from "./compare/page";
import TermPage, { dynamicParams, generateMetadata, generateStaticParams } from "./glossary/[term]/page";
import GlossaryPage, { metadata as glossaryMetadata } from "./glossary/page";

/** Every route a link on these pages may point at (C-163): public pages, guides and terms. */
const ROUTES = new Set<string>([
  ...PUBLIC_PATHS,
  ...GUIDES.map((guide) => guidePath(guide.slug)),
  ...GLOSSARY.map((term) => glossaryPath(term.slug)),
  "/sign-up",
]);

function jsonLd(container: HTMLElement): Record<string, unknown>[] {
  return [...container.querySelectorAll('script[type="application/ld+json"]')].map((node) => JSON.parse(node.textContent ?? "{}"));
}

function internalLinks(container: HTMLElement): string[] {
  return [...container.querySelectorAll("a[href^='/']")].map((a) => a.getAttribute("href")!.split("#")[0]).filter(Boolean);
}

const CLAIMS = /\bbest\b|#1|number one|\bplease\b/i;

describe("/glossary (C-163)", () => {
  it("has its metadata and a sitemap entry", () => {
    expect(glossaryMetadata.alternates?.canonical).toBe(GLOSSARY_PATH);
    expect(PUBLIC_PATHS).toContain(GLOSSARY_PATH);
    expect(PAGE_UPDATED[GLOSSARY_PATH]).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(footerColumns(null).find((column) => column.id === "resources")?.links).toContainEqual({ label: "Glossary", href: GLOSSARY_PATH });
  });

  it("lists every term by letter, one h1, a DefinedTermSet and breadcrumbs", () => {
    const { container } = render(<GlossaryPage />);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    for (const term of GLOSSARY) expect(screen.getByRole("link", { name: term.term })).toHaveAttribute("href", glossaryPath(term.slug));
    // Without script the list is whole: nothing is hidden.
    expect(container.querySelectorAll("[data-term][hidden]")).toHaveLength(0);
    const data = jsonLd(container);
    const set = data.find((node) => node["@type"] === "DefinedTermSet")!;
    expect(set).toMatchObject({ "@context": "https://schema.org", name: "Meta messaging glossary" });
    const terms = set.hasDefinedTerm as Record<string, unknown>[];
    expect(terms).toHaveLength(GLOSSARY.length);
    for (const term of terms) expect(term).toMatchObject({ "@type": "DefinedTerm", inDefinedTermSet: { "@id": set["@id"] } });
    expect(data.find((node) => node["@type"] === "BreadcrumbList")).toMatchObject({ itemListElement: [{ name: "Home" }, { name: "Glossary" }] });
    for (const href of internalLinks(container)) expect(ROUTES, href).toContain(href);
    expect(container.textContent).not.toMatch(CLAIMS);
  });
});

describe("/glossary/[term] (C-163)", () => {
  it("builds only the listed terms; any other slug is a 404", () => {
    expect(generateStaticParams()).toEqual(GLOSSARY.map((term) => ({ term: term.slug })));
    expect(dynamicParams).toBe(false);
  });

  it.each(GLOSSARY.map((term) => [term.slug, term] as const))("%s: metadata, one h1, the definition first, DefinedTerm and links", async (slug, term) => {
    const metadata = (await generateMetadata({ params: Promise.resolve({ term: slug }) } as never)) as Metadata;
    expect(metadata.title).toBe(term.title);
    expect(metadata.description).toBe(term.definition);
    expect(metadata.alternates?.canonical).toBe(glossaryPath(slug));

    const { container } = render(await TermPage({ params: Promise.resolve({ term: slug }) } as never));
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(term.term);
    expect(container.querySelector("[data-definition]")).toHaveTextContent(term.definition);
    expect(screen.getByRole("heading", { level: 2, name: "How Amplychat handles it" })).toBeInTheDocument();
    const data = jsonLd(container);
    expect(data.find((node) => node["@type"] === "DefinedTerm")).toMatchObject({
      name: term.term,
      description: term.definition,
      inDefinedTermSet: { "@type": "DefinedTermSet", name: "Meta messaging glossary" },
    });
    expect(data.find((node) => node["@type"] === "BreadcrumbList")).toMatchObject({
      itemListElement: [{ name: "Home" }, { name: "Glossary" }, { name: term.term }],
    });
    for (const source of term.sources) expect(container.querySelector(`a[href="${source.url}"]`)).not.toBeNull();
    for (const href of internalLinks(container)) expect(ROUTES, href).toContain(href);
    expect(container.querySelector(".close")).not.toBeNull();
    expect(container.textContent).not.toMatch(CLAIMS);
  });
});

describe("/compare/manychat-alternatives (C-163)", () => {
  it("has its metadata, a sitemap entry and links in from the hub, Manychat pages and the footer", () => {
    expect(alternativesMetadata.alternates?.canonical).toBe(ALTERNATIVES_PATH);
    expect(PUBLIC_PATHS).toContain(ALTERNATIVES_PATH);
    expect(PAGE_UPDATED[ALTERNATIVES_PATH]).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    for (const page of [COMPARE_MANYCHAT, SWITCH_PAGE]) expect(page.related.map((link) => link.href)).toContain(ALTERNATIVES_PATH);
    expect(footerColumns(null).find((column) => column.id === "compare")?.links).toContainEqual({ label: "Manychat alternatives", href: ALTERNATIVES_PATH });
    render(<CompareHub />);
    expect(screen.getByRole("link", { name: "Manychat alternatives" })).toHaveAttribute("href", ALTERNATIVES_PATH);
  });

  it("lists each tool alphabetically with its comparison, an unordered ItemList and the plural trademark note", () => {
    const { container } = render(<ManychatAlternatives />);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    const names = ALTERNATIVES.map((item) => item.name);
    expect(names).toEqual([...names].sort((a, b) => a.localeCompare(b)));
    expect(screen.getByText(/The order isn.t a ranking/)).toBeInTheDocument();
    const cards = within(screen.getByRole("region", { name: "The alternatives" }));
    expect(cards.getAllByRole("heading", { level: 3 }).map((heading) => heading.textContent)).toEqual(names);
    for (const item of ALTERNATIVES) expect(container.querySelector(`a[href="${item.href}"]`)).not.toBeNull();
    // Each competitor card says when its details were checked.
    expect(screen.getAllByText(/Checked on 29 October 2026\./)).toHaveLength(ALTERNATIVES.filter((item) => !item.ours).length);
    const list = jsonLd(container).find((node) => node["@type"] === "ItemList")!;
    expect(list).toMatchObject({ itemListOrder: "https://schema.org/ItemListUnordered", numberOfItems: ALTERNATIVES.length });
    expect((list.itemListElement as unknown[]).length).toBe(ALTERNATIVES.length);
    expect(jsonLd(container).find((node) => node["@type"] === "BreadcrumbList")).toMatchObject({
      itemListElement: [{ name: "Home" }, { name: "Compare", item: expect.stringMatching(new RegExp(`${COMPARE_PATH}$`)) }, { name: "Manychat alternatives" }],
    });
    expect(screen.getByText(/Manychat, AiSensy, .* and Wati are trademarks of their owners\./)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: SUPPORT_EMAIL })).toHaveAttribute("href", `mailto:${SUPPORT_EMAIL}`);
    for (const href of internalLinks(container)) expect(ROUTES, href).toContain(href);
    expect(container.textContent).not.toMatch(CLAIMS);
  });

  it("restates only what the comparison pages say: every competitor has its page", () => {
    for (const item of ALTERNATIVES.filter((entry) => !entry.ours)) {
      expect(GTM_PAGES).toContain(item.page);
      expect(item.page.competitor).toBe(item.name);
      expect(item.href).toBe(item.page.path);
    }
  });
});
