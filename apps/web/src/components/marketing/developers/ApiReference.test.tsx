import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { buildReference } from "@/lib/marketing/public-api";
import { SAMPLE } from "@/test/publicApiSample";

import { ApiReference, ApiReferenceUnavailable } from "./ApiReference";

function renderReference() {
  return render(<ApiReference reference={buildReference(SAMPLE)} baseUrl="https://api.example.test" />);
}

describe("the public API reference (GR-25)", () => {
  it("explains authentication with the key in a header and lists the scopes", () => {
    renderReference();
    const auth = screen.getByRole("region", { name: "Authentication" });
    expect(within(auth).getByText(/Authorization: Bearer \$SOCIALHOOD_API_KEY/)).toBeInTheDocument();
    expect(within(auth).getByRole("table", { name: "Scopes" })).toBeInTheDocument();
    expect(within(auth).getByText("contacts:write")).toBeInTheDocument();
  });

  it("has a heading, a contents link and a section for each area", () => {
    renderReference();
    expect(screen.getByRole("heading", { level: 1, name: "Amplychat public API" })).toBeInTheDocument();
    const contents = screen.getByRole("navigation", { name: "Contents" });
    expect(within(contents).getByRole("link", { name: "Contacts" })).toHaveAttribute("href", "#contacts");
    expect(within(contents).getByRole("link", { name: "REST hooks" })).toHaveAttribute("href", "#rest-hooks");
    expect(screen.getByRole("region", { name: "Contacts" })).toBeInTheDocument();
  });

  it("shows each operation with its method, path, scope, parameters and example", () => {
    renderReference();
    const create = screen.getByRole("article", { name: /POST\s*\/public\/v1\/contacts/ });
    expect(within(create).getByText("POST")).toBeInTheDocument();
    expect(within(create).getByText(/Needs the/)).toHaveTextContent("contacts:write");
    expect(within(create).getByText("account_id")).toBeInTheDocument();
    expect(within(create).getAllByText("required").length).toBe(2);
    expect(within(create).getByText(/-X POST "https:\/\/api\.example\.test\/public\/v1\/contacts"/)).toBeInTheDocument();
    // The scope line is not repeated in the prose.
    expect(within(create).queryByText(/Requires the/)).not.toBeInTheDocument();
    expect(within(create).getByText("Add a customer by phone number.")).toBeInTheDocument();
  });

  it("lists query parameters in a table a phone can scroll", () => {
    renderReference();
    const list = screen.getByRole("article", { name: /GET\s*\/public\/v1\/contacts$/ });
    const table = within(list).getByRole("table");
    expect(within(table).getByText("limit")).toBeInTheDocument();
    expect(within(table).getByText("Up to 100.")).toBeInTheDocument();
    expect(table.parentElement).toHaveClass("overflow-x-auto");
  });

  it("says so when the API can't be reached", () => {
    render(<ApiReferenceUnavailable />);
    expect(screen.getByRole("status")).toHaveTextContent("The API reference isn’t available right now.");
  });
});
