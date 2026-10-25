import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import type { FacebookPageOption } from "@/lib/api/types";
import { account, json, problem, renderWithApi } from "@/test/api";

import { defaultPicks, FacebookPagesDialog } from "./FacebookPagesDialog";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});

beforeEach(() => {
  toast.success.mockReset();
  toast.error.mockReset();
});

function page(overrides: Partial<FacebookPageOption> = {}): FacebookPageOption {
  return {
    id: "p1",
    name: "Maple Bakery",
    username: "maplebakery",
    picture_url: null,
    connected: false,
    can_connect: true,
    problem: null,
    ...overrides,
  };
}

const PAGES = [
  page(),
  page({ id: "p2", name: "Maple Cafe", username: null }),
  page({ id: "p3", name: "Moderators only", username: "mods", can_connect: false, problem: "You can't answer messages for this Page." }),
  page({ id: "p4", name: "Old Page", username: "oldpage", connected: true }),
];

function renderDialog(list: () => Response, connect: () => Response = () => json({ items: [account({ platform: "facebook" })] })) {
  const onClose = vi.fn();
  const view = renderWithApi(<FacebookPagesDialog wid="w1" nonce="n0nce" onClose={onClose} />, {
    handlers: {
      "POST /v1/w/:wid/social-accounts/facebook/pages": list,
      "POST /v1/w/:wid/social-accounts/facebook/connect-pages": connect,
    },
  });
  return { ...view, onClose };
}

describe("defaultPicks", () => {
  it("pre-checks the only Page that can be connected", () => {
    expect([...defaultPicks([page(), page({ id: "p3", can_connect: false }), page({ id: "p4", connected: true })])]).toEqual(["p1"]);
  });

  it("checks nothing when there is a choice to make", () => {
    expect([...defaultPicks(PAGES)]).toEqual([]);
    expect([...defaultPicks([])]).toEqual([]);
  });
});

describe("the Pages dialog (GR-29)", () => {
  it("lists the Pages with the nonce, and says why one can't be picked", async () => {
    const { calls } = renderDialog(() => json({ items: PAGES }));
    const list = await screen.findByRole("list", { name: "Your Facebook Pages" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(4);
    expect(calls.find((c) => c.path.endsWith("/facebook/pages"))?.body).toEqual({ nonce: "n0nce" });
    expect(within(list).getByText("@maplebakery")).toBeInTheDocument();
    expect(within(list).getByText("You can't answer messages for this Page.")).toBeInTheDocument();
    expect(within(list).getByText("Connected")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /Moderators only/ })).toBeDisabled();
    expect(screen.getByRole("checkbox", { name: /Maple Bakery/ })).toBeEnabled();
    // Nothing is picked yet when there is a choice.
    expect(screen.getByRole("button", { name: "Connect Page" })).toBeDisabled();
  });

  it("connects the picked Pages, names them and closes", async () => {
    const user = userEvent.setup();
    const { calls, onClose } = renderDialog(
      () => json({ items: PAGES }),
      () =>
        json({
          items: [
            account({ id: "a9", platform: "facebook", display_name: "Maple Bakery" }),
            account({ id: "a10", platform: "facebook", display_name: "Maple Cafe" }),
          ],
        }),
    );
    await screen.findByRole("list", { name: "Your Facebook Pages" });
    await user.click(screen.getByRole("checkbox", { name: /Maple Bakery/ }));
    await user.click(screen.getByRole("checkbox", { name: /Maple Cafe/ }));
    await user.click(screen.getByRole("button", { name: "Connect 2 Pages" }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(calls.find((c) => c.path.endsWith("/facebook/connect-pages"))?.body).toEqual({
      nonce: "n0nce",
      page_ids: ["p1", "p2"],
    });
    expect(toast.success).toHaveBeenCalledWith("2 Facebook Pages connected: Maple Bakery, Maple Cafe");
  });

  it("pre-checks a single Page, so one click connects it", async () => {
    const user = userEvent.setup();
    const { calls, onClose } = renderDialog(() => json({ items: [page()] }));
    expect(await screen.findByRole("checkbox", { name: /Maple Bakery/ })).toBeChecked();
    await user.click(screen.getByRole("button", { name: "Connect Page" }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(calls.find((c) => c.path.endsWith("/facebook/connect-pages"))?.body).toEqual({ nonce: "n0nce", page_ids: ["p1"] });
    expect(toast.success).toHaveBeenCalledWith("Facebook connected: Maple Bakery");
  });

  it("keeps the list open when the plan refuses, so fewer Pages can be picked", async () => {
    const user = userEvent.setup();
    const { onClose } = renderDialog(
      () => json({ items: PAGES }),
      () => problem(402, "quota_exceeded", "Your plan includes 1 Facebook account.", { entitlement: "accounts_per_platform", limit: 1 }),
    );
    await screen.findByRole("list", { name: "Your Facebook Pages" });
    await user.click(screen.getByRole("checkbox", { name: /Maple Bakery/ }));
    await user.click(screen.getByRole("button", { name: "Connect Page" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Connect Page" })).toBeEnabled());
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByRole("list", { name: "Your Facebook Pages" })).toBeInTheDocument();
  });

  it.each([
    [problem(404, "not_found", "gone"), "That connection link expired. Close this and connect Facebook again."],
    [
      problem(403, "forbidden", "not yours"),
      "This Facebook connection was started by someone else, so it wasn't added. To connect your own Pages, use Connect Facebook.",
    ],
    [problem(502, "platform_error", "Facebook didn't respond. Try again."), "Facebook didn't respond. Close this and connect Facebook again."],
  ])("explains a list that didn't load", async (response, message) => {
    renderDialog(() => response);
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(screen.getByRole("button", { name: "Connect Page" })).toBeDisabled();
  });

  it("is closed without a nonce", () => {
    renderWithApi(<FacebookPagesDialog wid="w1" nonce={null} onClose={vi.fn()} />);
    expect(screen.queryByTestId("facebook-pages-dialog")).toBeNull();
  });

  it("Cancel closes it", async () => {
    const user = userEvent.setup();
    const { onClose } = renderDialog(() => json({ items: PAGES }));
    await screen.findByRole("list", { name: "Your Facebook Pages" });
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onClose).toHaveBeenCalled();
  });
});
