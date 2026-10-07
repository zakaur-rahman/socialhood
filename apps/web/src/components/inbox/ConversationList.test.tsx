import { fireEvent, render as rtlRender, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { describe, expect, it, vi } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";
import type { ConversationListItem } from "@/lib/api/types";
import { listItem } from "@/test/api";

import { ConversationList, VIRTUALIZE_ABOVE } from "./ConversationList";

// The app renders every page inside a TooltipProvider (app/layout.tsx); the badges' hints need one.
const render = (ui: ReactElement) => rtlRender(ui, { wrapper: TooltipProvider });

const now = new Date("2026-09-28T12:00:00Z");

function items(count: number): ConversationListItem[] {
  return Array.from({ length: count }, (_, i) =>
    listItem({
      id: `c${i}`,
      contact: { id: `p${i}`, display_name: `Contact ${i}`, username: null, profile_picture_url: null },
      last_message_at: new Date(now.getTime() - i * 60_000).toISOString(),
    }),
  );
}

function renderList(list: ConversationListItem[], fetchNextPage = vi.fn()) {
  const view = render(
    <ConversationList
      items={list}
      slug="maple"
      selectedId={null}
      now={now}
      hasNextPage
      isFetchingNextPage={false}
      fetchNextPage={fetchNextPage}
    />,
  );
  return { ...view, fetchNextPage };
}

describe("ConversationList (UX-INB-04, TR-FE-08)", () => {
  it("renders every row up to 100 and virtualises above", () => {
    const { container, rerender } = renderList(items(3));
    expect(container.firstElementChild).toHaveAttribute("data-virtual", "false");
    expect(screen.getAllByRole("link")).toHaveLength(3);
    rerender(
      <ConversationList
        items={items(VIRTUALIZE_ABOVE + 50)}
        slug="maple"
        selectedId={null}
        now={now}
        hasNextPage={false}
        isFetchingNextPage={false}
        fetchNextPage={() => {}}
      />,
    );
    expect(container.firstElementChild).toHaveAttribute("data-virtual", "true");
    // jsdom has no layout, so only a window of rows (if any) is in the DOM, never all 150.
    expect(screen.queryAllByRole("link").length).toBeLessThan(VIRTUALIZE_ABOVE);
  });

  it("AI Auto follows the conversation's own mode, else its account's (C-063)", () => {
    const [first, second, third] = items(3);
    render(
      <ConversationList
        items={[first, { ...second, ai_mode_override: "off" }, { ...third, social_account_id: "a2", ai_mode_override: "auto" }]}
        slug="maple"
        selectedId={null}
        now={now}
        hasNextPage={false}
        isFetchingNextPage={false}
        fetchNextPage={() => {}}
        accountModes={{ a1: "auto", a2: "suggest" }}
      />,
    );
    const rows = screen.getAllByRole("link");
    expect(rows.map((row) => row.querySelector('[data-badge="ai"]') !== null)).toEqual([true, false, true]);
    expect(rows[0]).toHaveClass("h-[90px]");
    expect(rows[1]).toHaveClass("h-[68px]");
  });

  it("moves focus between rows with the arrow keys (UX-A11Y-02)", async () => {
    const user = userEvent.setup();
    renderList(items(3));
    const links = screen.getAllByRole("link");
    links[0].focus();
    await user.keyboard("{ArrowDown}");
    await vi.waitFor(() => expect(links[1]).toHaveFocus());
    await user.keyboard("{ArrowUp}");
    await vi.waitFor(() => expect(links[0]).toHaveFocus());
  });

  it("loads the next page near the end of the list", () => {
    const { container, fetchNextPage } = renderList(items(3));
    const scroller = container.firstElementChild as HTMLElement;
    Object.defineProperty(scroller, "scrollHeight", { configurable: true, value: 1000 });
    Object.defineProperty(scroller, "clientHeight", { configurable: true, value: 600 });
    scroller.scrollTop = 100;
    fireEvent.scroll(scroller);
    expect(fetchNextPage).toHaveBeenCalled();
  });

  it("announces a conversation that becomes unread, once (UX-A11Y-03)", () => {
    const list = items(2);
    const { rerender } = renderList(list);
    const props = { slug: "maple", selectedId: null, now, hasNextPage: false, isFetchingNextPage: false, fetchNextPage: () => {} };
    rerender(<ConversationList items={[{ ...list[1], unread_count: 1, last_message_at: now.toISOString() }, list[0]]} {...props} />);
    expect(screen.getByText("New message from Contact 1")).toHaveAttribute("aria-live", "polite");
  });
});
