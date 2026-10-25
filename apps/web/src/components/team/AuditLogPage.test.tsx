import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it } from "vitest";

import { json, renderWithApi } from "@/test/api";

import { actionLabel, AuditLogPage } from "./AuditLogPage";

beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});

const event = {
  id: "e1",
  at: "2026-10-27T10:00:00Z",
  actor_user_id: "u1",
  actor_name: "Priya Nair",
  action: "automation.created",
  target_type: "automation",
  target_id: "a1",
  detail: { count: 2 },
};

function setup(permissions: string[], hasMore = false) {
  return renderWithApi(<AuditLogPage />, {
    handlers: {
      "GET /v1/w/:wid/permissions": () => json({ role: "owner", permissions }),
      "GET /v1/w/:wid/members": () =>
        json({ items: [], seats: { members: 1, pending_invitations: 0, limit: 3 } }),
      "GET /v1/w/:wid/audit-events": () =>
        json({ items: [event], has_more: hasMore, actions: ["automation.created", "member.removed"] }),
    },
  });
}

describe("AuditLogPage (GR-19)", () => {
  it("labels an action in plain words", () => {
    expect(actionLabel("member.role_changed")).toBe("Member role changed");
  });

  it("lists who did what, newest first", async () => {
    setup(["audit.read", "members.read"]);
    const row = await screen.findByTestId("audit-row");
    expect(within(row).getByText("Automation created")).toBeInTheDocument();
    expect(within(row).getByText("Priya Nair")).toBeInTheDocument();
    expect(within(row).getByText("count: 2")).toBeInTheDocument();
  });

  it("filters by action and pages", async () => {
    const user = userEvent.setup();
    const { calls } = setup(["audit.read", "members.read"], true);
    await screen.findByTestId("audit-row");
    await user.click(screen.getByRole("button", { name: "Older" }));
    await waitFor(() => expect(calls.some((c) => c.url.searchParams.get("offset") === "30")).toBe(true));
    expect(screen.getByRole("button", { name: "Newer" })).toBeEnabled();
  });

  it("explains itself to someone without access and asks for nothing", async () => {
    const { calls } = setup(["inbox.reply"]);
    expect(await screen.findByText("The audit log is for owners and admins")).toBeInTheDocument();
    expect(calls.some((c) => c.path.endsWith("/audit-events"))).toBe(false);
  });
});
