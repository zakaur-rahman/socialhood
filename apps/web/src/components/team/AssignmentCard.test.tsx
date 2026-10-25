import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it } from "vitest";

import type { Assignable, AssignmentOverview } from "@/lib/api/types";
import { json, noContent, renderWithApi } from "@/test/api";

import { AssignmentCard } from "./AssignmentCard";

beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});

const priya: Assignable = {
  user_id: "u1",
  name: "Priya Nair",
  avatar_url: null,
  role: "owner",
  available: true,
  open_conversations: 3,
  is_you: true,
};
const sam: Assignable = { ...priya, user_id: "u2", name: "Sam Rao", role: "agent", open_conversations: 1, is_you: false };

function setup(permissions: string[], roundRobin = false) {
  const overview: AssignmentOverview = { round_robin: roundRobin, members: [priya, sam] };
  const sent: { path: string; body: unknown }[] = [];
  const view = renderWithApi(<AssignmentCard />, {
    handlers: {
      "GET /v1/w/:wid/permissions": () => json({ role: "owner", permissions }),
      "GET /v1/w/:wid/assignment": () => json(overview),
      "PUT /v1/w/:wid/assignment/settings": (call) => {
        sent.push({ path: call.path, body: call.body });
        return json({ ...overview, round_robin: true });
      },
      "PUT /v1/w/:wid/members/:user_id/availability": (call) => {
        sent.push({ path: call.path, body: call.body });
        return noContent();
      },
    },
  });
  return { ...view, sent };
}

describe("AssignmentCard (GR-20)", () => {
  it("lists each member's availability and open conversations", async () => {
    setup(["settings.manage"]);
    const rows = await screen.findAllByTestId("availability-row");
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByText("3 open conversations")).toBeInTheDocument();
    expect(within(rows[1]).getByText("1 open conversation")).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "Round-robin" })).not.toBeChecked();
  });

  it("an admin turns round-robin on and sets anyone's availability", async () => {
    const { sent } = setup(["settings.manage"]);
    await userEvent.click(await screen.findByRole("switch", { name: "Round-robin" }));
    await userEvent.click(screen.getByRole("switch", { name: "Sam Rao is available" }));
    await waitFor(() => expect(sent).toHaveLength(2));
    expect(sent[0]).toEqual({ path: "/v1/w/w1/assignment/settings", body: { round_robin: true } });
    expect(sent[1]).toEqual({ path: "/v1/w/w1/members/u2/availability", body: { available: false } });
  });

  it("an agent sets only their own availability and cannot change round-robin", async () => {
    setup(["inbox.reply"]);
    expect(await screen.findByRole("switch", { name: "Round-robin" })).toBeDisabled();
    expect(screen.getByRole("switch", { name: "Sam Rao is available" })).toBeDisabled();
    expect(screen.getByRole("switch", { name: "Priya Nair is available" })).toBeEnabled();
  });
});
