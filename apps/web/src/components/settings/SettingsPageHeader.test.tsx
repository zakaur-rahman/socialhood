import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SettingsPageHeader } from "./SettingsPageHeader";

const nav = vi.hoisted(() => ({ pathname: "/w/maple/settings/billing" }));
vi.mock("next/navigation", () => ({ usePathname: () => nav.pathname }));

function crumbs(pathname: string, title = "Some title") {
  nav.pathname = pathname;
  render(
    <SettingsPageHeader
      label="Plan & usage"
      title={title}
      description="One line."
      actions={<button type="button">Act</button>}
    />,
  );
  const trail = screen.getByRole("navigation", { name: "Breadcrumb" });
  return { trail, text: within(trail).getAllByRole("listitem").map((li) => li.textContent).filter(Boolean) };
}

describe("SettingsPageHeader (C-066)", () => {
  it.each([
    ["/w/maple/settings/billing", "Billing"],
    ["/w/maple/settings/connections", "Connections"],
    ["/w/maple/settings/ai", "AI Rules & Takeover"],
    ["/w/maple/settings/workspace", "Workspace"],
    ["/w/maple/settings/notifications", "Notifications"],
    ["/w/maple/settings/agent", "Agent"],
  ])("the breadcrumb names the tab the page is on (%s)", (pathname, tab) => {
    const { trail, text } = crumbs(pathname, "A page title that differs");
    expect(text).toEqual(["Settings", tab]);
    expect(within(trail).getByText(tab)).toHaveAttribute("aria-current", "page");
  });

  it("has the label, the title as the page heading, the description and the actions", () => {
    crumbs("/w/maple/settings/billing", "Billing & Usage");
    expect(screen.getByText("Plan & usage")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Billing & Usage" })).toBeInTheDocument();
    expect(screen.getByText("One line.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Act" })).toBeInTheDocument();
  });
});
