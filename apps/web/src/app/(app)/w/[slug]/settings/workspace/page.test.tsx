import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Workspace } from "@/lib/api/types";
import { account, json, problem, renderWithApi, workspace, type Call } from "@/test/api";

import WorkspaceSettingsPage from "./page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/w/maple/settings/workspace",
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
    member_count: 1,
    ...overrides,
  };
}

function renderPage(initial: Workspace, patch?: (call: Call) => Response | Promise<Response>) {
  const patches: unknown[] = [];
  const view = renderWithApi(<WorkspaceSettingsPage />, {
    handlers: {
      "GET /v1/w/:wid": () => json(initial),
      "GET /v1/w/:wid/social-accounts": () =>
        json({
          items: [
            account({ id: "a1" }),
            account({ id: "a2", platform: "whatsapp", username: null }),
            account({ id: "a3", status: "disconnected" }),
          ],
        }),
      "PATCH /v1/w/:wid": (call: Call) => {
        patches.push(call.body);
        return patch ? patch(call) : json({ ...initial, ...(call.body as object) });
      },
    },
  });
  const bar = () => screen.getByRole("region", { name: "Save changes" });
  return { ...view, patches, bar };
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
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(patches).toEqual([{ automation_disclosure: "Sent automatically" }]));
  });

  it("turning it off sends null", async () => {
    const user = userEvent.setup();
    const { patches } = renderPage(settings({ automation_disclosure: "Auto reply" }));

    const toggle = await screen.findByRole("switch", { name: "Say when a message is automated" });
    expect(toggle).toBeChecked();
    expect(screen.getByLabelText("Line to add")).toHaveValue("Auto reply");

    await user.click(toggle);
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(patches).toEqual([{ automation_disclosure: null }]));
  });

  it("an empty line while on is an error, not a save", async () => {
    const user = userEvent.setup();
    const { patches } = renderPage(settings({ automation_disclosure: "Auto reply" }));

    await user.clear(await screen.findByLabelText("Line to add"));
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Enter the line to add, or turn the disclosure off.");
    expect(patches).toEqual([]);
  });
});

describe("the save bar (C-066)", () => {
  it("is clean until something changes; Reset puts the saved values back", async () => {
    const user = userEvent.setup();
    const { patches, bar } = renderPage(settings());
    const name = await screen.findByLabelText("Workspace name");
    expect(within(bar()).getByRole("status")).toHaveTextContent("All changes saved");
    expect(within(bar()).queryByRole("button", { name: "Save" })).toBeNull();
    expect(screen.getByText("12 / 80")).toBeInTheDocument();

    await user.clear(name);
    await user.type(name, "Maple & Co");
    expect(within(bar()).getByRole("status")).toHaveTextContent("Unsaved changes");
    expect(screen.getByText("10 / 80")).toBeInTheDocument();

    await user.click(within(bar()).getByRole("button", { name: "Reset" }));
    expect(name).toHaveValue("Maple Bakery");
    expect(within(bar()).getByRole("status")).toHaveTextContent("All changes saved");
    expect(patches).toEqual([]);
  });

  it("Save sends what changed, shows a spinner meanwhile, then is clean", async () => {
    const user = userEvent.setup();
    let finish: (response: Response) => void = () => {};
    const { patches, bar } = renderPage(settings(), () => new Promise<Response>((resolve) => (finish = resolve)));
    const name = await screen.findByLabelText("Workspace name");
    await user.clear(name);
    await user.type(name, "Maple & Co");
    await user.click(within(bar()).getByRole("button", { name: "Save" }));

    expect(await within(bar()).findByText("Saving…")).toBeInTheDocument();
    expect(within(bar()).getByRole("button", { name: "Save" })).toBeDisabled();
    expect(patches).toEqual([{ name: "Maple & Co" }]);

    finish(json({ ...settings(), name: "Maple & Co" }));
    await waitFor(() => expect(within(bar()).getByRole("status")).toHaveTextContent("All changes saved"));
    expect(name).toHaveValue("Maple & Co");
  });

  it("a failed save says why in place and keeps the changes", async () => {
    const user = userEvent.setup();
    const { bar } = renderPage(settings(), () => problem(500, "internal", "Something broke"));
    const name = await screen.findByLabelText("Workspace name");
    await user.type(name, "!");
    await user.click(within(bar()).getByRole("button", { name: "Save" }));

    expect(await within(bar()).findByRole("alert")).toHaveTextContent(/./);
    expect(within(bar()).getByRole("status")).toHaveTextContent("Unsaved changes");
    expect(name).toHaveValue("Maple Bakery!");
  });

  it("a field the API refuses is marked on the field", async () => {
    const user = userEvent.setup();
    const { bar } = renderPage(settings(), () =>
      json(
        {
          type: "about:blank",
          title: "Validation error",
          status: 422,
          code: "validation_error",
          detail: "Check the fields.",
          errors: [{ field: "slug", message: "That URL is taken." }],
        },
        422,
      ),
    );
    const slug = await screen.findByLabelText("URL");
    await user.clear(slug);
    await user.type(slug, "taken-slug");
    await user.click(within(bar()).getByRole("button", { name: "Save" }));
    expect(await screen.findByText("That URL is taken.")).toBeInTheDocument();
  });

  it("previews the line automated messages end with", async () => {
    const user = userEvent.setup();
    renderPage(settings({ automation_disclosure: "Auto reply" }));
    const preview = await screen.findByTestId("disclosure-preview");
    expect(preview).toHaveTextContent("Auto reply");
    await user.clear(screen.getByLabelText("Line to add"));
    await user.type(screen.getByLabelText("Line to add"), "Sent by a bot");
    expect(preview).toHaveTextContent("Sent by a bot");
  });

  it("the summary is the workspace's own: plan, live channels, members, created", async () => {
    renderPage(settings({ member_count: 3 }));
    const summary = await screen.findByRole("region", { name: "At a glance" });
    expect(within(summary).getByText("Pro")).toBeInTheDocument();
    expect(await within(summary).findByText("Instagram (1), WhatsApp (1)")).toBeInTheDocument();
    expect(within(summary).getByText("3")).toBeInTheDocument();
    expect(within(summary).getByText(/^1 Sep/)).toBeInTheDocument();
  });
});
