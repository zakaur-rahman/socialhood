import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ContactImportPreview } from "@/lib/api/types";
import { account, json, renderWithApi, type Call } from "@/test/api";

import { ImportContactsDialog } from "./ImportContactsDialog";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

const PREVIEW: ContactImportPreview = {
  rows: [
    { line: 2, phone: "+919876543210", action: "create", reasons: [] },
    { line: 3, phone: "+919812345678", action: "update", reasons: ["Marketing consent was withdrawn, so it stays withdrawn."] },
    { line: 4, phone: "", action: "skip", reasons: ["Enter a phone number with its country code, like +91 98765 43210."] },
  ],
  total_rows: 3,
  created: 1,
  updated: 1,
  unchanged: 0,
  skipped: 1,
  consents_granted: 1,
  consents_kept_withdrawn: 1,
  consent_ignored: 0,
  tags_created: 0,
  row_cap: 5000,
  columns: ["Phone", "Name"],
  ignored_columns: ["username"],
};

const FILE = "Phone,Name,WhatsApp marketing\n+919876543210,Asha,yes\n";
const NUMBER = account({ id: "wa1", platform: "whatsapp", username: null, display_name: "Maple WhatsApp" });

function setup(handlers: Record<string, (call: Call) => Response> = {}) {
  const onOpenChange = vi.fn();
  const view = renderWithApi(<ImportContactsDialog open onOpenChange={onOpenChange} />, {
    handlers: {
      "GET /v1/w/:wid/social-accounts": () => json({ items: [account(), NUMBER] }),
      "POST /v1/w/:wid/contacts/import/preview": () => json(PREVIEW),
      "POST /v1/w/:wid/contacts/import": () =>
        json({ created: 1, updated: 1, unchanged: 0, skipped: 1, consents_granted: 1, consents_kept_withdrawn: 1, tags_created: 0 }),
      ...handlers,
    },
  });
  return { ...view, onOpenChange };
}

async function choose(content = FILE) {
  const user = userEvent.setup();
  const input = await screen.findByTestId("csv-file-input");
  await user.upload(input, new File([content], "people.csv", { type: "text/csv" }));
  return user;
}

beforeEach(() => {
  toast.success.mockReset();
});

describe("Contact import (GR-43)", () => {
  it("explains the file and has no import until one is chosen", async () => {
    setup();
    expect(await screen.findByText(/The first line is the header row/)).toBeInTheDocument();
    expect(screen.getByText(/Up to 5,000 rows in one file/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Import" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Download a starter file" })).toBeInTheDocument();
  });

  it("previews new, updated and left-out rows with their reasons, and saves nothing", async () => {
    const { calls } = setup();
    await choose();
    expect(await screen.findByText(/3 rows: 1 new, 1 to update, 0 unchanged, 1 left out\./)).toBeInTheDocument();
    expect(screen.getByText("Not used: username.")).toBeInTheDocument();
    expect(screen.getByText(/1 withdrew their consent earlier, so they stay opted out/)).toBeInTheDocument();
    const rows = screen.getAllByRole("row").slice(1);
    expect(within(rows[0]).getByText("New")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Update")).toBeInTheDocument();
    expect(within(rows[2]).getByText("Left out")).toBeInTheDocument();
    expect(calls.filter((c) => c.path.endsWith("/contacts/import")).length).toBe(0);
    expect(calls.find((c) => c.path.endsWith("/import/preview"))?.body).toEqual({
      account_id: "wa1",
      csv: FILE,
      grant_consent: false,
      file_name: "people.csv",
    });
  });

  it("sends the consent tick with the preview and the import", async () => {
    const { calls, onOpenChange } = setup();
    const user = await choose();
    await screen.findByText(/3 rows/);
    await user.click(screen.getByRole("checkbox", { name: /These people agreed to get WhatsApp marketing from us/ }));
    await waitFor(() =>
      expect(calls.filter((c) => c.path.endsWith("/import/preview")).at(-1)?.body).toMatchObject({ grant_consent: true }),
    );
    await user.click(await screen.findByRole("button", { name: "Import 2 contacts" }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Imported 1 new and 1 updated contacts, 1 row left out"));
    expect(calls.find((c) => c.method === "POST" && c.path.endsWith("/contacts/import"))?.body).toMatchObject({
      account_id: "wa1",
      csv: FILE,
      grant_consent: true,
    });
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("needs a WhatsApp number", async () => {
    setup({ "GET /v1/w/:wid/social-accounts": () => json({ items: [account()] }) });
    expect(await screen.findByText(/Contacts can only be imported to a WhatsApp number/)).toBeInTheDocument();
    expect(screen.queryByTestId("csv-file-input")).not.toBeInTheDocument();
  });
});
