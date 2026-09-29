import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentProps, ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";

import { AppSidebar, type SidebarWorkspace } from "./AppSidebar";
import { MobileNav } from "./MobileNav";

let pathname = "/w/aria/home";
vi.mock("next/navigation", () => ({ usePathname: () => pathname }));

const owner: SidebarWorkspace = { name: "Aria Label", slug: "aria", plan: "free", role: "owner" };

function renderWithProviders(node: ReactNode) {
  return render(<TooltipProvider>{node}</TooltipProvider>);
}

function renderSidebar(props: Partial<ComponentProps<typeof AppSidebar>> = {}) {
  const all = { workspace: owner, collapsed: false, ...props };
  const result = renderWithProviders(<AppSidebar {...all} />);
  return {
    ...result,
    rerender: (next: Partial<ComponentProps<typeof AppSidebar>>) =>
      result.rerender(
        <TooltipProvider>
          <AppSidebar {...all} {...next} />
        </TooltipProvider>,
      ),
  };
}

function mainNav() {
  return screen.getByRole("navigation", { name: "Main" });
}

function linkNames(container: HTMLElement): string[] {
  return within(container)
    .getAllByRole("link")
    .map((link) => link.getAttribute("aria-label") ?? link.textContent ?? "");
}

describe("AppSidebar (UX-SH-01)", () => {
  beforeEach(() => {
    pathname = "/w/aria/home";
  });

  it("shows labels, the workspace, the plan and every section for an owner when expanded", () => {
    renderSidebar({ userName: "Priya Nair", userEmail: "priya@aria.example" });
    const nav = mainNav();
    for (const label of ["Home", "Inbox", "Comments", "Schedule", "Automations", "Knowledge", "Settings", "Help"]) {
      expect(within(nav).getByText(label)).toBeInTheDocument();
    }
    expect(within(nav).getByText("Social Hood")).toBeInTheDocument();
    expect(within(nav).getByText("Aria Label")).toBeInTheDocument();
    expect(within(nav).getByText("Free")).toBeInTheDocument();
    expect(within(nav).getByText("Priya Nair")).toBeInTheDocument();
    expect(within(nav).getByText("priya@aria.example")).toBeInTheDocument();
    expect(nav).toHaveAttribute("data-collapsed", "false");
  });

  it("names the role under the account when there is no email", () => {
    renderSidebar({ workspace: { ...owner, role: "admin" }, userName: "Priya Nair" });
    expect(within(mainNav()).getByText("Admin")).toBeInTheDocument();
  });

  it("collapses to icons with accessible names and no visible labels", () => {
    renderSidebar({ collapsed: true, credits: { used: 10, limit: 200, plan: "free" } });
    const nav = mainNav();
    expect(nav).toHaveAttribute("data-collapsed", "true");
    expect(within(nav).queryByText("Inbox")).not.toBeInTheDocument();
    expect(within(nav).queryByText("Aria Label")).not.toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Inbox" })).toHaveAttribute("href", "/w/aria/inbox");
    expect(within(nav).getByRole("button", { name: "Workspace menu: Aria Label" })).toBeInTheDocument();
    expect(within(nav).queryByText("Upgrade")).not.toBeInTheDocument();
  });

  it("marks the active item", () => {
    pathname = "/w/aria/settings/workspace";
    renderSidebar();
    expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Home" })).not.toHaveAttribute("aria-current");
  });

  it("toggles collapse when the host allows it", async () => {
    const toggle = vi.fn();
    renderSidebar({ onToggleCollapsed: toggle });
    const button = screen.getByRole("button", { name: "Collapse sidebar" });
    expect(button).toHaveAttribute("aria-keyshortcuts", "Control+[ Meta+[");
    expect(button).toHaveTextContent("Ctrl [");
    await userEvent.click(button);
    expect(toggle).toHaveBeenCalledOnce();
  });
});

