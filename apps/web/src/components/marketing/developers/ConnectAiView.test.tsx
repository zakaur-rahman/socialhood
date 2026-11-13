import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CONNECT_AI_FAQ, CONNECT_AI_PATH, CAPABILITIES, PLAN_ROWS, SAFETY, TOOLS, clientGuides, mcpUrl } from "@/lib/marketing/connect-ai";
import { llmsText } from "@/lib/marketing/llms";
import { CONFIRM_LINE, MCP_PAGE_FAQ } from "@/lib/marketing/mcp-page";
import table from "@/lib/marketing/plan-table.json";
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
    const plans = screen.getByRole("table", { name: "What each plan includes for AI apps" });
    for (const name of ["Free", "Creator", "Business", "Agency"]) {
      expect(within(plans).getByRole("columnheader", { name })).toBeInTheDocument();
    }
  });

  it("takes the plans table's daily limits from billing/plans.py (plan-table.json)", () => {
    const limits = table.entitlements;
    const count = (n: number) => n.toLocaleString("en-US");
    const row = (label: string) => PLAN_ROWS.find((r) => r.label === label)!;
    for (const plan of ["free", "pro", "max", "agency"] as const) {
      expect(row("Tool calls a day")[plan]).toBe(count(limits.mcp_calls_daily[plan]));
      const posts = limits.mcp_posts_daily[plan];
      expect(row("Posts scheduled from AI apps a day")[plan]).toBe(posts === 0 ? "None" : count(posts));
      expect(row("Files uploaded from AI apps a day")[plan]).toBe(
        `${count(limits.mcp_uploads_daily[plan])} (${count(limits.mcp_upload_mb_daily[plan])} MB)`,
      );
      expect(row("Make an API key")[plan]).toBe(limits.public_api[plan] ? "Yes" : "No");
    }
  });

  it("lists every tool from the server's registry in one table (01-design.md §7.3)", () => {
    render(<ConnectAiView apiBase="https://api.amplychat.com" />);
    const tools = screen.getByRole("table", { name: "Every tool on the server" });
    expect(within(tools).getAllByRole("row")).toHaveLength(TOOLS.length + 1);
    // Reads first, then drafts, then changes.
    expect(TOOLS.map((tool) => tool.access).join(" ")).toMatch(/^(read )+(draft )+(write ?)+$/);
    const row = within(tools).getByRole("row", { name: /get_workspace/ });
    expect(row).toHaveTextContent("Read");
    expect(row).toHaveTextContent("workspace:read");
    expect(row).toHaveTextContent("Any member");
    expect(row).toHaveTextContent("Every plan");
    const cancel = within(tools).getByRole("row", { name: /cancel_post/ });
    expect(cancel).toHaveTextContent("Change");
    expect(cancel).toHaveTextContent("Owners and admins");
    expect(cancel).toHaveTextContent("Paid plans");
    expect(cancel).toHaveTextContent("Yes");
  });

  it("promises a preview for what the server previews, and nothing more (audit 2026-11-11)", () => {
    const preview = SAFETY.find((item) => item.title === "A preview and a yes before a change")!.body;
    for (const text of [preview, CONFIRM_LINE]) {
      expect(text).toMatch(/scheduled post/);
      expect(text).toMatch(/draft post is saved at once/);
      expect(text).toMatch(/paus(ed|ing) or turn(ed|ing) on/);
      expect(text).not.toMatch(/exactly/);
    }
    // Owner, 2026-11-11: AI apps schedule a minute ahead, as the app does, so no page states a wait.
    expect(JSON.stringify([CAPABILITIES, SAFETY, CONNECT_AI_FAQ, CONFIRM_LINE, MCP_PAGE_FAQ])).not.toMatch(/5 minutes/);
    const list = SAFETY.find((item) => item.title === "Your switch, your list")!.body;
    expect(list).toMatch(/every connected app and every API key with its recent tool calls/);
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
