import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { bindMotionControl } from "./motion-control";
import { MotionToggle } from "./MotionToggle";

function stubReducedMotion(reduce: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: reduce && query.includes("reduce"),
    media: query,
    addEventListener() {},
    removeEventListener() {},
  }));
}

/** A hidden button has no accessible name to query by, so find it by its hook. */
const hiddenToggle = () => document.querySelector("[data-motion-toggle]") as HTMLButtonElement;

function scene() {
  render(
    <section data-motion-scope="" data-testid="scope">
      <MotionToggle />
      <p>Looping scene</p>
    </section>,
  );
  return screen.getByTestId("scope");
}

describe("the pause control for looping motion (C-157, WCAG 2.2.2)", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders hidden, so a page without script shows no dead control", () => {
    scene();
    const toggle = hiddenToggle();
    expect(toggle).not.toBeVisible();
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    expect(toggle).toHaveAttribute("aria-label", "Pause the animation");
  });

  it("once bound it shows, and pausing marks the scope and tells the listeners", async () => {
    stubReducedMotion(false);
    const scope = scene();
    const control = bindMotionControl(scope);
    const listener = vi.fn();
    control.subscribe(listener);
    const toggle = screen.getByRole("button", { name: "Pause the animation" });
    expect(toggle).toBeVisible();
    expect(control.paused).toBe(false);

    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-pressed", "true");
    expect(scope).toHaveAttribute("data-motion-paused");
    expect(control.paused).toBe(true);
    expect(listener).toHaveBeenLastCalledWith(true);

    await userEvent.click(toggle);
    expect(scope).not.toHaveAttribute("data-motion-paused");
    expect(listener).toHaveBeenLastCalledWith(false);
  });

  it("a script can pause on its own (off screen, after 5 s); the button then offers play", () => {
    stubReducedMotion(false);
    const scope = scene();
    const control = bindMotionControl(scope);
    control.pause();
    expect(screen.getByRole("button", { name: "Pause the animation" })).toHaveAttribute("aria-pressed", "true");
    control.play();
    expect(control.paused).toBe(false);
  });

  it("with reduced motion the toggle stays hidden and the scope counts as paused", () => {
    stubReducedMotion(true);
    const scope = scene();
    const control = bindMotionControl(scope);
    expect(control.paused).toBe(true);
    control.play();
    expect(control.paused).toBe(true);
    expect(hiddenToggle()).not.toBeVisible();
  });

  it("destroy hides the toggle again and stops listening", async () => {
    stubReducedMotion(false);
    const scope = scene();
    const control = bindMotionControl(scope);
    control.destroy();
    const toggle = hiddenToggle();
    expect(toggle).not.toBeVisible();
    expect(scope).not.toHaveAttribute("data-motion-paused");
  });
});
