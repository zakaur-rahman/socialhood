import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { account, json, noContent, problem, renderWithApi, workspace, type Call } from "@/test/api";

import ConnectionsPage from "./page";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

const nav = vi.hoisted(() => ({ search: "", replace: vi.fn() }));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(nav.search),
  usePathname: () => "/w/maple/settings/connections",
  useRouter: () => ({ push: vi.fn(), replace: nav.replace }),
}));

beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});

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
    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(toast.error).not.toHaveBeenCalled();
    expect(toast.success).not.toHaveBeenCalled();
  });

  it("still shows the callback's own errors without calling the API", async () => {
    nav.search = "error=access_denied";
    const { calls } = renderPage(() => json(account()));
    expect(await screen.findByText("Connection cancelled")).toBeInTheDocument();
    expect(completeCalls(calls)).toEqual([]);
  });

  it("keeps the last connect error inline with Try again until dismissed (UI-061)", async () => {
    const user = userEvent.setup();
    nav.search = "error=connect_failed";
    renderPage(() => json(account()));
    expect(await screen.findByText("Instagram didn't respond. Try again.")).toBeInTheDocument();
    expect(toast.error).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByText("Instagram didn't respond. Try again.")).toBeNull();
  });

  it("an error that can't be retried has no Try again", async () => {
    nav.search = "error=account_in_use";
    renderPage(() => json(account()));
    await screen.findByText(/connected to another Social Hood workspace/);
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("the empty state offers every Connect button, once", async () => {
    renderPage(() => json(account()));
    expect(await screen.findByRole("button", { name: /Connect Instagram/ })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Connect Instagram/ })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: /Connect Facebook/ })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: /Connect WhatsApp/ })).toHaveLength(1);
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

  it("lists an account being deleted as Deleting…, among the disconnected ones", async () => {
    renderWithApi(<ConnectionsPage />, {
      handlers: {
        "GET /v1/w/:wid/social-accounts": () =>
          json({ items: [account({ id: "a9", display_name: "Gone Soon", status: "disconnected", deleting: true })] }),
      },
    });
    const card = await screen.findByRole("article", { name: "Gone Soon" });
    expect(within(card).getByText("Deleting…")).toBeInTheDocument();
    expect(within(card).queryAllByRole("button")).toEqual([]);
    const filters = screen.getByRole("radiogroup", { name: "Show accounts" });
    expect(counts(filters)).toEqual(["All1", "Connected0", "Disconnected1", "Sandboxes0"]);
  });

  it("Auto on the Free plan opens the upgrade dialog, with no request (UI-061)", async () => {
    const user = userEvent.setup();
    const { calls } = renderWithApi(<ConnectionsPage />, {
      ws: { ...workspace, plan: "free" },
      upgradeDialog: true,
      handlers: { "GET /v1/w/:wid/social-accounts": () => json({ items }) },
    });
    const card = await screen.findByRole("article", { name: "Maple Bakery" });
    await user.click(within(card).getByRole("combobox", { name: /AI replies/ }));
    await user.click(await screen.findByRole("option", { name: /Auto/ }));
    expect(await screen.findByTestId("upgrade-dialog")).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "PATCH")).toEqual([]);
  });

  it("has no breadcrumb (D-08) and keeps the connect actions", async () => {
    renderList();
    expect(await screen.findByRole("heading", { level: 1, name: "Connections" })).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Breadcrumb" })).toBeNull();
    expect(screen.getByRole("button", { name: /Connect Instagram/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Connect WhatsApp/ })).toBeInTheDocument();
  });
});

