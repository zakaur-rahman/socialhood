import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CONNECT_AI_FAQ, PLAN_ROWS, SAFETY } from "@/lib/marketing/connect-ai";
import { API_KEY_FAQ, API_KEY_META, API_KEY_PAGE_PATH } from "@/lib/marketing/mcp-api-key";
import { ASKS, MCP_PAGE_FAQ, MCP_PAGE_META, MCP_PAGE_PATH, WHERE_CARDS } from "@/lib/marketing/mcp-page";
import { DESCRIPTION_MAX, TITLE_MAX } from "@/lib/marketing/seo";
import { PAGE_UPDATED, PUBLIC_PATHS, footerColumns } from "@/lib/marketing/site";
import { llmsText } from "@/lib/marketing/llms";

import { McpApiKeyView } from "./McpApiKeyView";
import { McpProductView } from "./McpProductView";

const CLAIMS = /\b(best|#1|number one|leading|official partner|verified partner|tiktok)\b/i;

function jsonLd(container: HTMLElement) {
  return [...container.querySelectorAll('script[type="application/ld+json"]')].map((node) => JSON.parse(node.textContent ?? "{}"));
}

describe("/mcp (C-165)", () => {
  it("has one h1, the sections and the two calls to action", () => {
    render(<McpProductView />);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    for (const name of ["Where you can use it", "What you can ask", "How it works", "Plans", "Safety"]) {
      expect(screen.getByRole("heading", { level: 2, name })).toBeInTheDocument();
    }
    expect(screen.getAllByRole("link", { name: /Start free/ }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Set it up" })[0]).toHaveAttribute("href", "/developers/mcp");
    for (const card of WHERE_CARDS) expect(screen.getByRole("heading", { level: 3, name: card.title })).toBeInTheDocument();
    expect(screen.getByText(/haven't tested them yet/)).toBeInTheDocument();
  });

  it("shows 6 to 8 asks and reuses the shared plans and safety", () => {
    expect(ASKS.length).toBeGreaterThanOrEqual(6);
    expect(ASKS.length).toBeLessThanOrEqual(8);
    render(<McpProductView />);
    const table = screen.getByRole("table");
    expect(within(table).getAllByRole("row")).toHaveLength(PLAN_ROWS.length + 1);
    for (const item of SAFETY) expect(screen.getByRole("heading", { level: 3, name: item.title })).toBeInTheDocument();
  });

  it("keeps its metadata within the limits and unique", () => {
    expect(MCP_PAGE_META.title.length).toBeLessThanOrEqual(TITLE_MAX);
    expect(MCP_PAGE_META.description.length).toBeLessThanOrEqual(155);
    expect(MCP_PAGE_META.description.length).toBeLessThanOrEqual(DESCRIPTION_MAX);
    expect(MCP_PAGE_META.description).not.toBe(API_KEY_META.description);
  });

  it("emits breadcrumbs and FAQ JSON-LD for its own questions only", () => {
    const { container } = render(<McpProductView />);
    const data = jsonLd(container);
    expect(data.some((d) => d["@type"] === "BreadcrumbList")).toBe(true);
    const faq = data.find((d) => d["@type"] === "FAQPage");
    expect(faq.mainEntity).toHaveLength(MCP_PAGE_FAQ.length);
    const own = new Set<string>(CONNECT_AI_FAQ.map((q) => q.question));
    for (const q of MCP_PAGE_FAQ) expect(own.has(q.question)).toBe(false);
  });

  it("links only to routes that exist and makes no claim words", () => {
    const { container } = render(<McpProductView />);
    for (const a of container.querySelectorAll("main a[href^='/']")) {
      const path = (a.getAttribute("href") ?? "").split("#")[0];
      if (path && path !== "/sign-up") expect([...PUBLIC_PATHS, "/pricing"], path).toContain(path);
    }
    expect(JSON.stringify([WHERE_CARDS, ASKS.map((ask) => ask.result), MCP_PAGE_FAQ])).not.toMatch(CLAIMS);
  });

  it("is in the sitemap lists, the footer and llms.txt", () => {
    for (const path of [MCP_PAGE_PATH, API_KEY_PAGE_PATH]) {
      expect(PUBLIC_PATHS).toContain(path);
      expect((PAGE_UPDATED as Record<string, string>)[path]).toBe("2026-11-01");
      expect(llmsText()).toContain(path);
    }
    const connect = footerColumns(null).find((c) => c.links.some((l) => l.href === "/developers/mcp"));
    expect(connect?.links.map((l) => l.href)).toContain(MCP_PAGE_PATH);
  });
});

describe("/developers/mcp/api-key (C-165)", () => {
  it("has one h1, every config block and the address", () => {
    render(<McpApiKeyView apiBase="https://api.amplychat.com" />);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    for (const name of ["Claude Code", "Codex", "Other MCP apps", "Check it with curl"]) {
      expect(screen.getByRole("heading", { level: 3, name })).toBeInTheDocument();
    }
    expect(screen.getAllByText(/https:\/\/api\.amplychat\.com\/mcp/).length).toBeGreaterThan(3);
    expect(screen.getByText(/bearer_token_env_var = "AMPLYCHAT_API_KEY"/)).toBeInTheDocument();
    expect(screen.getAllByText(/Settings › API keys/).length).toBeGreaterThan(0);
  });

  it("keeps its metadata within the limits and its FAQ JSON-LD valid", () => {
    expect(API_KEY_META.title.length).toBeLessThanOrEqual(TITLE_MAX);
    expect(API_KEY_META.description.length).toBeLessThanOrEqual(155);
    const { container } = render(<McpApiKeyView />);
    const faq = jsonLd(container).find((d) => d["@type"] === "FAQPage");
    expect(faq.mainEntity).toHaveLength(API_KEY_FAQ.length);
    expect(JSON.stringify(API_KEY_FAQ)).not.toMatch(CLAIMS);
  });

  it("links to routes that exist", () => {
    const { container } = render(<McpApiKeyView />);
    for (const a of container.querySelectorAll("main a[href^='/']")) {
      const path = (a.getAttribute("href") ?? "").split("#")[0];
      if (path && path !== "/sign-up") expect([...PUBLIC_PATHS, "/pricing"], path).toContain(path);
    }
  });
});
