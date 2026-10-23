import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { SavedReply } from "@/lib/api/types";
import { json, noContent, problem, renderWithApi, workspace } from "@/test/api";

import { SavedRepliesPage } from "./SavedRepliesPage";

const price: SavedReply = {
  id: "r1",
  title: "Prices",
  shortcut: "price",
  body: "Hi {first_name}, from 499.",
  created_at: "2026-10-20T10:00:00Z",
  updated_at: "2026-10-20T10:00:00Z",
};

type Handlers = NonNullable<Parameters<typeof renderWithApi>[1]>["handlers"];

function setup(items: SavedReply[], ws = workspace, extra: Handlers = {}) {
  return renderWithApi(<SavedRepliesPage />, {
    ws,
    handlers: { "GET /v1/w/:wid/saved-replies": () => json({ items, max_items: 200 }), ...extra },
  });
}

describe("SavedRepliesPage (GR-21)", () => {
  it("lists each reply with its shortcut and message", async () => {
    setup([price]);
    const row = await screen.findByTestId("saved-reply-row");
    expect(within(row).getByText("/price")).toBeInTheDocument();
    expect(within(row).getByText("Prices")).toBeInTheDocument();
    expect(within(row).getByText("Hi {first_name}, from 499.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Edit /price" })).toBeInTheDocument();
  });

  it("explains an empty list and offers the first one", async () => {
    setup([]);
    expect(await screen.findByText("No saved replies yet")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /New saved reply/ }).length).toBeGreaterThan(0);
  });

  it("agents see the replies but cannot change them", async () => {
    setup([price], { ...workspace, role: "agent" });
    await screen.findByTestId("saved-reply-row");
    expect(screen.queryByRole("button", { name: /New/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit /price" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete /price" })).not.toBeInTheDocument();
  });

  it("adds a reply, dropping a typed slash from the shortcut", async () => {
    const user = userEvent.setup();
    let sent: unknown;
    setup([], workspace, {
      "POST /v1/w/:wid/saved-replies": (call) => {
        sent = call.body;
        return json({ ...price, id: "r2", title: "Hours", shortcut: "hours", body: "9 to 5." }, 201);
      },
    });
    await user.click((await screen.findAllByRole("button", { name: /New saved reply/ }))[0]);
    await user.type(screen.getByLabelText("Title"), "Hours");
    await user.type(screen.getByLabelText("Shortcut"), "/hours");
    await user.type(screen.getByLabelText("Message"), "9 to 5.");
    await user.click(screen.getByRole("button", { name: "Add saved reply" }));
    await waitFor(() => expect(sent).toEqual({ title: "Hours", shortcut: "hours", body: "9 to 5." }));
  });

  it("shows a taken shortcut under the field", async () => {
    const user = userEvent.setup();
    setup([price], workspace, {
      "POST /v1/w/:wid/saved-replies": () => problem(409, "conflict", "Another saved reply already uses this shortcut."),
    });
    await user.click((await screen.findAllByRole("button", { name: /New/ }))[0]);
    await user.type(screen.getByLabelText("Title"), "Prices again");
    await user.type(screen.getByLabelText("Shortcut"), "price");
    await user.type(screen.getByLabelText("Message"), "x");
    await user.click(screen.getByRole("button", { name: "Add saved reply" }));
    expect(await screen.findByText("Another saved reply already uses this shortcut.")).toBeInTheDocument();
  });

  it("deletes after confirming", async () => {
    const user = userEvent.setup();
    const { calls } = setup([price], workspace, { "DELETE /v1/w/:wid/saved-replies/:id": () => noContent() });
    await user.click(await screen.findByRole("button", { name: "Delete /price" }));
    await user.click(await screen.findByRole("button", { name: "Delete reply" }));
    await waitFor(() =>
      expect(calls.some((c) => c.method === "DELETE" && c.path.endsWith("/saved-replies/r1"))).toBe(true),
    );
  });
});
