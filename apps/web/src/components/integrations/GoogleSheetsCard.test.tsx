import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { browser } from "@/lib/billing/browser";
import type { GoogleSheetsStatus } from "@/lib/api/types";
import { json, noContent, problem, renderWithApi, type Call } from "@/test/api";

import { GoogleSheetsCard } from "./GoogleSheetsCard";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

const nav = vi.hoisted(() => ({ search: "" }));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(nav.search),
}));

const FIELDS = [
  { field: "contact_name", label: "Name", custom: false },
  { field: "username", label: "Username", custom: false },
  { field: "email", label: "Email", custom: false },
  { field: "phone", label: "Phone", custom: false },
  { field: "field:city", label: "City", custom: true },
];

function status(values: Partial<GoogleSheetsStatus> = {}): GoogleSheetsStatus {
  return {
    available: true,
    entitled: true,
    connected: false,
    status: null,
    google_email: null,
    sheet: null,
    columns: [
      { field: "contact_name", header: "Name" },
      { field: "email", header: "Email" },
    ],
    fields: FIELDS,
    last_success_at: null,
    last_failure_at: null,
    last_error: null,
    pending_rows: 0,
    failed_rows: 0,
    recent: [],
    ...values,
  } as GoogleSheetsStatus;
}

const SHEET = { spreadsheet_id: "sheet-1", title: "Leads sheet", url: "https://docs.google.test/sheet-1", tab: "Leads" };
const CONNECTED = { connected: true, status: "active" as const, google_email: "owner@example.com", sheet: SHEET };

function setup(initial: GoogleSheetsStatus, extra: Record<string, (call: Call) => Response> = {}) {
  let current = initial;
  return renderWithApi(<GoogleSheetsCard wid="w1" />, {
    handlers: {
      "GET /v1/w/:wid/integrations/google-sheets": () => json(current),
      "POST /v1/w/:wid/integrations/google-sheets/connect": () =>
        json({ authorize_url: "https://accounts.google.test/auth?state=s1" }),
      "POST /v1/w/:wid/integrations/google-sheets/complete": () => {
        current = status(CONNECTED);
        return json(current);
      },
      "POST /v1/w/:wid/integrations/google-sheets/sheet": (call) => {
        current = status({ ...CONNECTED, sheet: { ...SHEET, title: (call.body as { title: string }).title } });
        return json(current, 201);
      },
      "PUT /v1/w/:wid/integrations/google-sheets/mapping": (call) => {
        current = { ...current, columns: (call.body as { columns: GoogleSheetsStatus["columns"] }).columns };
        return json(current);
      },
      "POST /v1/w/:wid/integrations/google-sheets/test": () => json({ ok: true }),
      "DELETE /v1/w/:wid/integrations/google-sheets": () => {
        current = status();
        return noContent();
      },
      ...extra,
    },
  });
}

beforeEach(() => {
  nav.search = "";
  toast.success.mockReset();
  toast.error.mockReset();
  vi.restoreAllMocks();
  window.history.replaceState(null, "", "/");
});

