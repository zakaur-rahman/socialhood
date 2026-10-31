import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CONNECT_AI_FAQ, CONNECT_AI_PATH, CAPABILITIES, SAFETY, clientGuides, mcpUrl } from "@/lib/marketing/connect-ai";
import { llmsText } from "@/lib/marketing/llms";
import { PAGE_UPDATED, PUBLIC_PATHS, footerColumns } from "@/lib/marketing/site";

import { ConnectAiView } from "./ConnectAiView";

const ALL_TEXT = JSON.stringify([CAPABILITIES, SAFETY, CONNECT_AI_FAQ, clientGuides("https://api.amplychat.com/mcp")]);

describe("/developers/mcp (C-165)", () => {
  it("renders one h1, every app's steps and the server address", () => {
    render(<ConnectAiView apiBase="https://api.amplychat.com" />);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    for (const name of ["Claude (claude.ai, desktop and mobile)", "Claude Code", "ChatGPT", "Codex"]) {
      expect(screen.getByRole("heading", { level: 3, name })).toBeInTheDocument();
    }
    expect(screen.getAllByText("https://api.amplychat.com/mcp").length).toBeGreaterThan(1);
    const table = screen.getByRole("table");
    expect(within(table).getByRole("columnheader", { name: "Free" })).toBeInTheDocument();
  });

  it("points the key-based guides to the API-key page and names Settings > API keys", () => {
    render(<ConnectAiView apiBase="https://api.amplychat.com" />);
    const links = screen.getAllByRole("link", { name: "Using an API key instead" });
    expect(links).toHaveLength(2);
    for (const link of links) expect(link).toHaveAttribute("href", "/developers/mcp/api-key");
    expect(screen.getByText(/API key from Settings › API keys/)).toBeInTheDocument();
    expect(screen.queryByText(/Settings › Integrations/)).toBeNull();
  });

  it("builds the address from the API's base URL", () => {
    expect(mcpUrl("https://api.example.com/")).toBe("https://api.example.com/mcp");
    expect(mcpUrl(undefined)).toMatch(/\/mcp$/);
  });

  it("claims only what R1 builds (01-design.md §7.4)", () => {
    const text = ALL_TEXT.toLowerCase();
    for (const banned of ["tiktok", "facebook", "official partner", "verified partner", "virus", "automatically posts"]) {
      expect(text, banned).not.toContain(banned);
    }
    expect(text).toContain("can't send it");
    expect(text).toContain("business, enterprise and edu");
  });

  it("is in the sitemap, the footer and llms.txt", () => {
    expect(PUBLIC_PATHS).toContain(CONNECT_AI_PATH);
    expect(PAGE_UPDATED[CONNECT_AI_PATH]).toBeDefined();
    expect(footerColumns(null).flatMap((c) => c.links.map((l) => l.href))).toContain(CONNECT_AI_PATH);
    expect(llmsText()).toContain("/developers/mcp");
  });
});
