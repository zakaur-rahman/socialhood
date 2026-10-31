import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Role } from "@/lib/api/types";
import { WorkspaceProvider } from "@/lib/workspace";
import { workspace } from "@/test/api";

import SettingsLayout from "./layout";

const nav = vi.hoisted(() => ({ path: "/w/maple/settings/notifications" }));
vi.mock("next/navigation", () => ({ usePathname: () => nav.path }));

function rail(role: Role) {
  render(
    <WorkspaceProvider value={{ ...workspace, role }}>
      <SettingsLayout>
        <p>page</p>
      </SettingsLayout>
    </WorkspaceProvider>,
  );
  const nav = screen.getByRole("navigation", { name: "Settings" });
  return { nav, links: within(nav).getAllByRole("link").map((link) => link.textContent) };
}

describe("Settings rail (UX-SCR-07)", () => {
  it("owners see every group, in order", () => {
    const { nav, links } = rail("owner");
    expect(within(nav).getAllByRole("heading").map((h) => h.textContent)).toEqual([
      "Workspace",
      "Channels",
      "Automation and AI",
      "Admin",
      "Just for you",
    ]);
    expect(links).toEqual([
      "Workspace",
      "Members",
      "Business hours",
      "Connections",
      "Website chat",
      "AI rules and takeover",
      "Saved replies",
      "Ask Amplychat",
      "Connected AI apps",
      "Billing and usage",
      "Integrations",
      "Audit log",
      "Activity",
      "Notifications",
      "Appearance",
    ]);
  });

  it("agents see their own Notifications, not Billing or the Admin group", () => {
    const { nav, links } = rail("agent");
    expect(links).not.toContain("Billing and usage");
    expect(within(nav).queryByRole("heading", { name: "Admin" })).toBeNull();
    expect(within(nav).getByText("Only changes things for you")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Notifications" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Connections" })).not.toHaveAttribute("aria-current");
  });

  it("filters by label or keyword, says when nothing matches, and Escape clears", async () => {
    const user = userEvent.setup();
    const { nav } = rail("owner");
    const box = within(nav).getByRole("searchbox", { name: "Find a setting" });
    await user.type(box, "spam");
    expect(within(nav).getAllByRole("link").map((l) => l.textContent)).toEqual(["AI rules and takeover"]);
    await user.clear(box);
    await user.type(box, "zzzz");
    expect(within(nav).getByText("No settings match")).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(box).toHaveValue("");
    expect(within(nav).getAllByRole("link").length).toBeGreaterThan(5);
  });

  it("a page shows the Settings back link below lg; the home does not", () => {
    rail("owner");
    expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute("href", "/w/maple/settings");
  });
});
