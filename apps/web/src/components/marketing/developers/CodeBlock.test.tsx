import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Code } from "./CodeBlock";

const COMMAND = "claude mcp add --transport http amplychat https://api.amplychat.com/mcp";

function withClipboard(writeText: (text: string) => Promise<void>) {
  Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
}

describe("Code", () => {
  it("copies exactly the command and says so", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    withClipboard(writeText);
    render(<Code>{COMMAND}</Code>);
    expect(screen.getByText(COMMAND)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Copy" }));
    expect(writeText).toHaveBeenCalledWith(COMMAND);
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Copied"));
  });

  it("says when the browser refuses, and the text stays there", async () => {
    withClipboard(vi.fn().mockRejectedValue(new Error("denied")));
    render(<Code>{COMMAND}</Code>);
    fireEvent.click(screen.getByRole("button", { name: "Copy" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Couldn't copy"));
    expect(screen.getByText(COMMAND)).toBeInTheDocument();
  });
});
