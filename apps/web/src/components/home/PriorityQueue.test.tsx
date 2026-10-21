import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PriorityQueue } from "./PriorityQueue";

const NOW = new Date("2026-10-17T10:00:00Z");

describe("PriorityQueue's empty state", () => {
  it("says nothing is waiting when no conversation needs a reply", () => {
    render(<PriorityQueue items={[]} needsReply={0} slug="acme" now={NOW} />);
    expect(screen.getByTestId("queue-empty")).toHaveTextContent("Nothing is waiting.");
  });

  it("explains closed reply windows when conversations need a reply but none can be answered", () => {
    render(<PriorityQueue items={[]} needsReply={13} slug="acme" now={NOW} />);
    const empty = screen.getByTestId("queue-empty");
    expect(empty).toHaveTextContent("No replies are possible right now.");
    expect(empty).toHaveTextContent("13 conversations need a reply, but the reply window has closed.");
    expect(empty).not.toHaveTextContent("Nothing is waiting.");
    expect(screen.getByRole("link", { name: /Open inbox/ })).toHaveTextContent("Open inbox (13)");
  });

  it("uses the singular for one conversation", () => {
    render(<PriorityQueue items={[]} needsReply={1} slug="acme" now={NOW} />);
    expect(screen.getByTestId("queue-empty")).toHaveTextContent("1 conversation needs a reply");
  });
});
