import { waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { account, json, problem, renderWithApi, type Call } from "@/test/api";

import ConnectionsPage from "./page";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

const nav = vi.hoisted(() => ({ search: "", replace: vi.fn() }));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(nav.search),
  usePathname: () => "/w/maple/settings/connections",
  useRouter: () => ({ push: vi.fn(), replace: nav.replace }),
}));

beforeEach(() => {
  nav.search = "";
  nav.replace.mockReset();
  toast.success.mockReset();
  toast.error.mockReset();
});

function renderPage(complete: (call: Call) => Response) {
  return renderWithApi(<ConnectionsPage />, {
    handlers: {
      "GET /v1/w/:wid/social-accounts": () => json({ items: [] }),
      "POST /v1/w/:wid/social-accounts/instagram/complete": complete,
    },
  });
}

const completeCalls = (calls: Call[]) => calls.filter((c) => c.path.endsWith("/instagram/complete"));

describe("finishing an Instagram connect (F-03, X-1)", () => {
  it("posts the nonce once, drops it from the URL and names the account", async () => {
    nav.search = "instagram=n0nce";
    const { calls, rerender } = renderPage(() => json(account({ username: "maple.bakery" })));

    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Instagram connected: @maple.bakery"));
    rerender(<ConnectionsPage />);
    expect(completeCalls(calls).map((c) => c.body)).toEqual([{ nonce: "n0nce" }]);
    expect(calls.find((c) => c.path.endsWith("/instagram/complete"))?.path).toBe(
      "/v1/w/w1/social-accounts/instagram/complete",
    );
    expect(nav.replace).toHaveBeenCalledWith("/w/maple/settings/connections", { scroll: false });
  });

  it.each([
    [problem(404, "not_found", "gone"), "That connection link expired."],
    [
      problem(403, "forbidden", "not yours"),
      "This Instagram connection was started by someone else, so it wasn't added. To connect your own account, use Connect Instagram.",
    ],
    [
      problem(409, "account_in_use", "in use"),
      "This account is connected to another Social Hood workspace. Disconnect it there first.",
    ],
  ])("explains a refused nonce", async (response, message) => {
    nav.search = "instagram=n0nce";
    renderPage(() => response);
    await waitFor(() => expect(toast.error).toHaveBeenCalledTimes(1));
    expect(toast.error.mock.calls[0][0]).toBe(message);
    expect(toast.success).not.toHaveBeenCalled();
  });

  it("still shows the callback's own errors without calling the API", async () => {
    nav.search = "error=access_denied";
    const { calls } = renderPage(() => json(account()));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Connection cancelled", undefined));
    expect(completeCalls(calls)).toEqual([]);
  });
});
