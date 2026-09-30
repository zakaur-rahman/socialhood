import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

describe("search and filters (C-066)", () => {
  const items = [
    account({ id: "a1", username: "maple.bakery", display_name: "Maple Bakery" }),
    account({
      id: "a2",
      platform: "whatsapp",
      username: null,
      display_name: "Maple Orders",
      phone_number: "+91 98765 43210",
    }),
    account({ id: "a3", username: "old.maple", display_name: "Old Maple", status: "disconnected" }),
    account({ id: "a4", username: "sandbox.shop", display_name: "Sandbox shop", sandbox: true }),
    account({
      id: "a5",
      username: "sandbox.gone",
      display_name: "Sandbox gone",
      sandbox: true,
      status: "disconnected",
    }),
  ];

  function renderList() {
    renderWithApi(<ConnectionsPage />, {
      handlers: { "GET /v1/w/:wid/social-accounts": () => json({ items }) },
    });
  }
  const cards = () => screen.getAllByRole("article").map((card) => card.getAttribute("aria-label"));
  const counts = (group: HTMLElement) => within(group).getAllByRole("radio").map((radio) => radio.textContent);

  it("counts every filter from the list and shows each one's accounts", async () => {
    const user = userEvent.setup();
    renderList();
    const filters = await screen.findByRole("radiogroup", { name: "Show accounts" });
    expect(counts(filters)).toEqual(["All5", "Connected3", "Disconnected2", "Sandboxes2"]);
    expect(within(filters).getByRole("radio", { name: /^All/ })).toHaveAttribute("aria-checked", "true");
    expect(cards()).toHaveLength(5);

    await user.click(within(filters).getByRole("radio", { name: /^Connected/ }));
    expect(cards()).toEqual(["Maple Bakery", "Maple Orders", "Sandbox shop"]);
    await user.click(within(filters).getByRole("radio", { name: /^Disconnected/ }));
    expect(cards()).toEqual(["Old Maple", "Sandbox gone"]);
    await user.click(within(filters).getByRole("radio", { name: /^Sandboxes/ }));
    expect(cards()).toEqual(["Sandbox shop", "Sandbox gone"]);
  });

  it("search matches names, handles and numbers, and the counts follow it", async () => {
    const user = userEvent.setup();
    renderList();
    const filters = await screen.findByRole("radiogroup", { name: "Show accounts" });
    const search = screen.getByRole("searchbox", { name: "Search accounts" });

    await user.type(search, "MAPLE");
    expect(cards()).toEqual(["Maple Bakery", "Maple Orders", "Old Maple"]);
    expect(counts(filters)).toEqual(["All3", "Connected2", "Disconnected1", "Sandboxes0"]);

    await user.clear(search);
    await user.type(search, "98765");
    expect(cards()).toEqual(["Maple Orders"]);

    await user.clear(search);
    await user.type(search, "@sandbox");
    await user.click(within(filters).getByRole("radio", { name: /^Disconnected/ }));
    expect(cards()).toEqual(["Sandbox gone"]);
  });

  it("nothing matching says so and can show everything again", async () => {
    const user = userEvent.setup();
    renderList();
    await screen.findByRole("radiogroup", { name: "Show accounts" });
    await user.type(screen.getByRole("searchbox", { name: "Search accounts" }), "zzz");
    expect(screen.getByText("No accounts match")).toBeInTheDocument();
    expect(screen.queryAllByRole("article")).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "Show all accounts" }));
    expect(cards()).toHaveLength(5);
    expect(screen.getByRole("searchbox", { name: "Search accounts" })).toHaveValue("");
  });

  it("names the page's tab in the breadcrumb and keeps the connect actions", async () => {
    renderList();
    const trail = await screen.findByRole("navigation", { name: "Breadcrumb" });
    expect(within(trail).getByText("Connections")).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("button", { name: /Connect Instagram/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Connect WhatsApp/ })).toBeInTheDocument();
  });
});
