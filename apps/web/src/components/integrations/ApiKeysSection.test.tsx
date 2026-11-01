import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import type { ApiKey, ApiScope, WorkspaceSummary } from "@/lib/api/types";
import { json, problem, renderWithApi, workspace, type Call } from "@/test/api";

import { ApiKeysSection } from "./ApiKeysSection";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

const SCOPES: ApiScope[] = [
  { scope: "contacts:read", description: "Read contacts and their custom fields." },
  { scope: "contacts:write", description: "Create contacts and change their email, phone and custom fields." },
  { scope: "messages:send", description: "Send a message in a conversation, inside the platform's reply window." },
];

function key(values: Partial<ApiKey> = {}): ApiKey {
  return {
    id: "k-1",
    name: "Sheets sync",
    key_prefix: "shk_aaaaaaaa",
    scopes: ["contacts:read"],
    created_at: "2026-10-20T09:00:00Z",
    last_used_at: null,
    revoked_at: null,
    expires_at: null,
    allowed_ips: [],
    made_by_former_member: false,
    ...values,
  };
}

beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});

function setup({
  items = [] as ApiKey[],
  ws = workspace,
  create,
}: { items?: ApiKey[]; ws?: WorkspaceSummary; create?: (call: Call) => Response } = {}) {
  return renderWithApi(<ApiKeysSection />, {
    ws,
    upgradeDialog: true,
    handlers: {
      "GET /v1/w/:wid/api-keys": () => json({ items, scopes: SCOPES, active_limit: 20 }),
      "POST /v1/w/:wid/api-keys": (call) =>
        create
          ? create(call)
          : json({ ...key({ id: "k-2" }), ...(call.body as object), key: "shk_the-whole-key-shown-once" }, 201),
      "DELETE /v1/w/:wid/api-keys/:id": () => json(key({ revoked_at: "2026-10-24T10:00:00Z" })),
      "PATCH /v1/w/:wid/api-keys/:id": (call) => json(key(call.body as Partial<ApiKey>)),
    },
  });
}

beforeEach(() => {
  toast.success.mockReset();
  toast.error.mockReset();
});

