import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { account, json, problem, renderWithApi, type Call } from "@/test/api";
import { scheduledPost } from "@/test/composer-fixtures";

import { newDraftBody, NewPost } from "./NewPost";

const nav = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: nav.push, replace: nav.replace }),
  useParams: () => ({ slug: "maple" }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/w/maple/schedule/new",
}));

const now = new Date("2026-09-29T12:00:00Z");
const ready = account({ id: "a1", capabilities: ["publish"] });

beforeEach(() => nav.replace.mockReset());

describe("newDraftBody (F-13)", () => {
  it("starts with the only account that can publish, and a calendar click's time", () => {
    expect(newDraftBody([ready, account({ id: "w", platform: "whatsapp" })], "2026-09-30T12:30:00Z", now)).toEqual({
      targets: [{ social_account_id: "a1", caption_override: null }],
      asset_ids: [],
      caption: "",
      first_comment: null,
      publish_at: "2026-09-30T12:30:00.000Z",
    });
  });

  it("leaves accounts to the user when several can publish, and drops a time too soon or invalid", () => {
    const body = newDraftBody([ready, account({ id: "a2", capabilities: ["publish"] })], "2026-09-29T12:03:00Z", now);
    expect(body.targets).toEqual([]);
    expect(body.publish_at).toBeNull();
    expect(newDraftBody([ready], "not a date", now).publish_at).toBeNull();
    expect(newDraftBody([account({ id: "a3", status: "needs_reconnect", capabilities: ["publish"] })], null, now).targets).toEqual([]);
  });
});

describe("NewPost", () => {
  it("creates one draft and opens the composer on it", async () => {
    const calls: Call[] = [];
    renderWithApi(<NewPost at={null} />, {
      handlers: {
        "GET /v1/w/:wid/social-accounts": () => json({ items: [ready] }),
        "POST /v1/w/:wid/scheduled-posts": (call) => {
          calls.push(call);
          return json(scheduledPost({ id: "sp7" }), 201);
        },
      },
    });
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/w/maple/schedule/sp7"));
    expect(calls).toHaveLength(1);
    expect(calls[0].body).toMatchObject({ targets: [{ social_account_id: "a1", caption_override: null }], caption: "" });
  });

  it("passes when=queue on to the composer", async () => {
    renderWithApi(<NewPost at={null} when="queue" />, {
      handlers: {
        "GET /v1/w/:wid/social-accounts": () => json({ items: [ready] }),
        "POST /v1/w/:wid/scheduled-posts": () => json(scheduledPost({ id: "sp9" }), 201),
      },
    });
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/w/maple/schedule/sp9?when=queue"));
  });

  it("offers Try again when the draft can't be created", async () => {
    const user = userEvent.setup();
    let count = 0;
    renderWithApi(<NewPost at={null} />, {
      handlers: {
        "GET /v1/w/:wid/social-accounts": () => json({ items: [] }),
        "POST /v1/w/:wid/scheduled-posts": () => {
          count += 1;
          return count === 1 ? problem(500, "internal") : json(scheduledPost({ id: "sp8" }), 201);
        },
      },
    });
    await user.click(await screen.findByRole("button", { name: "Try again" }));
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/w/maple/schedule/sp8"));
  });
});
