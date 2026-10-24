import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { SequenceEnrolment } from "@/lib/api/types";
import { json, renderWithApi } from "@/test/api";

import { SequencePeople } from "./SequencePeople";

function person(values: Partial<SequenceEnrolment> = {}): SequenceEnrolment {
  return {
    id: "e1",
    sequence_id: "s1",
    sequence_name: "Welcome follow-up",
    contact: { id: "c1", display_name: "Asha Rao", username: null },
    status: "active",
    next_step: 2,
    step_count: 3,
    next_due_at: "2026-10-28T09:00:00Z",
    enrolled_at: "2026-10-25T09:00:00Z",
    finished_at: null,
    entry_event: "Tagged Follow up",
    stop_reason: null,
    stop_text: null,
    last_run: { position: 1, status: "sent", reason: null, at: "2026-10-26T09:00:00Z" },
    ...values,
  } as SequenceEnrolment;
}

function setup(items: SequenceEnrolment[]) {
  const stopped: string[] = [];
  const queries: (string | null)[] = [];
  const view = renderWithApi(<SequencePeople sequenceId="s1" />, {
    handlers: {
      "GET /v1/w/:wid/sequences/:id/enrolments": (call) => {
        queries.push(call.url.searchParams.get("status"));
        return json({ items, total: items.length, has_more: false });
      },
      "POST /v1/w/:wid/sequences/:id/enrolments/:eid/stop": (_call, params) => {
        stopped.push(params.eid);
        return json(person({ id: params.eid, status: "stopped", stop_reason: "member", stop_text: "Taken out by your team" }));
      },
    },
  });
  return { ...view, stopped, queries };
}

describe("the people in a sequence (GR-24)", () => {
  it("shows each person's status, step, due time, last step and why one stopped", async () => {
    setup([
      person(),
      person({
        id: "e2",
        contact: { id: "c2", display_name: "Ben Cole", username: null },
        status: "stopped",
        next_step: null,
        stop_reason: "reply",
        stop_text: "They replied",
        last_run: { position: 1, status: "skipped", reason: "They haven't agreed to WhatsApp marketing messages.", at: "2026-10-26T09:00:00Z" },
      }),
    ]);
    const rows = await screen.findAllByTestId("person-row");
    expect(rows[0]).toHaveTextContent("Asha Rao");
    expect(rows[0]).toHaveTextContent("On step 2 of 3");
    expect(rows[0]).toHaveTextContent("Step 1: sent");
    expect(within(rows[0]).getByText("In it")).toBeInTheDocument();
    expect(rows[1]).toHaveTextContent("They replied");
    expect(rows[1]).toHaveTextContent("Step 1: skipped. They haven't agreed to WhatsApp marketing messages.");
    expect(within(rows[1]).queryByRole("button", { name: /Take/ })).not.toBeInTheDocument();
  });

  it("takes a person out of the sequence", async () => {
    const user = userEvent.setup();
    const { stopped } = setup([person()]);
    await user.click(await screen.findByRole("button", { name: "Take Asha Rao out of the sequence" }));
    await waitFor(() => expect(stopped).toEqual(["e1"]));
  });

  it("filters by status", async () => {
    const user = userEvent.setup();
    const { queries } = setup([person()]);
    await screen.findAllByTestId("person-row");
    await user.click(screen.getByRole("radio", { name: "Stopped" }));
    await waitFor(() => expect(queries).toContain("stopped"));
  });

  it("says when nobody has joined", async () => {
    setup([]);
    expect(await screen.findByText("Nobody has joined yet")).toBeInTheDocument();
  });
});
