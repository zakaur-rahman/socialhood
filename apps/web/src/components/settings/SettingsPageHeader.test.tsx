import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SETTINGS_SECTIONS } from "./sections";
import { SettingsPageHeader } from "./SettingsPageHeader";

describe("SettingsPageHeader (C-066, D-08)", () => {
  it("has the title as the page heading, the description and the actions, and nothing above the title", () => {
    render(
      <SettingsPageHeader
        title="Billing and usage"
        description="One line."
        actions={<button type="button">Act</button>}
      />,
    );
    const heading = screen.getByRole("heading", { level: 1, name: "Billing and usage" });
    expect(heading).toHaveClass("text-2xl");
    expect(heading.className).not.toMatch(/md:text-3xl/);
    expect(screen.getByText("One line.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Act" })).toBeInTheDocument();
    // D-08: no breadcrumb, and the heading is the first thing in its block (no eyebrow).
    expect(screen.queryByRole("navigation")).toBeNull();
    expect(heading.previousElementSibling).toBeNull();
  });

  it("the tab labels are the page titles (D-08)", () => {
    expect(SETTINGS_SECTIONS.map((section) => section.label)).toEqual([
      "Connections",
      "AI rules and takeover",
      "Workspace",
      "Saved replies",
      "Business hours",
      "Notifications",
      "Billing and usage",
      "Integrations",
      "Members",
      "Audit log",
      "Activity",
      "Ask Social Hood",
    ]);
  });
});
