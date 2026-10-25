import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { CatalogueLimits, CsvImportPreview } from "@/lib/api/types";
import { CSV_COLUMNS } from "@/lib/catalogue/format";
import { json, problem, renderWithApi, type Call } from "@/test/api";

import { ImportDialog } from "./ImportDialog";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

const LIMITS: CatalogueLimits = {
  entitled: true,
  product_cap: 1000,
  import_row_cap: 500,
  csv_max_chars: 900_000,
  default_currency: "INR",
};

const PREVIEW: CsvImportPreview = {
  rows: [
    { line: 2, action: "create", name: "Cotton kurta", variant: "Blue / M", errors: [] },
    { line: 3, action: "update", name: "Silk scarf", variant: null, errors: [] },
    { line: 4, action: "error", name: "Hat", variant: null, errors: ["Enter the price as a number, like 799 or 799.50."] },
  ],
  total_rows: 3,
  create: 1,
  update: 1,
  errors: 1,
  products: 2,
  row_cap: 500,
  columns: [...CSV_COLUMNS],
  ignored_columns: ["colour"],
};

const FILE = "name,price\nCotton kurta,799\nSilk scarf,499\nHat,lots\n";

function setup(handlers: Record<string, (call: Call) => Response> = {}) {
  const onOpenChange = vi.fn();
  const view = renderWithApi(<ImportDialog open onOpenChange={onOpenChange} limits={LIMITS} />, {
    upgradeDialog: false,
    handlers: {
      "POST /v1/w/:wid/products/import/preview": () => json(PREVIEW),
      "POST /v1/w/:wid/products/import": () => json({ created: 1, updated: 1, skipped: 1, products: 2 }),
      ...handlers,
    },
  });
  return { ...view, onOpenChange };
}

async function choose(content = FILE) {
  const user = userEvent.setup();
  const input = screen.getByTestId("csv-file-input");
  await user.upload(input, new File([content], "products.csv", { type: "text/csv" }));
  return user;
}

beforeEach(() => {
  toast.success.mockReset();
});

describe("CSV import (GR-31)", () => {
  it("documents the header row before a file is chosen", () => {
    setup();
    expect(screen.getByText(/The first line is the header row/)).toBeInTheDocument();
    expect(screen.getByText(CSV_COLUMNS.join(", "))).toBeInTheDocument();
    expect(screen.getByText(/up to 500 lines in one file/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Import" })).toBeDisabled();
  });

  it("previews every line with its problems before anything is saved", async () => {
    const { calls } = setup();
    await choose();
    expect(await screen.findByText("3 lines: 1 new, 1 to update, 1 left out.")).toBeInTheDocument();
    expect(screen.getByText("Not used: colour.")).toBeInTheDocument();
    const rows = screen.getAllByRole("row").slice(1);
    expect(within(rows[0]).getByText("New")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Update")).toBeInTheDocument();
    expect(within(rows[2]).getByText("Left out")).toBeInTheDocument();
    expect(within(rows[2]).getByText("Enter the price as a number, like 799 or 799.50.")).toBeInTheDocument();
    expect(calls.filter((c) => c.path.endsWith("/products/import")).length).toBe(0); // nothing saved yet
    expect(calls.find((c) => c.path.endsWith("/import/preview"))?.body).toEqual({ csv: FILE });
  });

  it("imports the valid lines with the same file", async () => {
    const { calls, onOpenChange } = setup();
    const user = await choose();
    await user.click(await screen.findByRole("button", { name: "Import 2 lines" }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Imported 2 products, 1 line left out"));
    expect(calls.find((c) => c.method === "POST" && c.path.endsWith("/products/import"))?.body).toEqual({ csv: FILE });
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("says when the file is over the plan's rows, with Upgrade", async () => {
    setup({
      "POST /v1/w/:wid/products/import/preview": () =>
        problem(402, "quota_exceeded", "This file has 900 rows. Your plan includes 500 rows in one import.", {
          entitlement: "catalogue_import_rows",
          limit: 500,
        }),
    });
    await choose();
    expect(await screen.findByText(/Your plan includes 500 rows in one import/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upgrade" })).toBeInTheDocument();
  });
});