describe("navigation groups by role", () => {
  it("owners and admins: Home alone, then Engage and Grow", () => {
    for (const role of ["owner", "admin"] as const) {
      const { unmount } = renderSidebar({ workspace: { ...owner, role } });
      const engage = screen.getByRole("group", { name: "Engage" });
      const grow = screen.getByRole("group", { name: "Grow" });
      expect(linkNames(engage)).toEqual(["Inbox", "Comments"]);
      expect(linkNames(grow)).toEqual(["Schedule", "Automations", "Knowledge"]);
      const home = screen.getByRole("link", { name: "Home" });
      expect(home.closest('[role="group"]')).toBeNull();
      expect(home.compareDocumentPosition(engage) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      expect(engage.compareDocumentPosition(grow) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      unmount();
    }
  });

  it("agents: Home, Inbox and Comments; the Grow group, label and all, is hidden", () => {
    renderSidebar({ workspace: { ...owner, role: "agent" } });
    const nav = mainNav();
    expect(linkNames(screen.getByRole("group", { name: "Engage" }))).toEqual(["Inbox", "Comments"]);
    expect(screen.queryByRole("group", { name: "Grow" })).not.toBeInTheDocument();
    expect(within(nav).queryByText("Grow")).not.toBeInTheDocument();
    for (const hidden of ["Automations", "Schedule", "Knowledge"]) {
      expect(within(nav).queryByText(hidden)).not.toBeInTheDocument();
    }
  });

  it("collapsed, the labels become dividers but still name the groups", () => {
    renderSidebar({ collapsed: true });
    const engage = screen.getByRole("group", { name: "Engage" });
    expect(linkNames(engage)).toEqual(["Inbox", "Comments"]);
    expect(within(engage).getByText("Engage")).toHaveClass("sr-only");
  });
});

describe("badges", () => {
  it("Inbox shows unread conversations and Comments the comments waiting for a reply", () => {
    renderSidebar({ unreadCount: 3, commentsCount: 1 });
    expect(screen.getByRole("link", { name: "Inbox, 3 unread" })).toHaveAttribute("href", "/w/aria/inbox");
    expect(screen.getByTestId("inbox-badge")).toHaveTextContent("3");
    expect(screen.getByRole("link", { name: "Comments, 1 needs a reply" })).toBeInTheDocument();
    expect(screen.getByTestId("comments-badge")).toHaveTextContent("1");
  });

  it("caps the pill at 99+ and the rail's corner badge at 9+, and shows nothing for zero", () => {
    const { rerender } = renderSidebar({ unreadCount: 0, commentsCount: 250 });
    expect(screen.queryByTestId("inbox-badge")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Inbox" })).toBeInTheDocument();
    expect(screen.getByTestId("comments-badge")).toHaveTextContent("99+");
    rerender({ collapsed: true, unreadCount: 4 });
    expect(screen.getByRole("link", { name: "Comments, 99+ need a reply" })).toBeInTheDocument();
    expect(screen.getByTestId("comments-badge")).toHaveTextContent("9+");
    expect(screen.getByRole("link", { name: "Inbox, 4 unread" })).toBeInTheDocument();
    expect(screen.getByTestId("inbox-badge")).toHaveTextContent("4");
  });
});

describe("workspace menu", () => {
  const maple: SidebarWorkspace = { name: "Maple Bakery", slug: "maple", plan: "pro", role: "admin" };

  it("switches to another workspace and opens workspace settings", async () => {
    const onNavigate = vi.fn();
    renderSidebar({ workspaces: [owner, maple], onNavigate });
    await userEvent.click(screen.getByRole("button", { name: "Workspace menu: Aria Label" }));
    const menu = await screen.findByRole("menu");
    const current = within(menu).getByRole("menuitem", { name: /Aria Label/ });
    expect(current).toHaveAttribute("aria-current", "true");
    expect(within(menu).getByRole("menuitem", { name: /Maple Bakery/ })).toHaveAttribute("href", "/w/maple/home");
    const settings = within(menu).getByRole("menuitem", { name: "Workspace settings" });
    expect(settings).toHaveAttribute("href", "/w/aria/settings/workspace");
    await userEvent.click(settings);
    expect(onNavigate).toHaveBeenCalledOnce();
  });

  it("lists just the current workspace until the list loads", async () => {
    renderSidebar();
    await userEvent.click(screen.getByRole("button", { name: "Workspace menu: Aria Label" }));
    const menu = await screen.findByRole("menu");
    expect(within(menu).getAllByRole("menuitem").map((item) => item.textContent)).toEqual([
      "Aria LabelFree",
      "Workspace settings",
    ]);
  });
});

describe("usage card (FR-AI-05)", () => {
  function meter() {
    return screen.queryByRole("progressbar", { name: "AI credits used" });
  }
  function upgrade() {
    return screen.queryByRole("link", { name: "Upgrade" });
  }

  it("Free: the meter and Upgrade for owners and admins", () => {
    const { rerender } = renderSidebar({ credits: { used: 50, limit: 200, plan: "free" } });
    expect(meter()).toHaveAttribute("aria-valuetext", "50 of 200 used");
    expect(meter()).toHaveAttribute("data-tone", "normal");
    expect(screen.getByText("25%")).toBeInTheDocument();
    expect(upgrade()).toHaveAttribute("href", "/w/aria/settings/billing");
    rerender({ workspace: { ...owner, role: "admin" } });
    expect(upgrade()).toBeInTheDocument();
  });

  it("paying and under 80 %: the quiet meter, no Upgrade", () => {
    renderSidebar({ workspace: { ...owner, plan: "pro" }, credits: { used: 3999, limit: 5000, plan: "pro" } });
    expect(screen.getByText("3,999 of 5,000 used")).toBeInTheDocument();
    expect(meter()).toHaveAttribute("data-tone", "normal");
    expect(upgrade()).not.toBeInTheDocument();
  });

  it("from 80 %: warning-toned with Upgrade; used up: danger-toned", () => {
    const { rerender } = renderSidebar({ credits: { used: 4000, limit: 5000, plan: "pro" } });
    expect(meter()).toHaveAttribute("data-tone", "warning");
    expect(upgrade()).toBeInTheDocument();
    rerender({ credits: { used: 5000, limit: 5000, plan: "pro" } });
    expect(meter()).toHaveAttribute("data-tone", "danger");
    expect(screen.getByText("100%")).toBeInTheDocument();
  });

  it("never offers Upgrade on Max, the top plan", () => {
    renderSidebar({ credits: { used: 24_000, limit: 25_000, plan: "max" } });
    expect(meter()).toHaveAttribute("data-tone", "warning");
    expect(upgrade()).not.toBeInTheDocument();
  });

  it("hidden for agents, for unlimited plans and when billing failed; a placeholder while loading", () => {
    const { rerender } = renderSidebar({
      workspace: { ...owner, role: "agent" },
      credits: { used: 190, limit: 200, plan: "free" },
    });
    expect(meter()).not.toBeInTheDocument();
    expect(upgrade()).not.toBeInTheDocument();
    rerender({ workspace: owner, credits: null });
    expect(meter()).not.toBeInTheDocument();
    expect(screen.queryByTestId("usage-loading")).not.toBeInTheDocument();
    rerender({ workspace: owner, credits: "loading" });
    expect(screen.getByTestId("usage-loading")).toBeInTheDocument();
    expect(upgrade()).not.toBeInTheDocument();
  });

  it("collapsed: a ring named by the figures, without Upgrade", () => {
    renderSidebar({ collapsed: true, credits: { used: 412, limit: 500, plan: "free" } });
    expect(screen.getByRole("img", { name: "AI credits: 412 of 500 used" })).toBeInTheDocument();
    expect(upgrade()).not.toBeInTheDocument();
  });
});

describe("collapse shortcut (Ctrl/⌘ [)", () => {
  it("toggles from anywhere but a field, and not while a dialog is open", () => {
    const toggle = vi.fn();
    renderWithProviders(
      <>
        <AppSidebar workspace={owner} collapsed={false} onToggleCollapsed={toggle} />
        <input aria-label="Search" />
        <textarea aria-label="Reply" />
        <div contentEditable aria-label="Caption" role="textbox" suppressContentEditableWarning>
          <span>text</span>
        </div>
      </>,
    );
    fireEvent.keyDown(document.body, { key: "[", code: "BracketLeft", ctrlKey: true });
    expect(toggle).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(document.body, { key: "[", code: "BracketLeft", metaKey: true });
    expect(toggle).toHaveBeenCalledTimes(2);

    fireEvent.keyDown(screen.getByRole("textbox", { name: "Search" }), { key: "[", ctrlKey: true });
    fireEvent.keyDown(screen.getByRole("textbox", { name: "Reply" }), { key: "[", ctrlKey: true });
    fireEvent.keyDown(screen.getByText("text"), { key: "[", ctrlKey: true });
    fireEvent.keyDown(document.body, { key: "[" }); // no modifier
    fireEvent.keyDown(document.body, { key: "[", ctrlKey: true, shiftKey: true });
    expect(toggle).toHaveBeenCalledTimes(2);

    const dialog = document.createElement("div");
    dialog.setAttribute("role", "dialog");
    document.body.appendChild(dialog);
    fireEvent.keyDown(document.body, { key: "[", ctrlKey: true });
    expect(toggle).toHaveBeenCalledTimes(2);
    dialog.remove();
    fireEvent.keyDown(document.body, { key: "[", ctrlKey: true });
    expect(toggle).toHaveBeenCalledTimes(3);
  });

  it("does nothing where the sidebar cannot toggle (narrow screens, the drawer)", () => {
    const toggle = vi.fn();
    const { rerender } = renderWithProviders(<AppSidebar workspace={owner} collapsed onToggleCollapsed={toggle} />);
    rerender(
      <TooltipProvider>
        <AppSidebar workspace={owner} collapsed />
      </TooltipProvider>,
    );
    fireEvent.keyDown(document.body, { key: "[", ctrlKey: true });
    expect(toggle).not.toHaveBeenCalled();
  });
});

describe("reconnecting notice", () => {
  it("shows a pill above the account card while live updates are reconnecting, nothing while connected", () => {
    const { rerender } = renderSidebar({ userName: "Priya Nair" });
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    rerender({ reconnecting: true });
    const pill = screen.getByRole("status");
    expect(pill).toHaveTextContent("Reconnecting…");
    expect(pill.compareDocumentPosition(screen.getByText("Priya Nair")) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("collapsed: a dot named for screen readers", () => {
    renderSidebar({ collapsed: true, reconnecting: true });
    expect(screen.getByRole("status", { name: "Reconnecting…" })).toBeInTheDocument();
    expect(screen.queryByText("Reconnecting…")).not.toBeInTheDocument();
  });
});

describe("MobileNav (UX-SH-02)", () => {
  it("starts with the drawer closed and closes it when a link is tapped", async () => {
    const user = userEvent.setup();
    renderWithProviders(<MobileNav title="Home" workspace={owner} />);
    expect(screen.getByText("Home", { selector: "p" })).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Main" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Open menu" }));
    const nav = await screen.findByRole("navigation", { name: "Main" });
    expect(nav).toHaveAttribute("data-collapsed", "false");
    expect(within(nav).queryByRole("button", { name: /sidebar/ })).not.toBeInTheDocument();
    await user.click(within(nav).getByRole("link", { name: "Settings" }));
    expect(screen.queryByRole("navigation", { name: "Main" })).not.toBeInTheDocument();
  });

  it("puts Ask Social Hood in the top bar, beside the menu (FR-AGT-01)", () => {
    renderWithProviders(<MobileNav title="Home" workspace={owner} ask={<button type="button">Ask Social Hood</button>} />);
    const bar = screen.getByRole("banner");
    const buttons = within(bar).getAllByRole("button").map((button) => button.textContent || button.getAttribute("aria-label"));
    expect(buttons).toEqual(["Ask Social Hood", "Open menu"]);
  });
});

describe("Ask Social Hood in the sidebar (FR-AGT-01)", () => {
  it("sits under the header, above the sections, as a card around the button", async () => {
    const onClick = vi.fn();
    const ask = (
      <button type="button" onClick={onClick}>
        Ask Social Hood
      </button>
    );
    const { rerender } = renderSidebar({ ask });
    const nav = mainNav();
    const button = within(nav).getByRole("button", { name: "Ask Social Hood" });
    const home = within(nav).getByRole("link", { name: "Home" });
    expect(button.compareDocumentPosition(home) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    const card = screen.getByTestId("ask-card");
    expect(card).toContainElement(button);
    expect(card).toHaveTextContent("Your business assistant");
    expect(card).toHaveTextContent("AI");
    expect(card).toHaveTextContent("Ctrl K");
    await userEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();

    rerender({ collapsed: true });
    expect(within(mainNav()).getByRole("button", { name: "Ask Social Hood" })).toBeInTheDocument();
    expect(screen.queryByTestId("ask-card")).not.toBeInTheDocument();
  });
});
