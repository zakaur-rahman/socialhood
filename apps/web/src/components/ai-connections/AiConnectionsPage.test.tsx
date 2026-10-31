import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { AiConnection, AiConnectionsSettings, WorkspaceSummary } from "@/lib/api/types";
import { json, noContent, renderWithApi, workspace } from "@/test/api";

import { AiConnectionsPage } from "./AiConnectionsPage";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

function connection(values: Partial<AiConnection> = {}): AiConnection {
  return {
    id: "c-1",
    client_name: "Claude",
    verified_host: "claude.ai",
    redirect_host: "claude.ai",
    member: { id: "u-1", name: "Asha", email: "asha@maple.test" },
    is_yours: true,
    scopes: ["workspace:read", "posts:read", "conversations:read"],
    created_at: "2026-10-30T09:00:00Z",
    last_used_at: new Date(Date.now() - 60_000).toISOString(),
    expires_at: "2026-11-29T09:00:00Z",
    calls_7d: 3,
    recent_calls: [{ id: "t-1", tool: "list_conversations", outcome: "ok", error_code: null, created_at: "2026-10-31T09:00:00Z" }],
    ...values,
  };
}

const SETTINGS: AiConnectionsSettings = { mode: "full", effective_mode: "full", plan_allows: ["off", "read_only", "read_drafts", "full"] };

function setup({
  items = [connection()],
  manages = true,
  settings = SETTINGS,
  ws = workspace,
}: { items?: AiConnection[]; manages?: boolean; settings?: AiConnectionsSettings; ws?: WorkspaceSummary } = {}) {
  return renderWithApi(<AiConnectionsPage />, {
    ws,
    handlers: {
      "GET /v1/w/:wid/ai-connections/settings": () => json(settings),
      "PUT /v1/w/:wid/ai-connections/settings": (call) => json({ ...settings, ...(call.body as object) }),
      "GET /v1/w/:wid/ai-connections": () => json({ items, can_manage_all: manages }),
      "GET /v1/w/:wid/ai-connections/:id/activity": () =>
        json({ items: [{ id: "t-9", tool: "get_workspace", outcome: "refused", error_code: "forbidden", created_at: "2026-10-31T08:00:00Z" }] }),
      "DELETE /v1/w/:wid/ai-connections/:id": () => noContent(),
      "POST /v1/w/:wid/ai-connections/revoke-all": () => json({ revoked: items.length }),
    },
  });
}

beforeEach(() => {
  toast.success.mockReset();
  toast.error.mockReset();
});

describe("Settings › Connected AI apps (C-165)", () => {
  it("lists each connection with its member, what it may do and its recent calls", async () => {
    setup();
    const [row] = await screen.findAllByTestId("ai-connection");
    expect(row).toHaveTextContent("Claude");
    expect(row).toHaveTextContent("claude.ai");
    expect(row).toHaveTextContent(/You · connected/);
    expect(row).toHaveTextContent("3 calls in 7 days");
    expect(row).toHaveTextContent("Read the inbox");
    expect(row).toHaveTextContent("list_conversations");
    expect(screen.getByRole("link", { name: /How to connect an AI app/ })).toHaveAttribute("href", expect.stringContaining("/developers/mcp"));
  });

  it("shows the latest activity on demand", async () => {
    const user = userEvent.setup();
    setup();
    await user.click(await screen.findByRole("button", { name: "Activity" }));
    expect(await screen.findByText("get_workspace")).toBeInTheDocument();
    expect(screen.getByText("Refused")).toBeInTheDocument();
  });

  it("disconnects one after confirming", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    await user.click(await screen.findByRole("button", { name: "Disconnect" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Disconnect" }));
    await waitFor(() => expect(calls.some((c) => c.method === "DELETE" && c.path.endsWith("/ai-connections/c-1"))).toBe(true));
    expect(toast.success).toHaveBeenCalledWith("Claude disconnected");
  });

  it("disconnects all for owners and admins", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ items: [connection(), connection({ id: "c-2", is_yours: false })] });
    await user.click(await screen.findByRole("button", { name: "Disconnect all" }));
    await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Disconnect all" }));
    await waitFor(() => expect(calls.some((c) => c.path.endsWith("/revoke-all"))).toBe(true));
  });

  it("changes the mode, and explains each one", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    expect(await screen.findByRole("radio", { name: /^Full/ })).toBeChecked();
    expect(screen.getByText(/Replies are never sent by an AI app/)).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: /^Read only/ }));
    await waitFor(() => expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ mode: "read_only" }));
  });

  it("on Free, Full is part of Pro and Max", async () => {
    setup({
      settings: { mode: "full", effective_mode: "read_drafts", plan_allows: ["off", "read_only", "read_drafts"] },
      ws: { ...workspace, plan: "free" },
    });
    expect(await screen.findByRole("radio", { name: /^Full/ })).toBeDisabled();
    expect(screen.getByText(/Your plan allows up to/)).toBeInTheDocument();
  });

  it("members see only their own, with no mode and no Disconnect all", async () => {
    setup({ ws: { ...workspace, role: "agent" }, manages: false });
    expect(await screen.findByRole("heading", { name: "Your connected apps" })).toBeInTheDocument();
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Disconnect all" })).not.toBeInTheDocument();
  });

  it("links to the setup guide when nothing is connected", async () => {
    setup({ items: [] });
    expect(await screen.findByText(/No AI apps are connected/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "setup guide" })).toHaveAttribute("href", expect.stringContaining("/developers/mcp"));
  });
});
