import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AutosaveStatus } from "./AutosaveStatus";

describe("AutosaveStatus (D-08)", () => {
  it("says nothing before the first change, then Saving… and Saved", () => {
    const { rerender } = render(<AutosaveStatus saving={false} saved={false} />);
    expect(screen.getByRole("status")).toBeEmptyDOMElement();
    rerender(<AutosaveStatus saving saved={false} />);
    expect(screen.getByRole("status")).toHaveTextContent("Saving…");
    rerender(<AutosaveStatus saving={false} saved />);
    expect(screen.getByRole("status")).toHaveTextContent("Saved");
  });
});
