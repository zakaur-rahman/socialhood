import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ConnectRequest } from "@/lib/api/types";
import { json, problem, renderWithApi } from "@/test/api";

import { ConsentPage, navigate } from "./ConsentPage";

const nav = vi.hoisted(() => ({ search: "request=req-1" }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(nav.search),
}));
const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

function request(values: Partial<ConnectRequest> = {}): ConnectRequest {
  return {
    client: {
      name: "Claude",
      logo_url: "https://claude.ai/logo.png",
      verified_host: "claude.ai",
      redirect_host: "claude.ai",
      loopback: false,
    },
    always: "See the workspace, its plan and time zone, and its connected accounts",
    groups: [
      {
        id: "publishing",
        label: "Publishing",
        scopes: [
          { scope: "posts:read", description: "See scheduled posts" },
          { scope: "posts:write", description: "Schedule, change, reschedule and cancel posts" },
        ],
      },
      { id: "inbox", label: "Inbox", scopes: [{ scope: "conversations:read", description: "Read your inbox conversations" }] },
    ],
    member: { email: "asha@maple.test", name: "Asha" },
    workspaces: [
      { id: "w-off", name: "Old shop", plan: "free", role: "agent", mode: "off", can_connect: false, reason: "AI connections are off here." },
      { id: "w1", name: "Maple Bakery", plan: "pro", role: "admin", mode: "full", can_connect: true, reason: null },
    ],
    ...values,
  };
}

const assign = vi.fn();

beforeEach(() => {
  nav.search = "request=req-1";
  assign.mockReset();
  vi.spyOn(navigate, "to").mockImplementation(assign);
});
afterEach(() => vi.restoreAllMocks());

function setup(body: ConnectRequest | Response = request()) {
  return renderWithApi(<ConsentPage />, {
    handlers: {
      "GET /v1/connect/requests/:id": () => (body instanceof Response ? body : json(body)),
      "POST /v1/connect/requests/:id/approve": () => json({ redirect_to: "https://claude.ai/api/mcp/auth_callback?code=shc_x&state=s" }),
      "POST /v1/connect/requests/:id/deny": () => json({ redirect_to: "https://claude.ai/api/mcp/auth_callback?error=access_denied" }),
    },
  });
}

describe("AI app consent page (C-165)", () => {
  it("names the app, where it goes back to and what it may do", async () => {
    setup();
    expect(await screen.findByRole("heading", { name: "Claude wants to connect to Amplychat" })).toBeInTheDocument();
    expect(screen.getByText(/Signed in as asha@maple.test/)).toHaveTextContent("Goes back to claude.ai");
    expect(screen.getByText("Details from claude.ai")).toBeInTheDocument();
    expect(screen.getByText("Schedule, change, reschedule and cancel posts")).toBeInTheDocument();
    const img = document.querySelector("img");
    expect(img).toHaveAttribute("referrerpolicy", "no-referrer");
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
    expect(screen.getByText(/can’t do anything your role \(Admin\)/)).toBeInTheDocument();
  });

  it("offers only workspaces that can connect, and picks the first one", async () => {
    setup();
    const picker = await screen.findByRole("group", { name: "Workspace" });
    expect(within(picker).getByRole("radio", { name: /Old shop/ })).toBeDisabled();
    expect(within(picker).getByRole("radio", { name: /Maple Bakery/ })).toBeChecked();
    expect(within(picker).getByText("AI connections are off here.")).toBeInTheDocument();
  });

  it("allows with the groups left ticked, then goes back to the app", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    await user.click(await screen.findByRole("checkbox", { name: "Inbox" }));
    await user.click(screen.getByRole("button", { name: "Allow" }));
    await waitFor(() => expect(assign).toHaveBeenCalledWith("https://claude.ai/api/mcp/auth_callback?code=shc_x&state=s"));
    const approve = calls.find((c) => c.path.endsWith("/approve"));
    expect(approve?.body).toEqual({ workspace_id: "w1", scopes: ["posts:read", "posts:write"] });
  });

  it("cancel sends access_denied back", async () => {
    const user = userEvent.setup();
    setup();
    await user.click(await screen.findByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(assign).toHaveBeenCalledWith(expect.stringContaining("error=access_denied")));
  });

  it("warns about apps on this computer and an unverified name, with no logo", async () => {
    setup(request({ client: { name: "Inspector", logo_url: null, verified_host: null, redirect_host: "127.0.0.1", loopback: true } }));
    expect(await screen.findByRole("note")).toHaveTextContent("Only allow it if you started the connection on this computer");
    expect(screen.getByText(/registered itself/)).toBeInTheDocument();
    expect(document.querySelector("img")).toBeNull();
  });

  it("can't allow without a workspace that can connect", async () => {
    setup(request({ workspaces: [request().workspaces[0]] }));
    expect(await screen.findByRole("button", { name: "Allow" })).toBeDisabled();
  });

  it("says an expired or used request has expired", async () => {
    setup(problem(404, "not_found", "expired"));
    expect(await screen.findByRole("heading", { name: "This request has expired" })).toBeInTheDocument();
  });

  it("says so without a request id", async () => {
    nav.search = "";
    setup();
    expect(await screen.findByRole("heading", { name: "This request has expired" })).toBeInTheDocument();
  });
});