describe("Google Sheets card (GR-27)", () => {
  it("says Sheets sync is part of Pro on a plan without it", async () => {
    setup(status({ entitled: false }));
    expect(await screen.findByText(/Google Sheets sync is part of Pro/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "See plans" })).toHaveAttribute("href", "/w/maple/settings/billing");
    expect(screen.queryByRole("button", { name: "Connect Google" })).not.toBeInTheDocument();
  });

  it("says when Google isn't set up on the server", async () => {
    setup(status({ available: false }));
    expect(await screen.findByText(/isn.t set up on this server yet/)).toBeInTheDocument();
  });

  it("sends the member to Google's consent page", async () => {
    const assign = vi.spyOn(browser, "assign").mockImplementation(() => {});
    const user = userEvent.setup();
    setup(status());
    expect(await screen.findByText("Not connected")).toBeInTheDocument();
    expect(screen.getByText(/never the rest of your Drive/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Connect Google" }));
    await waitFor(() => expect(assign).toHaveBeenCalledWith("https://accounts.google.test/auth?state=s1"));
  });

  it("finishes a connect with the nonce once, and drops it from the address", async () => {
    nav.search = "google=n0nce";
    const replace = vi.spyOn(window.history, "replaceState");
    const { calls } = setup(status());
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Google connected. Create or choose a sheet next."));
    const completes = calls.filter((c) => c.path.endsWith("/google-sheets/complete"));
    expect(completes.map((c) => c.body)).toEqual([{ nonce: "n0nce" }]);
    expect(replace).toHaveBeenCalled();
    expect(await screen.findByText("Connected as owner@example.com.")).toBeInTheDocument();
  });

  it.each([
    [404, "That connection link expired. Connect Google again."],
    [
      403,
      "This Google connection was started by someone else, so it wasn't added. To connect your own account, use Connect Google.",
    ],
  ])("explains a refused nonce (%s)", async (code, message) => {
    nav.search = "google=n0nce";
    setup(status(), {
      "POST /v1/w/:wid/integrations/google-sheets/complete": () => problem(code, code === 404 ? "not_found" : "forbidden", "x"),
    });
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith(message));
  });

  it("explains a cancelled consent without calling the API", async () => {
    nav.search = "error=access_denied";
    const { calls } = setup(status());
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Google wasn't connected: you cancelled it."));
    expect(calls.some((c) => c.path.endsWith("/complete"))).toBe(false);
  });

  it("creates a sheet with the name typed", async () => {
    const user = userEvent.setup();
    const { calls } = setup(status({ connected: true, status: "active", google_email: "owner@example.com" }));
    const name = await screen.findByRole("textbox", { name: "New sheet name" });
    expect(name).toHaveValue("Social Hood leads");
    await user.clear(name);
    await user.type(name, "Maple leads");
    await user.click(screen.getByRole("button", { name: "Create sheet" }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Sheet created in your Google Drive."));
    expect(calls.find((c) => c.method === "POST" && c.path.endsWith("/sheet"))?.body).toEqual({ title: "Maple leads" });
    expect(await screen.findByRole("link", { name: /Maple leads/ })).toHaveAttribute("href", SHEET.url);
  });

  it("shows why a sheet link was refused on the field", async () => {
    const user = userEvent.setup();
    setup(status({ connected: true, status: "active" }), {
      "PUT /v1/w/:wid/integrations/google-sheets/sheet": () =>
        new Response(
          JSON.stringify({
            type: "about:blank",
            title: "Validation error",
            status: 422,
            code: "validation_error",
            errors: [{ field: "link", message: "Social Hood can only use sheets it created or that Google has let it open." }],
          }),
          { status: 422, headers: { "Content-Type": "application/problem+json" } },
        ),
    });
    const link = await screen.findByRole("textbox", { name: "Or use a sheet by its link" });
    await user.type(link, "https://docs.google.com/spreadsheets/d/abc1234567");
    await user.click(screen.getByRole("button", { name: "Use this sheet" }));
    expect(await screen.findByText(/can only use sheets it created/)).toBeInTheDocument();
    expect(link).toHaveAttribute("aria-invalid", "true");
  });

  it("edits the columns and saves them in order", async () => {
    const user = userEvent.setup();
    const { calls } = setup(status(CONNECTED));
    const columns = await screen.findByRole("list", { name: "Columns" });
    const save = screen.getByRole("button", { name: "Save columns" });
    expect(save).toBeDisabled();

    const header = within(columns).getByRole("textbox", { name: "Header for Email" });
    await user.clear(header);
    await user.type(header, "Mail");
    await user.click(within(columns).getByRole("button", { name: "Move Email up" }));
    await user.click(screen.getByRole("button", { name: "Phone" })); // add a column
    expect(save).toBeEnabled();

    await user.click(save);
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Columns saved."));
    expect(calls.find((c) => c.method === "PUT" && c.path.endsWith("/mapping"))?.body).toEqual({
      columns: [
        { field: "email", header: "Mail" },
        { field: "contact_name", header: "Name" },
        { field: "phone", header: "Phone" },
      ],
    });
    await waitFor(() => expect(screen.getByRole("button", { name: "Save columns" })).toBeDisabled());
  });

  it("won't save a column without a header, and can undo", async () => {
    const user = userEvent.setup();
    setup(status(CONNECTED));
    const columns = await screen.findByRole("list", { name: "Columns" });
    await user.clear(within(columns).getByRole("textbox", { name: "Header for Name" }));
    expect(screen.getByRole("button", { name: "Save columns" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Undo changes" }));
    expect(within(columns).getByRole("textbox", { name: "Header for Name" })).toHaveValue("Name");
  });

  it("removes a column but keeps at least one", async () => {
    const user = userEvent.setup();
    setup(status(CONNECTED));
    const columns = await screen.findByRole("list", { name: "Columns" });
    await user.click(within(columns).getByRole("button", { name: "Remove Name" }));
    expect(within(columns).getAllByTestId("sheet-column")).toHaveLength(1);
    expect(within(columns).getByRole("button", { name: "Remove Email" })).toBeDisabled();
  });

  it("sends a test row", async () => {
    const user = userEvent.setup();
    const { calls } = setup(status(CONNECTED));
    await user.click(await screen.findByRole("button", { name: "Send a test row" }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Test row added to your sheet."));
    expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/test"))).toBe(true);
  });

  it("shows the latest rows with the plain reason a row failed", async () => {
    setup(
      status({
        ...CONNECTED,
        pending_rows: 0,
        failed_rows: 1,
        recent: [
          { id: "r1", status: "succeeded", attempts: 1, error: null, error_code: null, created_at: "2026-10-24T09:00:00Z", last_attempt_at: "2026-10-24T09:00:02Z", next_attempt_at: null },
          { id: "r2", status: "failed", attempts: 1, error: "Google said the sheet was deleted. Pick or create a sheet again.", error_code: "sheet_gone", created_at: "2026-10-24T08:00:00Z", last_attempt_at: "2026-10-24T08:00:02Z", next_attempt_at: null },
        ],
      }),
    );
    const rows = await screen.findAllByTestId("sheet-row");
    expect(rows[0]).toHaveTextContent("Added");
    expect(rows[1]).toHaveTextContent("Failed");
    expect(rows[1]).toHaveTextContent("Google said the sheet was deleted. Pick or create a sheet again.");
    expect(screen.getByText("0 waiting, 1 failed.")).toBeInTheDocument();
  });

  it("asks to reconnect when access was removed", async () => {
    vi.spyOn(browser, "assign").mockImplementation(() => {});
    setup(
      status({
        ...CONNECTED,
        status: "needs_reconnect",
        last_error: "Access was removed: reconnect Google in Settings, under Integrations.",
      }),
    );
    expect(await screen.findByText("Reconnect needed")).toBeInTheDocument();
    expect(screen.getByText("Access was removed: reconnect Google in Settings, under Integrations.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reconnect Google" })).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Columns" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send a test row" })).toBeDisabled();
  });

  it("disconnects after asking", async () => {
    const user = userEvent.setup();
    const { calls } = setup(status(CONNECTED));
    await user.click(await screen.findByRole("button", { name: "Disconnect" }));
    const dialog = await screen.findByRole("alertdialog", { name: "Disconnect Google?" });
    await user.click(within(dialog).getByRole("button", { name: "Disconnect Google" }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Google disconnected"));
    expect(calls.some((c) => c.method === "DELETE")).toBe(true);
    expect(await screen.findByRole("button", { name: "Connect Google" })).toBeInTheDocument();
  });
});
