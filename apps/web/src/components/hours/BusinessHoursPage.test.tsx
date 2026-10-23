import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { BusinessHours, BusinessHoursOverview } from "@/lib/api/types";
import { json, noContent, renderWithApi, workspace } from "@/test/api";

import { BusinessHoursPage } from "./BusinessHoursPage";

const days = [0, 1, 2, 3, 4, 5, 6].map((day) => ({ day, ranges: day < 5 ? [{ start: "09:00", end: "17:00" }] : [] }));

const workspaceHours: BusinessHours = {
  social_account_id: null,
  configured: true,
  enabled: true,
  days,
  away_enabled: true,
  away_message: "We're closed, back at 9.",
  auto_mode: "always",
  open_now: true,
};

type Handlers = NonNullable<Parameters<typeof renderWithApi>[1]>["handlers"];

function overview(overrides: Partial<BusinessHoursOverview> = {}): BusinessHoursOverview {
  return {
    timezone: "Asia/Kolkata",
    workspace: workspaceHours,
    accounts: [{ social_account_id: "a1", platform: "instagram", username: "maple.bakery", display_name: "Maple", override: null }],
    ...overrides,
  };
}

function setup(data: BusinessHoursOverview, handlers: Handlers = {}, ws = workspace) {
  return renderWithApi(<BusinessHoursPage />, {
    ws,
    handlers: { "GET /v1/w/:wid/business-hours": () => json(data), ...handlers },
  });
}

function invalid(field: string, message: string): Response {
  return new Response(
    JSON.stringify({
      type: "about:blank",
      title: "The request is not valid",
      status: 422,
      code: "validation_error",
      errors: [{ field, message }],
    }),
    { status: 422, headers: { "Content-Type": "application/problem+json" } },
  );
}

describe("BusinessHoursPage (GR-22)", () => {
  it("shows the week in the workspace time zone with the away message", async () => {
    setup(overview());
    const week = await screen.findByRole("list", { name: "Opening hours" });
    expect(within(week).getAllByRole("listitem")).toHaveLength(7);
    expect(within(week).getByLabelText("Monday opens at")).toHaveValue("09:00");
    expect(within(week).getByLabelText("Monday closes at")).toHaveValue("17:00");
    expect(within(week).getAllByText("Closed")).toHaveLength(2); // Saturday and Sunday
    expect(screen.getByLabelText("Message")).toHaveValue("We're closed, back at 9.");
    expect(screen.getAllByText(/Asia\/Kolkata/).length).toBeGreaterThan(0);
  });

  it("saves the whole week", async () => {
    const user = userEvent.setup();
    let sent: { enabled: boolean; days: { day: number }[]; away_message: string | null } | undefined;
    setup(overview(), {
      "PUT /v1/w/:wid/business-hours": (call) => {
        sent = call.body as typeof sent;
        return json(workspaceHours);
      },
    });
    const closes = await screen.findByLabelText("Monday closes at");
    await user.clear(closes);
    await user.type(closes, "18:30");
    await user.click(screen.getAllByRole("button", { name: "Save hours" })[0]);
    await waitFor(() => expect(sent).toBeDefined());
    expect(sent?.enabled).toBe(true);
    expect(sent?.days.map((d) => d.day)).toEqual([0, 1, 2, 3, 4, 5, 6]);
    expect(sent?.days[0]).toEqual({ day: 0, ranges: [{ start: "09:00", end: "18:30" }] });
    expect(sent?.away_message).toBe("We're closed, back at 9.");
  });

  it("a closing time of 00:00 is saved as midnight", async () => {
    const user = userEvent.setup();
    let sent: { days: { ranges: { end: string }[] }[] } | undefined;
    setup(overview(), {
      "PUT /v1/w/:wid/business-hours": (call) => {
        sent = call.body as typeof sent;
        return json(workspaceHours);
      },
    });
    const closes = await screen.findByLabelText("Friday closes at");
    await user.clear(closes);
    await user.type(closes, "00:00");
    await user.click(screen.getAllByRole("button", { name: "Save hours" })[0]);
    await waitFor(() => expect(sent).toBeDefined());
    expect(sent?.days[4].ranges[0].end).toBe("24:00");
  });

  it("adds and removes a range on a day", async () => {
    const user = userEvent.setup();
    setup(overview());
    await screen.findByRole("list", { name: "Opening hours" });
    await user.click(screen.getByRole("button", { name: "Add Saturday hours" }));
    expect(screen.getByLabelText("Saturday opens at")).toHaveValue("09:00");
    await user.click(screen.getByRole("button", { name: "Remove Saturday hours 1" }));
    expect(screen.queryByLabelText("Saturday opens at")).not.toBeInTheDocument();
  });

  it("shows the API's message under the range it names", async () => {
    const user = userEvent.setup();
    setup(overview(), {
      "PUT /v1/w/:wid/business-hours": () => invalid("days.1.ranges.0.end", "Closing time must be after opening time."),
    });
    await user.click((await screen.findAllByRole("button", { name: "Save hours" }))[0]);
    expect(await screen.findByText("Closing time must be after opening time.")).toBeInTheDocument();
  });

  it("will not save hours that are on with nothing open", async () => {
    const user = userEvent.setup();
    setup(overview({ workspace: { ...workspaceHours, days: days.map((d) => ({ ...d, ranges: [] })) } }));
    expect(await screen.findByText("Add at least one opening time, or turn business hours off.")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Save hours" })[0]).toBeDisabled();
    await user.click(screen.getAllByRole("switch", { name: "Use business hours" })[0]);
    expect(screen.getAllByRole("button", { name: "Save hours" })[0]).toBeEnabled();
  });

  it("an account can take its own hours", async () => {
    const user = userEvent.setup();
    let saved: unknown;
    setup(overview(), {
      "PUT /v1/w/:wid/social-accounts/:id/business-hours": (call) => {
        saved = call.body;
        return json({ ...workspaceHours, social_account_id: "a1" });
      },
    });
    expect(await screen.findByText(/Uses the workspace hours: Mon to Fri 09:00 to 17:00/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Set its own hours" }));
    expect(screen.getByRole("button", { name: "Use the workspace hours" })).toBeInTheDocument();
    const buttons = screen.getAllByRole("button", { name: "Save hours" });
    await user.click(buttons[buttons.length - 1]);
    await waitFor(() => expect(saved).toBeDefined());
  });

  it("an account with its own hours can return to the workspace's", async () => {
    const user = userEvent.setup();
    const own: BusinessHours = { ...workspaceHours, social_account_id: "a1" };
    const { calls } = setup(
      overview({
        accounts: [{ social_account_id: "a1", platform: "instagram", username: "maple.bakery", display_name: null, override: own }],
      }),
      { "DELETE /v1/w/:wid/social-accounts/:id/business-hours": () => noContent() },
    );
    await user.click(await screen.findByRole("button", { name: "Use the workspace hours" }));
    await waitFor(() => expect(calls.some((c) => c.method === "DELETE")).toBe(true));
  });

  it("agents read the hours but cannot save them", async () => {
    setup(overview(), {}, { ...workspace, role: "agent" });
    await screen.findByRole("list", { name: "Opening hours" });
    expect(screen.getByLabelText("Monday opens at")).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Save hours" })).not.toBeInTheDocument();
    expect(screen.getByText("Owners and admins can change business hours.")).toBeInTheDocument();
  });
});