describe("Settings > API keys (GR-25)", () => {
  it("lists keys by prefix with their scopes and when they were last used, never the key", async () => {
    setup({
      items: [
        key({ last_used_at: new Date(Date.now() - 3_600_000).toISOString() }),
        key({ id: "k-3", name: "Old", revoked_at: "2026-10-22T09:00:00Z" }),
      ],
    });
    const rows = await screen.findAllByTestId("api-key");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent("Sheets sync");
    expect(rows[0]).toHaveTextContent("shk_aaaaaaaa");
    expect(rows[0]).toHaveTextContent("contacts:read");
    expect(rows[0]).toHaveTextContent(/last used/);
    expect(within(rows[0]).getByRole("button", { name: "Revoke" })).toBeInTheDocument();
    expect(rows[1]).toHaveTextContent("Revoked");
    expect(within(rows[1]).queryByRole("button", { name: "Revoke" })).not.toBeInTheDocument();
  });

  it("says a key was never used", async () => {
    setup({ items: [key()] });
    expect(await screen.findByText(/never used/)).toBeInTheDocument();
  });

  it("creates a key with its scopes and shows it once", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    expect(await screen.findByText(/No API keys yet/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Create API key" }));
    const dialog = await screen.findByRole("dialog", { name: "Create an API key" });
    const submit = within(dialog).getByRole("button", { name: "Create key" });
    expect(submit).toBeDisabled(); // a name first
    await user.type(within(dialog).getByRole("textbox", { name: "Name" }), "Zapier");
    expect(within(dialog).getByRole("checkbox", { name: /contacts:read/ })).toBeChecked(); // read-only by default
    await user.click(within(dialog).getByRole("checkbox", { name: /messages:send/ }));
    await user.click(submit);

    const shown = await screen.findByRole("dialog", { name: "Your API key" });
    expect(within(shown).getByTestId("api-key-value")).toHaveTextContent("shk_the-whole-key-shown-once");
    expect(within(shown).getByText(/see it again/i)).toBeInTheDocument();
    const [post] = calls.filter((c) => c.method === "POST");
    expect(post.body).toEqual({ name: "Zapier", scopes: ["contacts:read", "messages:send"] });

    await user.click(within(shown).getByRole("button", { name: "Done" }));
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Your API key" })).not.toBeInTheDocument());
    expect(screen.queryByText("shk_the-whole-key-shown-once")).not.toBeInTheDocument();
  });

  it("cannot make a key with no scope", async () => {
    const user = userEvent.setup();
    setup();
    await user.click(await screen.findByRole("button", { name: "Create API key" }));
    const dialog = await screen.findByRole("dialog", { name: "Create an API key" });
    await user.type(within(dialog).getByRole("textbox", { name: "Name" }), "Zapier");
    await user.click(within(dialog).getByRole("checkbox", { name: /contacts:read/ }));
    expect(within(dialog).getByRole("button", { name: "Create key" })).toBeDisabled();
  });

  it("asks before revoking, then revokes", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ items: [key()] });
    await user.click(await screen.findByRole("button", { name: "Revoke" }));
    const confirm = await screen.findByRole("alertdialog", { name: "Revoke Sheets sync?" });
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
    await user.click(within(confirm).getByRole("button", { name: "Revoke key" }));
    await waitFor(() =>
      expect(calls.some((c) => c.method === "DELETE" && c.path.endsWith("/api-keys/k-1"))).toBe(true),
    );
    expect(toast.success).toHaveBeenCalledWith("API key revoked");
  });

  it("tells a Free workspace the API is part of Pro instead of offering the form", async () => {
    setup({ ws: { ...workspace, plan: "free" } });
    expect(await screen.findByText("The public API, API keys and Zapier are part of Pro.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Create API key" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "See plans" })).toHaveAttribute("href", "/w/maple/settings/billing");
  });

  it("opens the upgrade dialog when the API says the plan lacks it", async () => {
    const user = userEvent.setup();
    setup({
      create: () =>
        problem(402, "entitlement_required", "The public API, API keys and Zapier are part of Pro.", {
          entitlement: "public_api",
        }),
    });
    await user.click(await screen.findByRole("button", { name: "Create API key" }));
    const dialog = await screen.findByRole("dialog", { name: "Create an API key" });
    await user.type(within(dialog).getByRole("textbox", { name: "Name" }), "Zapier");
    await user.click(within(dialog).getByRole("button", { name: "Create key" }));
    expect(await screen.findByText("Public API access is part of Pro")).toBeInTheDocument();
    expect(toast.error).not.toHaveBeenCalled(); // the dialog says it, not a toast
  });

  it("shows when a key expires, the addresses it works from and a former member's key (C-167)", async () => {
    setup({
      items: [
        key({ expires_at: "2099-01-12T08:00:00Z", allowed_ips: ["203.0.113.7", "2001:db8::/32"] }),
        key({ id: "k-4", name: "Lapsed", expires_at: "2020-01-01T00:00:00Z" }),
        key({ id: "k-5", name: "Legacy", made_by_former_member: true }),
      ],
    });
    const rows = await screen.findAllByTestId("api-key");
    expect(rows[0]).toHaveTextContent("expires 12 Jan 2099");
    expect(within(rows[0]).getByTestId("api-key-ips")).toHaveTextContent("Only from 203.0.113.7, 2001:db8::/32");
    expect(within(rows[1]).getByText("Expired")).toBeInTheDocument();
    expect(rows[1]).not.toHaveTextContent("expires");
    expect(rows[2]).toHaveTextContent("Made by a former member");
    expect(rows[2]).not.toHaveTextContent("expire");
  });

  it("creates a key with an expiry and allowed addresses", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    await user.click(await screen.findByRole("button", { name: "Create API key" }));
    const dialog = await screen.findByRole("dialog", { name: "Create an API key" });
    await user.type(within(dialog).getByRole("textbox", { name: "Name" }), "Office server");
    await user.click(within(dialog).getByRole("combobox", { name: "Expires" }));
    await user.click(await screen.findByRole("option", { name: "90 days" }));
    const ips = within(dialog).getByRole("textbox", { name: "Allowed IP addresses" });
    await user.type(ips, "203.0.113.0/24{Enter}10.0.0.1,");
    await user.click(within(dialog).getByRole("button", { name: "Create key" }));
    await screen.findByRole("dialog", { name: "Your API key" });
    const [post] = calls.filter((c) => c.method === "POST");
    expect(post.body).toEqual({
      name: "Office server",
      scopes: ["contacts:read"],
      expires_in_days: 90,
      allowed_ips: ["203.0.113.0/24", "10.0.0.1"],
    });
  });

  it("edits a key's name and addresses, never its scopes", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ items: [key({ allowed_ips: ["203.0.113.7"] })] });
    await user.click(await screen.findByRole("button", { name: "Edit Sheets sync" }));
    const dialog = await screen.findByRole("dialog", { name: "Edit Sheets sync" });
    expect(within(dialog).queryByRole("checkbox")).not.toBeInTheDocument();
    const name = within(dialog).getByRole("textbox", { name: "Name" });
    await user.clear(name);
    await user.type(name, "Sheets");
    await user.click(within(dialog).getByRole("button", { name: "Remove 203.0.113.7" }));
    await user.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(calls.some((c) => c.method === "PATCH")).toBe(true));
    const patch = calls.find((c) => c.method === "PATCH");
    expect(patch?.path).toMatch(/\/api-keys\/k-1$/);
    expect(patch?.body).toEqual({ name: "Sheets", allowed_ips: [] });
    expect(toast.success).toHaveBeenCalledWith("API key saved");
  });

  it("links to the API reference", async () => {
    setup();
    expect(await screen.findByRole("link", { name: "Read the API reference" })).toHaveAttribute(
      "href",
      "/developers/api",
    );
  });
});
