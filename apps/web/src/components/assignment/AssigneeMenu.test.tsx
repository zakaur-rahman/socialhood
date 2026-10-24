import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it } from "vitest";

import type { Assignable, AssignmentOverview } from "@/lib/api/types";
import { conversation, json, renderWithApi } from "@/test/api";

import { AssigneeMenu, mayChoose } from "./AssigneeMenu";

beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});

const you: Assignable = {
  user_id: "u1",
  name: "Priya Nair",
  avatar_url: null,
  role: "agent",
  available: true,
  open_conversations: 2,
  is_you: true,
};
const sam: Assignable = { ...you, user_id: "u2", name: "Sam Rao", available: false, open_conversations: 0, is_you: false };

function setup(permissions: string[], assignee: { user_id: string; name: string } | null = null) {
  const overview: AssignmentOverview = { round_robin: false, members: [you, sam] };
  const done: unknown[] = [];
  const view = renderWithApi(<AssigneeMenu conversation={conversation({ assignee })} />, {
    handlers: {
      "GET /v1/w/:wid/permissions": () => json({ role: "agent", permissions }),
      "GET /v1/w/:wid/assignment": () => json(overview),
      "PUT /v1/w/:wid/conversations/:id/assignee": (call) => {
        done.push(call.body);
        return json(conversation({ assignee: { user_id: "u1", name: "Priya Nair", avatar_url: null } }));
      },
      "PUT /v1/w/:wid/members/:user_id/availability": (call) => {
        done.push(call.body);
        return new Response(null, { status: 204 });
      },
    },
  });
  return { ...view, done };
}

describe("mayChoose", () => {
  it("lets owners and admins choose anyone", () => {
    expect(mayChoose({ isAdmin: true, youId: "u1", current: "u2", target: "u3" })).toBe(true);
    expect(mayChoose({ isAdmin: true, youId: "u1", current: null, target: null })).toBe(true);
  });

  it("lets an agent take a free conversation, and release or hand on their own", () => {
    expect(mayChoose({ isAdmin: false, youId: "u1", current: null, target: "u1" })).toBe(true);
    expect(mayChoose({ isAdmin: false, youId: "u1", current: "u1", target: null })).toBe(true);
    expect(mayChoose({ isAdmin: false, youId: "u1", current: "u1", target: "u2" })).toBe(true);
  });

  it("keeps an agent from giving out a free conversation or taking a colleague's", () => {
    expect(mayChoose({ isAdmin: false, youId: "u1", current: null, target: "u2" })).toBe(false);
    expect(mayChoose({ isAdmin: false, youId: "u1", current: "u2", target: "u1" })).toBe(false);
    expect(mayChoose({ isAdmin: false, youId: "u1", current: "u2", target: null })).toBe(false);
  });
});

describe("AssigneeMenu (GR-20)", () => {
  it("names who has the conversation on the button", async () => {
    setup(["inbox.reply"], { user_id: "u2", name: "Sam Rao" });
    expect(await screen.findByRole("button", { name: "Assigned to Sam Rao. Change" })).toBeInTheDocument();
  });

  it("offers Assign when nobody has it, and an agent takes it", async () => {
    const { done } = setup(["inbox.reply"]);
    await userEvent.click(await screen.findByRole("button", { name: "Assign this conversation" }));
    const mine = await screen.findByRole("menuitemradio", { name: /Priya Nair \(you\)/ });
    // Not for an agent to give out.
    expect(screen.getByRole("menuitemradio", { name: /Sam Rao/ })).toHaveAttribute("aria-disabled", "true");
    await userEvent.click(mine);
    await waitFor(() => expect(done).toEqual([{ user_id: "u1" }]));
  });

  it("an admin can give it to a member who is away, and the menu says so", async () => {
    const { done } = setup(["inbox.reply", "settings.manage"]);
    await userEvent.click(await screen.findByRole("button", { name: "Assign this conversation" }));
    const away = await screen.findByRole("menuitemradio", { name: /Sam Rao.*away/ });
    await userEvent.click(away);
    await waitFor(() => expect(done).toEqual([{ user_id: "u2" }]));
  });

  it("turns your own availability on or off", async () => {
    const { done } = setup(["inbox.reply"]);
    await userEvent.click(await screen.findByRole("button", { name: "Assign this conversation" }));
    await userEvent.click(await screen.findByRole("menuitemcheckbox", { name: /available for new conversations/ }));
    await waitFor(() => expect(done).toEqual([{ available: false }]));
  });
});
