import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LEGAL_DOCUMENTS } from "@/lib/legal";

import { LegalPage } from "./LegalPage";

const SECTIONS = [
  { id: "first", title: "First part", body: <p>One.</p> },
  { id: "second", title: "Second part", body: <p>Two.</p> },
];

describe("LegalPage (C-159 layout)", () => {
  it("one h1, the dates, a labelled summary, contents that link every numbered section, and the reading bar", () => {
    const { container } = render(<LegalPage document="refunds" summary={<p>The short version.</p>} sections={SECTIONS} />);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(LEGAL_DOCUMENTS.refunds.title);
    expect(screen.getByText(/^Last updated /)).toBeInTheDocument();

    const summary = screen.getByRole("region", { name: "Summary" });
    expect(summary).toHaveTextContent("The short version.");

    const contents = screen.getByRole("navigation", { name: "Contents" });
    const links = within(contents).getAllByRole("link");
    expect(links.map((link) => link.getAttribute("href"))).toEqual(["#first", "#second"]);

    // The numbers stay in the headings' text, so anchors and screen readers read "1. First part".
    expect(screen.getByRole("heading", { level: 2, name: "1. First part" })).toHaveAttribute("id", "first");
    expect(screen.getByRole("heading", { level: 2, name: "2. Second part" })).toHaveAttribute("id", "second");

    expect(container.querySelector(".read-bar")).toHaveAttribute("aria-hidden");
  });
});
