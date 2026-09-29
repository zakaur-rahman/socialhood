import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { HashtagGroup } from "@/lib/api/types";
import { json, noContent, renderWithApi, type Call } from "@/test/api";
import { hashtagGroup } from "@/test/schedule";

import { HashtagGroupsDialog } from "./HashtagGroupsDialog";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

function problem422(field: string, message: string): Response {
  return new Response(
    JSON.stringify({ type: "about:blank", title: "validation_error", status: 422, code: "validation_error", errors: [{ field, message }] }),
    { status: 422, headers: { "Content-Type": "application/problem+json" } },
  );
}

function setup({ create }: { create?: (call: Call) => Response } = {}) {
  let groups: HashtagGroup[] = [hashtagGroup({ id: "hg1" })];
  return renderWithApi(<HashtagGroupsDialog open onOpenChange={() => {}} />, {
    handlers: {
      "GET /v1/w/:wid/hashtag-groups": () => json({ items: groups }),
      "POST /v1/w/:wid/hashtag-groups": (call) => {
        if (create) return create(call);
        const group = hashtagGroup({ id: "hg2", ...(call.body as object) });
        groups = [...groups, group];
        return json(group, 201);
      },
      "PATCH /v1/w/:wid/hashtag-groups/:id": (call, p) => {
        groups = groups.map((g) => (g.id === p.id ? { ...g, ...(call.body as object) } : g));
        return json(groups.find((g) => g.id === p.id));
      },
      "DELETE /v1/w/:wid/hashtag-groups/:id": (_, p) => {
        groups = groups.filter((g) => g.id !== p.id);
        return noContent();
      },
    },
  });
}

beforeEach(() => {
  toast.success.mockReset();
});

describe("HashtagGroupsDialog (UX-SCR-14, FR-PUB-12)", () => {
  it("lists each group with its count and first hashtags", async () => {
    setup();
    const list = await screen.findByRole("list", { name: "Hashtag groups" });
    expect(within(list).getByText("Summer linen")).toBeInTheDocument();
    expect(within(list).getByText("5 hashtags")).toBeInTheDocument();
    expect(within(list).getByText("#linen #summerstyle #handmade #slowfashion …")).toBeInTheDocument();
  });

  it("creates a group, counting hashtags against the limit of 30", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    await user.click(await screen.findByRole("button", { name: "New group" }));
    expect(screen.getByRole("dialog", { name: "New hashtag group" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Name"), "Festive");
    const tags = screen.getByLabelText("Hashtags");
    await user.type(tags, "#Diwali, lights #diwali bad-tag");
    expect(screen.getByTestId("hashtag-count")).toHaveTextContent("2 of 30 hashtags");
    await user.click(screen.getByRole("button", { name: "Create group" }));
    expect(screen.getByText("Use letters, numbers and underscores only: bad-tag")).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(0);

    await user.clear(tags);
    await user.type(tags, Array.from({ length: 31 }, (_, i) => `#tag${i}`).join(" "));
    expect(screen.getByTestId("hashtag-count")).toHaveTextContent("31 of 30 hashtags");
    await user.click(screen.getByRole("button", { name: "Create group" }));
    expect(screen.getByText("Use at most 30 hashtags.")).toBeInTheDocument();

    await user.clear(tags);
    await user.type(tags, "#Diwali, lights #diwali");
    await user.click(screen.getByRole("button", { name: "Create group" }));
    await waitFor(() => expect(calls.filter((c) => c.method === "POST")).toHaveLength(1));
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ name: "Festive", hashtags: ["diwali", "lights"] });
    expect(await screen.findByRole("dialog", { name: "Hashtag groups" })).toBeInTheDocument();
    expect(await screen.findByText("Festive")).toBeInTheDocument();
    expect(toast.success).toHaveBeenCalledWith("Festive created");
  });

  it("shows the API's field error", async () => {
    const user = userEvent.setup();
    setup({ create: () => problem422("name", "You already have a group with this name.") });
    await user.click(await screen.findByRole("button", { name: "New group" }));
    await user.type(screen.getByLabelText("Name"), "summer linen");
    await user.type(screen.getByLabelText("Hashtags"), "linen");
    await user.click(screen.getByRole("button", { name: "Create group" }));
    expect(await screen.findByText("You already have a group with this name.")).toBeInTheDocument();
  });

  it("edits and deletes a group", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    await user.click(await screen.findByRole("button", { name: "Edit Summer linen" }));
    const name = screen.getByLabelText("Name");
    expect(screen.getByLabelText("Hashtags")).toHaveValue("#linen #summerstyle #handmade #slowfashion #madeinindia");
    await user.clear(name);
    await user.type(name, "Linen");
    await user.click(screen.getByRole("button", { name: "Save group" }));
    await waitFor(() => expect(calls.filter((c) => c.method === "PATCH")).toHaveLength(1));
    expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({
      name: "Linen",
      hashtags: ["linen", "summerstyle", "handmade", "slowfashion", "madeinindia"],
    });

    await user.click(await screen.findByRole("button", { name: "Delete Linen" }));
    const confirm = screen.getByRole("group", { name: "Delete Linen?" });
    await user.click(within(confirm).getByRole("button", { name: "Delete group" }));
    await waitFor(() => expect(calls.filter((c) => c.method === "DELETE")).toHaveLength(1));
    expect(await screen.findByText("No hashtag groups yet")).toBeInTheDocument();
  });
});
