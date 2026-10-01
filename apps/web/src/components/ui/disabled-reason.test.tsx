import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { Button } from "./button";
import { DisabledReason } from "./disabled-reason";
import { TooltipProvider } from "./tooltip";

const REASON = "Scheduling needs an open reply window";

function setup(node: ReactNode) {
  const user = userEvent.setup();
  render(
    <TooltipProvider delayDuration={0}>
      <button type="button">Before</button>
      {node}
    </TooltipProvider>,
  );
  return user;
}

describe("DisabledReason (UI-ISS-026)", () => {
  it("is reachable by keyboard although the button is disabled, and shows the reason on focus", async () => {
    const user = setup(
      <DisabledReason reason={REASON}>
        <Button disabled>Schedule</Button>
      </DisabledReason>,
    );
    const button = screen.getByRole("button", { name: "Schedule" });
    expect(button).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Before" }));
    await user.tab();
    const wrapper = button.closest('[data-slot="disabled-reason"]')!;
    expect(wrapper).toHaveFocus();
    expect(await screen.findByRole("tooltip")).toHaveTextContent(REASON);
  });

  it("describes itself with an sr-only copy of the reason", () => {
    setup(
      <DisabledReason reason={REASON}>
        <Button disabled>Schedule</Button>
      </DisabledReason>,
    );
    const wrapper = screen.getByRole("button", { name: "Schedule" }).closest('[data-slot="disabled-reason"]')!;
    expect(wrapper).toHaveAttribute("tabindex", "0");
    const id = wrapper.getAttribute("aria-describedby")!;
    const description = document.getElementById(id)!;
    expect(description).toHaveTextContent(REASON);
    expect(description).toHaveClass("sr-only");
    expect(wrapper).toHaveAccessibleDescription(REASON);
  });

  it("shows the reason on hover", async () => {
    const user = setup(
      <DisabledReason reason={REASON}>
        <Button disabled>Schedule</Button>
      </DisabledReason>,
    );
    await user.hover(screen.getByRole("button", { name: "Schedule" }).closest('[data-slot="disabled-reason"]')!);
    expect(await screen.findByRole("tooltip")).toHaveTextContent(REASON);
  });

  it("shows the reason on a tap (tooltips don't open on touch by themselves)", async () => {
    const user = setup(
      <DisabledReason reason={REASON}>
        <Button disabled>Schedule</Button>
      </DisabledReason>,
    );
    await user.pointer({
      keys: "[TouchA]",
      target: screen.getByRole("button", { name: "Schedule" }).closest('[data-slot="disabled-reason"]')!,
    });
    expect(await screen.findByRole("tooltip")).toHaveTextContent(REASON);
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("tooltip")).toBeNull());
  });

  it("without a reason, steps aside: not focusable, not described, the control works as usual", async () => {
    let clicked = 0;
    const user = setup(
      <DisabledReason reason={null}>
        <Button onClick={() => (clicked += 1)}>Schedule</Button>
      </DisabledReason>,
    );
    const button = screen.getByRole("button", { name: "Schedule" });
    const wrapper = button.closest('[data-slot="disabled-reason"]')!;
    expect(wrapper).not.toHaveAttribute("tabindex");
    expect(wrapper).not.toHaveAttribute("aria-describedby");

    await user.click(screen.getByRole("button", { name: "Before" }));
    await user.tab();
    expect(button).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(clicked).toBe(1);
    expect(screen.queryByRole("tooltip")).toBeNull();
    expect(screen.queryByText(REASON)).toBeNull();
  });

  it("takes layout classes for the control's place in its row", () => {
    setup(
      <DisabledReason reason={REASON} className="w-full">
        <Button disabled className="w-full">
          Send
        </Button>
      </DisabledReason>,
    );
    expect(screen.getByRole("button", { name: "Send" }).closest('[data-slot="disabled-reason"]')).toHaveClass("w-full");
  });
});
