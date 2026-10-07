import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { toDefinition } from "@/lib/automations/definition";
import { automation, renderWithApi } from "@/test/api";

import { SettingsStep } from "./SettingsStep";
import { WhenStep } from "./WhenStep";

// In a line of text, colour alone doesn't mark a link (WCAG 1.4.1): the editor's inline links are
// underlined at rest, like Then's "Open Knowledge" (UI-005).
describe("inline links in the editor's steps", () => {
  it("When: Connect Instagram, with no account connected", () => {
    renderWithApi(
      <WhenStep draft={toDefinition(automation())} change={vi.fn()} errors={{}} state="incomplete" accounts={[]} slug="maple" />,
    );
    const link = screen.getByRole("link", { name: "Connect Instagram" });
    expect(link).toHaveAttribute("href", "/w/maple/settings/connections");
    expect(link).toHaveClass("underline");
  });

  it("Settings: the disclosure's link to Settings › Workspace", () => {
    renderWithApi(
      <SettingsStep
        draft={toDefinition(automation())}
        change={vi.fn()}
        errors={{}}
        state="complete"
        timeZone="Asia/Kolkata"
        disclosure="Sent automatically"
        slug="maple"
        defaultOpen
      />,
    );
    const link = screen.getByRole("link", { name: "Change it in Settings → Workspace" });
    expect(link).toHaveAttribute("href", "/w/maple/settings/workspace");
    expect(link).toHaveClass("underline");
  });
});
