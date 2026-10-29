import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FAQ, FAQ_ALL, FAQ_GROUPS } from "@/lib/marketing/faq";
import { llmsText } from "@/lib/marketing/llms";
import { footerColumns } from "@/lib/marketing/site";

import FaqPage, { metadata } from "./page";

function jsonLds(container: HTMLElement) {
  return [...container.querySelectorAll('script[type="application/ld+json"]')].map((script) => JSON.parse(script.textContent ?? "null") as Record<string, unknown>);
}

describe("/faq (C-157)", () => {
  beforeEach(() => vi.stubEnv("NEXT_PUBLIC_SITE_URL", "https://socialhood.example"));
  afterEach(() => vi.unstubAllEnvs());

  it("lists every question in groups, each a native disclosure, with one h1", () => {
    const { container } = render(<FaqPage />);
    expect(screen.getAllByRole("heading", { level: 1 }).map((h) => h.textContent)).toEqual(["Common questions"]);
    expect(screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent)).toEqual(FAQ_GROUPS.map((group) => group.title));
    expect([...container.querySelectorAll("details summary h3")].map((h) => h.textContent)).toEqual(FAQ_ALL.map((item) => item.question));
    // Every question the landing page shows is here too, and no question is listed twice.
    for (const item of FAQ) expect(FAQ_ALL).toContain(item);
    expect(new Set(FAQ_ALL.map((item) => item.question)).size).toBe(FAQ_ALL.length);
  });

  it("has FAQPage JSON-LD that matches the page word for word, and breadcrumbs", () => {
    const { container } = render(<FaqPage />);
    const data = jsonLds(container);
    const faq = data.find((node) => node["@type"] === "FAQPage") as { "@id": string; mainEntity: { name: string; acceptedAnswer: { text: string } }[] };
    expect(faq["@id"]).toBe("https://socialhood.example/faq#faq");
    const details = container.querySelectorAll("details");
    expect(faq.mainEntity).toHaveLength(details.length);
    faq.mainEntity.forEach((entity, index) => {
      expect(details[index].querySelector("summary")?.textContent).toBe(entity.name);
      expect(details[index].querySelector("p")?.textContent).toBe(entity.acceptedAnswer.text);
    });
    expect(data.find((node) => node["@type"] === "BreadcrumbList")).toMatchObject({
      itemListElement: [{ name: "Home" }, { name: "Common questions", item: "https://socialhood.example/faq" }],
    });
  });

  it("has its own metadata, and the footer and llms.txt point to it", () => {
    expect(metadata.title).toBe("Common questions");
    expect(metadata.alternates?.canonical).toBe("/faq");
    const resources = footerColumns(null).find((column) => column.id === "resources");
    expect(resources?.links).toContainEqual({ label: "Common questions", href: "/faq" });
    expect(llmsText("https://socialhood.example")).toContain("(https://socialhood.example/faq)");
  });
});
