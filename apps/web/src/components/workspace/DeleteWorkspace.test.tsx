import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { keys } from "@/lib/api/queries";
import { json, problem, renderWithApi, workspace } from "@/test/api";

import { DeleteWorkspace } from "./DeleteWorkspace";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

const nav = vi.hoisted(() => ({ replace: vi.fn(), push: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => nav }));

const deleted = {
  id: workspace.id,
  status: "deleting",
  deletion_requested_at: "2026-09-30T10:00:00Z",
  purge_by: "2026-10-01T10:00:00Z",
};

function setup(role: "owner" | "admin" | "agent" = "owner", answer = () => json(deleted, 202)) {
  const view = renderWithApi(<DeleteWorkspace />, {
    ws: { ...workspace, role },
    handlers: { "DELETE /v1/w/:wid": answer },
  });
  view.queryClient.setQueryData(keys.me, { id: "u1" });
  view.queryClient.setQueryData(keys.workspace(workspace.id), { id: workspace.id });
  return view;
}

async function openDialog() {
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Delete workspace" }));
  const input = await screen.findByLabelText(/to confirm/);
  const confirm = screen.getAllByRole("button", { name: "Delete workspace" }).at(-1)!;
  return { user, input, confirm };
}

beforeEach(() => {
  nav.replace.mockReset();
  toast.success.mockReset();
  toast.error.mockReset();
});

describe("DeleteWorkspace", () => {
  it("is shown to owners only", () => {
    setup("admin");
    expect(screen.queryByRole("button", { name: "Delete workspace" })).toBeNull();
  });

  it("says what is removed and when before asking for the name", async () => {
    setup();
    await openDialog();
    expect(screen.getByText(/Within 24 hours we permanently erase/)).toBeInTheDocument();
    expect(screen.getByText(/Conversations, messages, comments and contacts/)).toBeInTheDocument();
    expect(screen.getByText(/paid plan, if any, is cancelled now/)).toBeInTheDocument();
  });

  it("deletes only once the exact name is typed, then goes to /app", async () => {
    const { calls, queryClient } = setup();
    const { user, input, confirm } = await openDialog();
    expect(confirm).toBeDisabled();
    await user.type(input, "maple bakery");
    expect(confirm).toBeDisabled();
    await user.clear(input);
    await user.type(input, "Maple Bakery ");
    expect(confirm).toBeEnabled();
    await user.click(confirm);

    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/app"));
    const [call] = calls.filter((c) => c.method === "DELETE");
    expect(call.path).toBe(`/v1/w/${workspace.id}`);
    expect(call.url.searchParams.get("confirm_name")).toBe("Maple Bakery ");
    expect(toast.success).toHaveBeenCalledWith("Maple Bakery was deleted");
    // The deleted workspace's data and the old workspace list are forgotten, so /app refetches.
    expect(queryClient.getQueryData(keys.me)).toBeUndefined();
    expect(queryClient.getQueryData(keys.workspace(workspace.id))).toBeUndefined();
  });

  it("shows the API's refusal of the name beside the field", async () => {
    setup("owner", () =>
      new Response(
        JSON.stringify({
          type: "about:blank",
          title: "The request is not valid",
          status: 422,
          code: "validation_error",
          errors: [{ field: "confirm_name", message: "Type the workspace name exactly as it is shown to confirm." }],
        }),
        { status: 422, headers: { "Content-Type": "application/problem+json" } },
      ),
    );
    const { user, input, confirm } = await openDialog();
    await user.type(input, "Maple Bakery");
    await user.click(confirm);
    expect(await screen.findByRole("alert")).toHaveTextContent("exactly as it is shown");
    expect(nav.replace).not.toHaveBeenCalled();
  });

  it("toasts any other failure and stays", async () => {
    setup("owner", () => problem(503, "service_unavailable", "Try again in a moment."));
    const { user, input, confirm } = await openDialog();
    await user.type(input, "Maple Bakery");
    await user.click(confirm);
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(nav.replace).not.toHaveBeenCalled();
  });
});
