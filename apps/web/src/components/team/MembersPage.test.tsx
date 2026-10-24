import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it } from "vitest";

import type { TeamInvitation, TeamMember, WorkspacePermissions } from "@/lib/api/types";
import { json, noContent, problem, renderWithApi, workspace } from "@/test/api";

import { MembersPage } from "./MembersPage";

beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});

const AGENT_PERMISSIONS = ["inbox.reply", "contacts.tag"];
const ADMIN_PERMISSIONS = [...AGENT_PERMISSIONS, "members.read", "members.invite", "audit.read"];
const OWNER_PERMISSIONS = [...ADMIN_PERMISSIONS, "members.manage", "ownership.transfer"];

const owner: TeamMember = {
  user_id: "u1",
  name: "Priya Nair",
  email: "priya@example.com",
  avatar_url: null,
  role: "owner",
  last_seen_at: "2026-10-27T10:00:00Z",
  joined_at: "2026-09-01T10:00:00Z",
  is_you: true,
};
const sam: TeamMember = {
  user_id: "u2",
  name: "Sam Rao",
  email: "sam@example.com",
  avatar_url: null,
  role: "agent",
  last_seen_at: null,
  joined_at: "2026-10-01T10:00:00Z",
  is_you: false,
};
const invited: TeamInvitation = {
  id: "i1",
  email: "kim@example.com",
  role: "agent",
  status: "pending",
  invited_by_name: "Priya Nair",
  expires_at: "2026-11-10T10:00:00Z",
  created_at: "2026-10-27T10:00:00Z",
};

type Handlers = NonNullable<Parameters<typeof renderWithApi>[1]>["handlers"];

function setup(permissions: string[], extra: Handlers = {}, members = [owner, sam], pending = [invited]) {
  const perms: WorkspacePermissions = { role: "owner", permissions };
  return renderWithApi(<MembersPage />, {
    ws: workspace,
    handlers: {
      "GET /v1/w/:wid/permissions": () => json(perms),
      "GET /v1/w/:wid/members": () =>
        json({ items: members, seats: { members: members.length, pending_invitations: pending.length, limit: 3 } }),
      "GET /v1/w/:wid/invitations": () => json({ items: pending }),
      ...extra,
    },
  });
}

describe("MembersPage (GR-19)", () => {
  it("lists members with role and last active, and the seats used", async () => {
    setup(OWNER_PERMISSIONS);
    const rows = await screen.findAllByTestId("member-row");
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByText("Priya Nair")).toBeInTheDocument();
    expect(within(rows[0]).getByText("Owner")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Not active yet")).toBeInTheDocument();
    expect(screen.getByTestId("seat-summary")).toHaveTextContent("2 of 3 seats used, plus 1 pending invitation.");
    expect(screen.getByText("kim@example.com")).toBeInTheDocument();
  });

  it("an owner can change a role, remove a member and make someone the owner", async () => {
    setup(OWNER_PERMISSIONS);
    await screen.findAllByTestId("member-row");
    expect(screen.getByRole("combobox", { name: "Role of Sam Rao" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove Sam Rao" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Make Sam Rao the owner" })).toBeInTheDocument();
    // Not on yourself.
    expect(screen.queryByRole("button", { name: "Remove Priya Nair" })).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "Role of Priya Nair" })).not.toBeInTheDocument();
  });

  it("an admin can invite but not change roles, remove or transfer", async () => {
    setup(ADMIN_PERMISSIONS);
    await screen.findAllByTestId("member-row");
    expect(screen.getByRole("button", { name: /Invite/ })).toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "Role of Sam Rao" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Remove Sam Rao" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /the owner/ })).not.toBeInTheDocument();
  });

  it("an agent sees an explanation and no list", async () => {
    const { calls } = setup(AGENT_PERMISSIONS);
    expect(await screen.findByText("Members are for owners and admins")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Invite/ })).not.toBeInTheDocument();
    expect(calls.some((call) => call.path.endsWith("/members"))).toBe(false);
  });

  it("invites by email with a role", async () => {
    const user = userEvent.setup();
    let sent: unknown;
    setup(OWNER_PERMISSIONS, {
      "POST /v1/w/:wid/invitations": (call) => {
        sent = call.body;
        return json({ ...invited, id: "i2", email: "lee@example.com" }, 201);
      },
    });
    await screen.findAllByTestId("member-row");
    await user.click(screen.getByRole("button", { name: /Invite/ }));
    await user.type(await screen.findByLabelText("Email"), "lee@example.com");
    await user.click(screen.getByRole("button", { name: "Send invitation" }));
    await waitFor(() => expect(sent).toEqual({ email: "lee@example.com", role: "agent" }));
  });

  it("shows a refusal next to the email field", async () => {
    const user = userEvent.setup();
    setup(OWNER_PERMISSIONS, {
      "POST /v1/w/:wid/invitations": () =>
        problem(409, "conflict", "That person is already a member."),
    });
    await screen.findAllByTestId("member-row");
    await user.click(screen.getByRole("button", { name: /Invite/ }));
    await user.type(await screen.findByLabelText("Email"), "sam@example.com");
    await user.click(screen.getByRole("button", { name: "Send invitation" }));
    expect(await screen.findByText("That person is already a member.")).toBeInTheDocument();
  });

  it("removes a member after asking", async () => {
    const user = userEvent.setup();
    let removed = "";
    setup(OWNER_PERMISSIONS, {
      "DELETE /v1/w/:wid/members/:user_id": (_call, params) => {
        removed = params.user_id;
        return noContent();
      },
    });
    await screen.findAllByTestId("member-row");
    await user.click(screen.getByRole("button", { name: "Remove Sam Rao" }));
    await user.click(await screen.findByRole("button", { name: "Remove member" }));
    await waitFor(() => expect(removed).toBe("u2"));
  });

  it("transfers ownership only after the workspace name is typed", async () => {
    const user = userEvent.setup();
    let sent: unknown;
    setup(OWNER_PERMISSIONS, {
      "POST /v1/w/:wid/ownership-transfer": (call) => {
        sent = call.body;
        return json({ items: [owner, sam], seats: { members: 2, pending_invitations: 0, limit: 3 } });
      },
    });
    await screen.findAllByTestId("member-row");
    await user.click(screen.getByRole("button", { name: "Make Sam Rao the owner" }));
    const confirm = await screen.findByRole("button", { name: "Make owner" });
    expect(confirm).toBeDisabled();
    await user.type(screen.getByLabelText(/Type Maple Bakery to confirm/), "Maple Bakery");
    await user.click(confirm);
    await waitFor(() => expect(sent).toEqual({ user_id: "u2", confirm_name: "Maple Bakery" }));
  });

  it("resends and revokes an invitation", async () => {
    const user = userEvent.setup();
    const seen: string[] = [];
    setup(OWNER_PERMISSIONS, {
      "POST /v1/w/:wid/invitations/:invitation_id/resend": (call) => {
        seen.push(call.path);
        return json(invited);
      },
      "DELETE /v1/w/:wid/invitations/:invitation_id": (call) => {
        seen.push(call.path);
        return noContent();
      },
    });
    await screen.findAllByTestId("invitation-row");
    await user.click(screen.getByRole("button", { name: "Resend the invitation to kim@example.com" }));
    await user.click(screen.getByRole("button", { name: "Revoke the invitation to kim@example.com" }));
    await user.click(await screen.findByRole("button", { name: "Revoke invitation" }));
    await waitFor(() => expect(seen).toHaveLength(2));
  });
});
