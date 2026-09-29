import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Workspace } from "@/lib/api/types";
import { json, renderWithApi, workspace, type Call } from "@/test/api";

import WorkspaceSettingsPage from "./page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

// The real list has hundreds of zones; two keep the page fast to render.
beforeEach(() => {
  vi.spyOn(Intl, "supportedValuesOf").mockReturnValue(["Asia/Kolkata", "Europe/London"]);
});

function settings(overrides: Partial<Workspace> = {}): Workspace {
  return {
    id: workspace.id,
    name: workspace.name,
    slug: workspace.slug,
    timezone: "Asia/Kolkata",
    reply_language: "auto",
    status: "active",
    role: "owner",
    plan: "pro",
    automation_disclosure: null,
    checklist_dismissed_at: null,
    created_at: "2026-09-01T00:00:00Z",
    ...overrides,
  };
}

function renderPage(initial: Workspace) {
  const patches: unknown[] = [];
  const view = renderWithApi(<WorkspaceSettingsPage />, {
    handlers: {
      "GET /v1/w/:wid": () => json(initial),
      "PATCH /v1/w/:wid": (call: Call) => {
        patches.push(call.body);
        return json({ ...initial, ...(call.body as object) });
      },
    },
  });
  return { ...view, patches };
}

describe("automation disclosure (FR-AUT-11)", () => {
  it("turning it on fills the default line and saves only that", async () => {
    const user = userEvent.setup();
    const { patches } = renderPage(settings());

    const toggle = await screen.findByRole("switch", { name: "Say when a message is automated" });
    expect(toggle).not.toBeChecked();
    expect(screen.queryByLabelText("Line to add")).not.toBeInTheDocument();

    await user.click(toggle);
    expect(screen.getByLabelText("Line to add")).toHaveValue("Sent automatically");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(patches).toEqual([{ automation_disclosure: "Sent automatically" }]));
  });

  it("turning it off sends null", async () => {
    const user = userEvent.setup();
    const { patches } = renderPage(settings({ automation_disclosure: "Auto reply" }));

    const toggle = await screen.findByRole("switch", { name: "Say when a message is automated" });
    expect(toggle).toBeChecked();
    expect(screen.getByLabelText("Line to add")).toHaveValue("Auto reply");

    await user.click(toggle);
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(patches).toEqual([{ automation_disclosure: null }]));
  });

  it("an empty line while on is an error, not a save", async () => {
    const user = userEvent.setup();
    const { patches } = renderPage(settings({ automation_disclosure: "Auto reply" }));

    await user.clear(await screen.findByLabelText("Line to add"));
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Enter the line to add, or turn the disclosure off.");
    expect(patches).toEqual([]);
  });
});
