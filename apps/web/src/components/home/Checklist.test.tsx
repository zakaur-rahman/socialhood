import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ChecklistStep } from "@/lib/api/types";

import { Checklist } from "./Checklist";

const steps = (done: Partial<Record<ChecklistStep["key"], boolean>> = {}): ChecklistStep[] =>
  (["connect_account", "add_knowledge", "choose_ai_mode", "create_automation"] as const).map((key) => ({
    key,
    done: done[key] ?? false,
  }));

describe("Checklist (FR-ACC-04)", () => {
  it("expands only the first open step, with its action", () => {
    render(<Checklist steps={steps()} slug="aria" onDismiss={() => {}} />);
    expect(screen.getByText("0 of 4 done")).toBeInTheDocument();
    const action = screen.getByRole("link", { name: "Connect an account" });
    expect(action).toHaveAttribute("href", "/w/aria/settings/connections");
    expect(screen.queryByRole("link", { name: "Add knowledge" })).not.toBeInTheDocument();
  });

  it("ticks done steps from data and moves to the next open one", () => {
    render(<Checklist steps={steps({ connect_account: true })} slug="aria" onDismiss={() => {}} />);
    expect(screen.getByText("1 of 4 done")).toBeInTheDocument();
    expect(screen.getAllByLabelText("Done")).toHaveLength(1);
    expect(screen.getByRole("link", { name: "Add knowledge" })).toBeInTheDocument();
  });

  it("sends Create an automation straight to the template gallery (F-11)", () => {
    render(
      <Checklist
        steps={steps({ connect_account: true, add_knowledge: true, choose_ai_mode: true })}
        slug="aria"
        onDismiss={() => {}}
      />,
    );
    expect(screen.getByRole("link", { name: "Browse templates" })).toHaveAttribute("href", "/w/aria/automations/new");
  });

  it("calls onDismiss", async () => {
    const onDismiss = vi.fn();
    render(<Checklist steps={steps()} slug="aria" onDismiss={onDismiss} />);
    await userEvent.click(screen.getByRole("button", { name: "Dismiss the checklist" }));
    expect(onDismiss).toHaveBeenCalledOnce();
  });
});
