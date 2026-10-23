import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { account, json, renderWithApi } from "@/test/api";

import { EntryLinksPage } from "./EntryLinksPage";

const link = {
  id: "l1",
  social_account_id: "a1",
  account_username: "maple.bakery",
  name: "Shop window",
  code: "spring26",
  url: "https://ig.me/m/maple.bakery?ref=spring26",
  automation_id: "au1",
  automation_name: "Welcome",
  opened_conversations: 12,
  runs: 9,
  created_at: "2026-10-20T10:00:00Z",
};

function setup(items: (typeof link)[]) {
  return renderWithApi(<EntryLinksPage />, {
    handlers: {
      "GET /v1/w/:wid/entry-links": () => json({ items }),
      "GET /v1/w/:wid/social-accounts": () => json({ items: [account()] }),
      "GET /v1/w/:wid/automations": () => json({ items: [] }),
    },
  });
}

describe("EntryLinksPage (GR-08)", () => {
  it("lists each link with its address, automation and counts", async () => {
    setup([link]);
    expect(await screen.findByText("Shop window")).toBeInTheDocument();
    expect(screen.getByTestId("entry-link-url")).toHaveTextContent("https://ig.me/m/maple.bakery?ref=spring26");
    expect(screen.getByText('Starts "Welcome"')).toBeInTheDocument();
    expect(screen.getByTestId("entry-link-opened")).toHaveTextContent("12");
    expect(screen.getByTestId("entry-link-runs")).toHaveTextContent("9");
    expect(screen.getByRole("button", { name: "Copy link" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "QR code" })).toBeInTheDocument();
  });

  it("explains an empty list", async () => {
    setup([]);
    expect(await screen.findByText("No entry links yet")).toBeInTheDocument();
  });
});
