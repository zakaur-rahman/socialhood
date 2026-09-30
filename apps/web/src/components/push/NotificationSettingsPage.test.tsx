import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { NotificationPreferences } from "@/lib/api/types";
import type { PushBrowser } from "@/lib/push/browser";
import { json, problem, renderWithApi, type Call } from "@/test/api";

import { NotificationSettingsPage } from "./NotificationSettingsPage";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

const unsupported: PushBrowser = {
  environment: () => ({ platform: "desktop", standalone: false, pushApis: false, permission: "unsupported" }),
  enabled: () => true,
  registration: async () => null,
  requestPermission: async () => "default",
};

const prefs: NotificationPreferences = {
  email_digest: true,
  push: { needs_you: true, new_lead: true, window_closing: true, account: true },
};

function setup(put?: (call: Call) => Response) {
  const view = renderWithApi(<NotificationSettingsPage pushBrowser={unsupported} />, {
    handlers: {
      "GET /v1/w/:wid/notification-preferences": () => json(prefs),
      "PUT /v1/w/:wid/notification-preferences": (call) => (put ? put(call) : json(call.body)),
    },
  });
  const puts = () => view.calls.filter((c) => c.method === "PUT").map((c) => c.body);
  return { ...view, puts };
}

beforeEach(() => toast.error.mockReset());

describe("Settings → Notifications (UX-SCR-07, FR-NOT-03, FR-NOT-04)", () => {
  it("the weekly digest switch saves the whole preferences object", async () => {
    const user = userEvent.setup();
    const { puts } = setup();
    const digest = await screen.findByRole("switch", { name: "Weekly digest" });
    expect(digest).toBeChecked();
    expect(screen.getByText(/Mondays at 09:00 \(Asia\/Kolkata\)/)).toBeInTheDocument();
    await user.click(digest);
    await waitFor(() => expect(puts()).toEqual([{ ...prefs, email_digest: false }]));
    expect(digest).not.toBeChecked();
  });

  it("a switch per push event: Needs you, new lead, window closing, account problems", async () => {
    const user = userEvent.setup();
    const { puts } = setup();
    const section = await screen.findByRole("region", { name: "Push notifications" });
    for (const name of ["Needs you", "New lead", "Reply window closing", "Account problems"]) {
      expect(await within(section).findByRole("switch", { name })).toBeChecked();
    }
    await user.click(within(section).getByRole("switch", { name: "Reply window closing" }));
    await waitFor(() => expect(puts()).toEqual([{ ...prefs, push: { ...prefs.push, window_closing: false } }]));
    // The device's own state shows beside them.
    expect(within(section).getByText("This browser can't show notifications from Social Hood")).toBeInTheDocument();
  });

  it("a switch that fails to save moves back and says why", async () => {
    const user = userEvent.setup();
    setup(() => problem(500, "internal"));
    const lead = await screen.findByRole("switch", { name: "New lead" });
    await user.click(lead);
    // C-066: the save bar says why, in place (the switches still save as they change).
    const bar = screen.getByRole("region", { name: "Save changes" });
    expect(await within(bar).findByRole("alert")).toHaveTextContent(/./);
    await waitFor(() => expect(screen.getByRole("switch", { name: "New lead" })).toBeChecked());
    expect(toast.error).not.toHaveBeenCalled();
  });
});
