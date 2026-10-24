import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { json, renderWithApi, workspace } from "@/test/api";

import { ContactSequences } from "./ContactSequences";

const enrolment = {
  id: "e1",
  sequence_id: "s1",
  sequence_name: "Welcome follow-up",
  contact: { id: "c1", display_name: "Asha Rao", username: null },
  status: "stopped",
  next_step: null,
  step_count: 3,
  next_due_at: null,
  enrolled_at: "2026-10-25T09:00:00Z",
  finished_at: "2026-10-27T09:00:00Z",
  entry_event: "Tagged Follow up",
  stop_reason: "reply",
  stop_text: "They replied",
  last_run: null,
};

function setup(items: unknown[], role: "owner" | "agent" = "owner") {
  return renderWithApi(<ContactSequences contactId="c1" />, {
    ws: { ...workspace, role },
    handlers: { "GET /v1/w/:wid/contacts/:id/sequences": () => json({ items }) },
  });
}

describe("a contact's sequences (GR-24)", () => {
  it("says when they are in none", async () => {
    setup([]);
    expect(await screen.findByText("Not in any sequence.")).toBeInTheDocument();
  });

  it("shows each sequence with what happened at every step and why it stopped", async () => {
    setup([
      {
        enrolment,
        runs: [
          { position: 1, status: "sent", reason: null, at: "2026-10-26T09:00:00Z" },
          { position: 2, status: "skipped", reason: "They opted out of WhatsApp marketing messages.", at: "2026-10-27T09:00:00Z" },
        ],
      },
    ]);
    const item = await screen.findByTestId("contact-sequence");
    expect(within(item).getByRole("link", { name: "Welcome follow-up" })).toHaveAttribute("href", "/w/maple/sequences/s1");
    expect(item).toHaveTextContent("Stopped");
    expect(item).toHaveTextContent("They replied");
    expect(item).toHaveTextContent("Step 1: sent");
    expect(item).toHaveTextContent("Step 2: skipped. They opted out of WhatsApp marketing messages.");
  });

  it("shows an agent the sequence's name without a link", async () => {
    setup([{ enrolment, runs: [] }], "agent");
    const item = await screen.findByTestId("contact-sequence");
    expect(within(item).queryByRole("link")).not.toBeInTheDocument();
    expect(item).toHaveTextContent("Welcome follow-up");
  });
});
