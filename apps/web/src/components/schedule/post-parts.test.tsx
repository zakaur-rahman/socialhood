import { render, screen } from "@testing-library/react";
import type { Route } from "next";
import { describe, expect, it, vi } from "vitest";

import { accountColors } from "@/lib/schedule/format";
import { IDENTITIES } from "@/lib/ui/identity";
import { account } from "@/test/api";
import { NOW } from "@/test/schedule";

import { AccountAvatar } from "./post-parts";
import { ScheduleProvider, type ScheduleContextValue } from "./schedule-context";

const accounts = [account({ id: "a1", username: "maple.bakery" }), account({ id: "a2", username: "maple.cakes" })];

const context: ScheduleContextValue = {
  wid: "w1",
  slug: "maple",
  timeZone: "Asia/Kolkata",
  now: NOW,
  accounts: new Map(accounts.map((a) => [a.id, a])),
  colors: accountColors(accounts),
  actions: {
    moveTo: vi.fn(),
    queue: vi.fn(),
    unschedule: vi.fn(),
    duplicate: vi.fn(),
    remove: vi.fn(),
    newPostAt: vi.fn(),
  },
  composerHref: (post) => `/w/maple/schedule/${post.id}` as Route,
  busyIds: new Set(),
};

function renderAvatar(accountId: string) {
  return render(
    <ScheduleProvider value={context}>
      <span data-testid="holder">
        <AccountAvatar account={context.accounts.get(accountId)} accountId={accountId} />
      </span>
    </ScheduleProvider>,
  );
}

describe("AccountAvatar", () => {
  it("rings the account in its identity and fills its fallback with the same identity (D-13)", () => {
    renderAvatar("a2");
    const identity = IDENTITIES[1];
    const avatar = screen.getByTestId("holder").querySelector("[data-slot=avatar]");
    expect(avatar).toHaveClass("ring-2", "ring-offset-1", "ring-offset-panel", identity.ring);
    const initial = screen.getByText("M");
    expect(initial).toHaveClass("bg-linear-135", ...identity.gradient.split(" "), "text-on-brand", "font-semibold");
    expect(initial).toHaveAttribute("aria-hidden", "true");
  });

  it("keeps an unknown account neutral: no identity, a line-strong ring", () => {
    renderAvatar("gone");
    const avatar = screen.getByTestId("holder").querySelector("[data-slot=avatar]");
    expect(avatar).toHaveClass("ring-line-strong");
    const initial = screen.getByText("A");
    expect(initial).toHaveClass("bg-raised", "text-fg");
    expect(initial).not.toHaveClass("bg-linear-135");
  });
});