describe("deleting an account's data (C-067)", () => {
  it("Delete account and data sends the typed handle, then the list shows Deleting…", async () => {
    const user = userEvent.setup();
    let deleting = false;
    const { calls } = renderWithApi(<ConnectionsPage />, {
      handlers: {
        "GET /v1/w/:wid/social-accounts": () =>
          json({ items: [account(deleting ? { status: "disconnected", deleting: true } : {})] }),
        "DELETE /v1/w/:wid/social-accounts/:account_id": () => {
          deleting = true;
          return noContent();
        },
      },
    });
    const card = await screen.findByRole("article", { name: "Maple Bakery" });
    await user.click(within(card).getByRole("button", { name: /More actions/ }));
    await user.click(await screen.findByRole("menuitem", { name: "Delete account and data" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.type(within(dialog).getByLabelText(/to confirm/), "@maple.bakery");
    await user.click(within(dialog).getByRole("button", { name: "Disconnect and delete" }));

    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Deleting @maple.bakery and its data"));
    const sent = calls.find((c) => c.method === "DELETE");
    expect(sent?.path).toBe("/v1/w/w1/social-accounts/a1");
    expect(Object.fromEntries(sent?.url.searchParams ?? [])).toEqual({
      delete_data: "true",
      confirm: "@maple.bakery",
    });
    expect(await within(card).findByText("Deleting…")).toBeInTheDocument();
  });

  it("a refusal other than the typed handle is a toast", async () => {
    const user = userEvent.setup();
    renderWithApi(<ConnectionsPage />, {
      handlers: {
        "GET /v1/w/:wid/social-accounts": () => json({ items: [account({ status: "disconnected" })] }),
        "DELETE /v1/w/:wid/social-accounts/:account_id": () =>
          problem(409, "conflict", "Disconnect this account first, or use Disconnect and delete data."),
      },
    });
    const card = await screen.findByRole("article", { name: "Maple Bakery" });
    await user.click(within(card).getByRole("button", { name: /More actions/ }));
    await user.click(await screen.findByRole("menuitem", { name: "Delete account and data" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.type(within(dialog).getByLabelText(/to confirm/), "maple.bakery");
    await user.click(within(dialog).getByRole("button", { name: "Remove account" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledTimes(1));
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
  });
});

describe("connecting Facebook Pages (GR-29)", () => {
  const pages = [
    { id: "p1", name: "Maple Bakery", username: "maplebakery", picture_url: null, connected: false, can_connect: true, problem: null },
    { id: "p2", name: "Maple Cafe", username: null, picture_url: null, connected: false, can_connect: true, problem: null },
  ];

  it("Connect Facebook asks the API to start, and a refusal is a toast", async () => {
    const user = userEvent.setup();
    const { calls } = renderWithApi(<ConnectionsPage />, {
      handlers: {
        "GET /v1/w/:wid/social-accounts": () => json({ items: [account({ platform: "facebook", username: "maplebakery" })] }),
        "POST /v1/w/:wid/social-accounts/facebook/connect": () =>
          problem(503, "service_unavailable", "Facebook connections are not configured."),
      },
    });
    await user.click(await screen.findByRole("button", { name: /Connect Facebook/ }));
    await waitFor(() => expect(calls.some((c) => c.path === "/v1/w/w1/social-accounts/facebook/connect")).toBe(true));
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
  });

  it("opens the Pages dialog with the nonce Facebook sent back, and drops it from the address", async () => {
    nav.search = "facebook=n0nce";
    const { calls } = renderWithApi(<ConnectionsPage />, {
      handlers: {
        "GET /v1/w/:wid/social-accounts": () => json({ items: [] }),
        "POST /v1/w/:wid/social-accounts/facebook/pages": () => json({ items: pages }),
      },
    });
    expect(await screen.findByRole("list", { name: "Your Facebook Pages" })).toBeInTheDocument();
    expect(calls.find((c) => c.path.endsWith("/facebook/pages"))?.body).toEqual({ nonce: "n0nce" });
    expect(nav.replace).toHaveBeenCalledWith("/w/maple/settings/connections", { scroll: false });
  });

  it("a cancelled Facebook login is explained, and nothing starts on its own", async () => {
    nav.search = "error=access_denied&platform=facebook";
    const { calls } = renderWithApi(<ConnectionsPage />, {
      handlers: {
        "GET /v1/w/:wid/social-accounts": () => json({ items: [] }),
      },
    });
    expect(await screen.findByText("Connection cancelled")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
    expect(calls.filter((c) => c.path.endsWith("/connect"))).toEqual([]);
  });

  it("a Page's card names Facebook and its API", async () => {
    renderWithApi(<ConnectionsPage />, {
      handlers: {
        "GET /v1/w/:wid/social-accounts": () =>
          json({ items: [account({ platform: "facebook", username: "maplebakery", display_name: "Maple Bakery" })] }),
      },
    });
    const card = await screen.findByRole("article", { name: "Maple Bakery" });
    expect(within(card).getByRole("img", { name: "Facebook" })).toBeInTheDocument();
    expect(within(card).getByText("Facebook Pages API")).toBeInTheDocument();
    expect(within(card).getByText("@maplebakery")).toBeInTheDocument();
  });
});
