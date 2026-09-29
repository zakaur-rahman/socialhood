import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { focusStep, StepCard } from "./StepCard";

function node(step: string) {
  return document.querySelector(`#step-${step} [data-node]`);
}

describe("StepCard (UX-SCR-03)", () => {
  it("complete: brand node, announced as complete", () => {
    render(
      <StepCard id="when" label="When" state="complete">
        <p>Body</p>
      </StepCard>,
    );
    const section = screen.getByRole("region", { name: "When, complete" });
    expect(section).toHaveAttribute("data-state", "complete");
    expect(node("when")).toHaveClass("bg-brand");
    expect(screen.getByText("Body")).toBeInTheDocument();
  });

  it("incomplete: neutral node, announced as not finished", () => {
    render(
      <StepCard id="keywords" label="Keywords" state="incomplete">
        <p>Body</p>
      </StepCard>,
    );
    expect(screen.getByRole("region", { name: "Keywords, not finished" })).toHaveAttribute("data-state", "incomplete");
    expect(node("keywords")).not.toHaveClass("bg-brand");
    expect(node("keywords")).not.toHaveClass("bg-danger");
  });

  it("error: danger node and border, with each problem listed", () => {
    render(
      <StepCard id="then" label="Then" state="error" errors={["Add a message.", "Use a full link that starts with https://"]}>
        <p>Body</p>
      </StepCard>,
    );
    const section = screen.getByRole("region", { name: "Then, needs attention" });
    expect(section).toHaveClass("border-danger");
    expect(node("then")).toHaveClass("bg-danger");
    expect(screen.getByText("Add a message.")).toBeInTheDocument();
    expect(screen.getByText("Use a full link that starts with https://")).toBeInTheDocument();
  });

  it("focusStep takes the user to the step's first field, or the step itself", () => {
    render(
      <>
        <StepCard id="keywords" label="Keywords" state="incomplete">
          <label htmlFor="k">Keyword</label>
          <input id="k" />
        </StepCard>
        <StepCard id="settings" label="Settings" state="error">
          <p>Summary</p>
        </StepCard>
      </>,
    );
    focusStep("keywords");
    expect(screen.getByLabelText("Keyword")).toHaveFocus();
    focusStep("settings", { field: false });
    expect(screen.getByRole("region", { name: "Settings, needs attention" })).toHaveFocus();
  });
});
