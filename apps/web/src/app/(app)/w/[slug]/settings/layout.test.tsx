import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Role } from "@/lib/api/types";
import { WorkspaceProvider } from "@/lib/workspace";
import { workspace } from "@/test/api";

import SettingsLayout from "./layout";

vi.mock("next/navigation", () => ({ usePathname: () => "/w/maple/settings/notifications" }));

function tabs(role: Role) {
  render(
    <WorkspaceProvider value={{ ...workspace, role }}>
      <SettingsLayout>
        <p>page</p>
      </SettingsLayout>
    </WorkspaceProvider>,
  );
  return within(screen.getByRole("navigation", { name: "Settings" }))
    .getAllByRole("link")
    .map((link) => link.textContent);
}

describe("Settings tabs (UX-SCR-07)", () => {
  it("owners and admins see Notifications and Billing", () => {
    expect(tabs("owner")).toEqual([
      "Connections",
      "AI Rules & Takeover",
      "Workspace",
      "Notifications",
      "Billing",
      "Agent",
    ]);
  });

  it("agents see their own Notifications, not Billing", () => {
    expect(tabs("agent")).toEqual(["Connections", "AI Rules & Takeover", "Workspace", "Notifications", "Agent"]);
    expect(screen.getByRole("link", { name: "Notifications" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Connections" })).not.toHaveAttribute("aria-current");
  });
});
