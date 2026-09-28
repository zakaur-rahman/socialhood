import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { NotificationItem, SocialAccount } from "@/lib/api/types";

import { accountBanners } from "./AppShell";
import { NotificationsPanel } from "./NotificationsButton";

vi.mock("@clerk/nextjs", () => ({ UserButton: () => null }));

const reconnect: NotificationItem = {
  id: "n1",
  type: "account_needs_reconnect",
  severity: "critical",
  title: "Reconnect @maple.bakery",
  body: "@maple.bakery needs reconnecting to keep receiving messages.",
  link: "/settings/connections",
  read_at: null,
  created_at: "2026-09-28T11:55:00Z",
};

const now = new Date("2026-09-28T12:00:00Z");

describe("NotificationsPanel (UX-SH-04)", () => {
  it("lists notifications with an unread dot, a relative time and a workspace link", async () => {
    const onOpen = vi.fn();
    render(
      <NotificationsPanel items={[reconnect]} unread={1} slug="maple" marking={false} onMarkAllRead={vi.fn()} onOpen={onOpen} now={now} />,
    );
    const link = screen.getByRole("link", { name: /Reconnect @maple.bakery/ });
    expect(link).toHaveAttribute("href", "/w/maple/settings/connections");
    expect(screen.getByLabelText("unread")).toBeInTheDocument();
    expect(screen.getByText("5m")).toBeInTheDocument();
    await userEvent.click(link);
    expect(onOpen).toHaveBeenCalledWith(reconnect);
  });

  it("marks all read, and only when something is unread", async () => {
    const onMarkAllRead = vi.fn();
    const { rerender } = render(
      <NotificationsPanel items={[reconnect]} unread={1} slug="maple" marking={false} onMarkAllRead={onMarkAllRead} onOpen={vi.fn()} now={now} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Mark all read" }));
    expect(onMarkAllRead).toHaveBeenCalledOnce();

    rerender(
      <NotificationsPanel
        items={[{ ...reconnect, read_at: "2026-09-28T11:58:00Z" }]}
        unread={0}
        slug="maple"
        marking={false}
        onMarkAllRead={onMarkAllRead}
        onOpen={vi.fn()}
        now={now}
      />,
    );
    expect(screen.getByRole("button", { name: "Mark all read" })).toBeDisabled();
    expect(screen.queryByLabelText("unread")).not.toBeInTheDocument();
  });

  it("shows the empty state", () => {
    render(<NotificationsPanel items={[]} unread={0} slug="maple" marking={false} onMarkAllRead={vi.fn()} onOpen={vi.fn()} />);
    expect(screen.getByText("No notifications")).toBeInTheDocument();
  });
});

describe("account banners (F-05)", () => {
  const account = (status: SocialAccount["status"], username: string): SocialAccount =>
    ({ id: username, status, username }) as SocialAccount;

  it("raises one banner per account that needs reconnecting", () => {
    const banners = accountBanners(
      [account("active", "a"), account("needs_reconnect", "maple.bakery"), account("error", "b")],
      "maple",
    );
    expect(banners).toEqual([
      {
        id: "reconnect:maple.bakery",
        tone: "warning",
        message: "Reconnect @maple.bakery to keep receiving messages",
        action: { label: "Reconnect", href: "/w/maple/settings/connections" },
      },
    ]);
  });
});
