import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
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

function mainNav() {
  return screen.getByRole("navigation", { name: "Main" });
}

describe("AppSidebar (UX-SH-01)", () => {
  beforeEach(() => {
    pathname = "/w/aria/home";
  });

  it("shows labels, the workspace name and every section for an owner when expanded", () => {
    renderWithProviders(<AppSidebar workspace={owner} collapsed={false} userName="Priya Nair" />);
    const nav = mainNav();
    for (const label of ["Home", "Inbox", "Comments", "Automations", "Schedule", "Knowledge", "Settings", "Help"]) {
      expect(within(nav).getByText(label)).toBeInTheDocument();
    }
    expect(within(nav).getByText("Aria Label")).toBeInTheDocument();
    expect(within(nav).getByText("Priya Nair")).toBeInTheDocument();
    expect(nav).toHaveAttribute("data-collapsed", "false");
  });

  it("collapses to icons with accessible names and no visible labels", () => {
    renderWithProviders(<AppSidebar workspace={owner} collapsed />);
    const nav = mainNav();
    expect(nav).toHaveAttribute("data-collapsed", "true");
    expect(within(nav).queryByText("Inbox")).not.toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Inbox" })).toHaveAttribute("href", "/w/aria/inbox");
    expect(within(nav).queryByText("Upgrade")).not.toBeInTheDocument();
  });

  it("marks the active item", () => {
    pathname = "/w/aria/settings/workspace";
    renderWithProviders(<AppSidebar workspace={owner} collapsed={false} />);
    expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Home" })).not.toHaveAttribute("aria-current");
  });

  it("shows the unread badge on Inbox", () => {
    renderWithProviders(<AppSidebar workspace={owner} collapsed={false} unreadCount={3} />);
    expect(screen.getByLabelText("3 unread")).toHaveTextContent("3");
  });

  it("offers Upgrade on the Free plan only", () => {
    const { rerender } = renderWithProviders(<AppSidebar workspace={owner} collapsed={false} />);
    expect(screen.getByRole("link", { name: "Upgrade" })).toBeInTheDocument();
    rerender(
      <TooltipProvider>
        <AppSidebar workspace={{ ...owner, plan: "pro" }} collapsed={false} />
      </TooltipProvider>,
    );
    expect(screen.queryByRole("link", { name: "Upgrade" })).not.toBeInTheDocument();
    expect(screen.getByText("Pro plan")).toBeInTheDocument();
  });

  it("shows agents only Home, Inbox and Comments", () => {
    renderWithProviders(<AppSidebar workspace={{ ...owner, role: "agent" }} collapsed={false} />);
    const nav = mainNav();
    expect(within(nav).getByText("Comments")).toBeInTheDocument();
    for (const hidden of ["Automations", "Schedule", "Knowledge"]) {
      expect(within(nav).queryByText(hidden)).not.toBeInTheDocument();
    }
  });

  it("toggles collapse when the host allows it", async () => {
    const toggle = vi.fn();
    renderWithProviders(<AppSidebar workspace={owner} collapsed={false} onToggleCollapsed={toggle} />);
    await userEvent.click(screen.getByRole("button", { name: "Collapse sidebar" }));
    expect(toggle).toHaveBeenCalledOnce();
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
    await user.click(within(nav).getByRole("link", { name: "Settings" }));
    expect(screen.queryByRole("navigation", { name: "Main" })).not.toBeInTheDocument();
  });
});
