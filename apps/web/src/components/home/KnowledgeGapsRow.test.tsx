import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { KnowledgeGapsRow } from "./KnowledgeGapsRow";

describe("Home: questions the AI couldn't answer (UX-SCR-01, FR-KB-06)", () => {
  it("links the open count to Knowledge", () => {
    render(<KnowledgeGapsRow count={3} slug="maple" />);
    const link = screen.getByRole("link", { name: "3 questions the AI couldn't answer" });
    expect(link).toHaveAttribute("href", "/w/maple/knowledge");
  });

  it("one question, and nothing at zero", () => {
    const { rerender } = render(<KnowledgeGapsRow count={1} slug="maple" />);
    expect(screen.getByRole("link", { name: "1 question the AI couldn't answer" })).toBeInTheDocument();
    rerender(<KnowledgeGapsRow count={0} slug="maple" />);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
