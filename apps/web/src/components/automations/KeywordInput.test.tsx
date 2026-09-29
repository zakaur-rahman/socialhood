import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { KeywordInput } from "./KeywordInput";

function Harness({ initial = [], error }: { initial?: string[]; error?: string }) {
  const [keywords, setKeywords] = useState(initial);
  return (
    <>
      <KeywordInput id="kw" keywords={keywords} onChange={setKeywords} error={error} />
      <pre data-testid="value">{JSON.stringify(keywords)}</pre>
    </>
  );
}

const value = () => JSON.parse(screen.getByTestId("value").textContent ?? "[]") as string[];
const field = () => screen.getByRole("textbox", { name: "Add a keyword" });

describe("KeywordInput (UX-SCR-03)", () => {
  it("adds on Enter and on a comma", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.type(field(), "link{Enter}");
    await user.type(field(), "price,");
    expect(value()).toEqual(["link", "price"]);
    expect(field()).toHaveValue("");
    expect(screen.getByText("2 of 50")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Added “price”.");
  });

  it("splits a pasted list", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(field());
    await user.paste("link, price\ndetails");
    expect(value()).toEqual(["link", "price", "details"]);
    expect(screen.getByRole("status")).toHaveTextContent("Added 3 keywords.");
  });

  it("skips duplicates as the matcher compares them", async () => {
    const user = userEvent.setup();
    render(<Harness initial={["price"]} />);
    await user.type(field(), "PRICE{Enter}");
    expect(value()).toEqual(["price"]);
    expect(screen.getByRole("status")).toHaveTextContent("“PRICE” is already a keyword.");
  });

  it("removes with the chip's button or Backspace in the empty field", async () => {
    const user = userEvent.setup();
    render(<Harness initial={["link", "price", "details"]} />);
    await user.click(screen.getByRole("button", { name: "Remove price" }));
    expect(value()).toEqual(["link", "details"]);
    await user.click(field());
    await user.keyboard("{Backspace}");
    expect(value()).toEqual(["link"]);
  });

  it("shows an error from activation on the field", () => {
    render(<Harness error="Add at least one keyword." />);
    expect(field()).toHaveAttribute("aria-invalid", "true");
    expect(field()).toHaveAccessibleDescription(/Add at least one keyword\./);
  });
});
