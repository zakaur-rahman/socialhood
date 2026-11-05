import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Tabs } from "@/components/ui/tabs";

import { ListHeader } from "./ListHeader";

const originalMatchMedia = window.matchMedia;

function renderHeader(short: boolean) {
  window.matchMedia = ((query: string) => ({
    matches: short && query === "(max-height: 40rem)",
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })) as unknown as typeof window.matchMedia;
  render(
    <Tabs value="chats">
      <ListHeader
        tab="chats"
        scheduledCount={0}
        view="needs_reply"
        onViewChange={vi.fn()}
        counts={{ needs_reply: 3, needs_you: 0 }}
        search=""
        onSearchChange={vi.fn()}
        accounts={[]}
        accountId={null}
        onAccountChange={vi.fn()}
      />
    </Tabs>,
  );
}

afterEach(() => {
  window.matchMedia = originalMatchMedia;
});

describe("the inbox's view filters", () => {
  it("are chips when there is room", () => {
    renderHeader(false);
    expect(screen.getByRole("radio", { name: "Needs reply, 3" })).toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "Views" })).not.toBeInTheDocument();
  });

  it("collapse into one select showing the current view and its count when space is short", () => {
    renderHeader(true);
    expect(screen.getByRole("combobox", { name: "Views" })).toHaveTextContent("Needs reply, 3");
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
  });
});
