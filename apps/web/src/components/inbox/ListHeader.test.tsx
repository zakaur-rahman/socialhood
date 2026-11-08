import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { Tabs } from "@/components/ui/tabs";
import { account } from "@/test/api";

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

describe("the account filter and the chips (C-188)", () => {
  beforeAll(() => {
    Element.prototype.hasPointerCapture ??= () => false;
    Element.prototype.releasePointerCapture ??= () => {};
    Element.prototype.scrollIntoView ??= () => {};
  });

  function renderAccounts() {
    window.matchMedia = vi.fn(() => ({
      matches: false,
      media: "",
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })) as unknown as typeof window.matchMedia;
    render(
      <Tabs value="chats">
        <ListHeader
          tab="chats"
          scheduledCount={0}
          view="all"
          onViewChange={vi.fn()}
          search=""
          onSearchChange={vi.fn()}
          accounts={[
            account({ id: "a1", username: "maple", profile_picture_url: "https://cdn.test/maple.jpg" }),
            account({ id: "a2", username: "maple.two", profile_picture_url: null }),
          ]}
          accountId={null}
          onAccountChange={vi.fn()}
        />
      </Tabs>,
    );
  }

  it("shows each account with its picture or initial, named by its handle", async () => {
    renderAccounts();
    await userEvent.click(screen.getByRole("combobox", { name: "Account" }));
    const withoutPicture = await screen.findByRole("option", { name: "@maple.two" });
    expect(within(withoutPicture).getByText("M")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /@maple$/ })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "All accounts" })).toBeInTheDocument();
  });

  it("keeps the chips on one row that scrolls, and a mouse wheel scrolls it", () => {
    renderAccounts();
    const chips = screen.getByRole("radiogroup", { name: "Views" });
    expect(chips).toHaveClass("flex-nowrap");
    expect(chips).not.toHaveClass("md:flex-wrap");
    const row = chips.parentElement as HTMLElement;
    expect(row).toHaveClass("overflow-x-auto");
    fireEvent.wheel(row, { deltaY: 40 });
    expect(row.scrollLeft).toBe(40);
  });
});
