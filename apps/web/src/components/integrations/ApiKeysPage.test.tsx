import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { json, renderWithApi } from "@/test/api";

import { ApiKeysPage } from "./ApiKeysPage";
import { SETTINGS_SECTIONS } from "@/components/settings/sections";
import { visibleGroups } from "@/components/settings/groups";

describe("Settings > API keys (C-165)", () => {
  it("is a page of its own with one h1 and links to the API and AI app guides", async () => {
    renderWithApi(<ApiKeysPage />, {
      handlers: { "GET /v1/w/:wid/api-keys": () => json({ items: [], scopes: [], active_limit: 20 }) },
    });
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("heading", { level: 1, name: "API keys" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "public API" }).getAttribute("href")).toMatch(/\/developers\/api$/);
    expect(screen.getByRole("link", { name: "Connect an AI app with a key" }).getAttribute("href")).toMatch(
      /\/developers\/mcp\/api-key$/,
    );
    expect(await screen.findByText(/No API keys yet/)).toBeInTheDocument();
  });

  it("is in the rail for owners and admins, not for agents, beside Integrations", () => {
    expect(SETTINGS_SECTIONS.find((s) => s.segment === "api-keys")?.roles).toEqual(["owner", "admin"]);
    const labels = (role: "owner" | "admin" | "agent") => visibleGroups(role).flatMap((g) => g.items.map((i) => i.label));
    expect(labels("owner")).toContain("API keys");
    expect(labels("admin")).toContain("API keys");
    expect(labels("agent")).not.toContain("API keys");
  });
});
