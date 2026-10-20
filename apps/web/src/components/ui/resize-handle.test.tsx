import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { ResizeHandle } from "./resize-handle";

function Pane({ edge, initial = 320 }: { edge: "start" | "end"; initial?: number }) {
  const [width, setWidth] = useState(initial);
  return (
    <div style={{ position: "relative", width }}>
      <ResizeHandle
        edge={edge}
        label="Resize the list"
        value={width}
        min={260}
        max={560}
        onChange={setWidth}
        onReset={() => setWidth(320)}
      />
    </div>
  );
}

const handle = () => screen.getByRole("separator", { name: "Resize the list" });

describe("ResizeHandle (UI-078)", () => {
  it("is a focusable vertical separator that states its width range", () => {
    render(<Pane edge="end" />);
    expect(handle()).toHaveAttribute("aria-orientation", "vertical");
    expect(handle()).toHaveAttribute("aria-valuenow", "320");
    expect(handle()).toHaveAttribute("aria-valuemin", "260");
    expect(handle()).toHaveAttribute("aria-valuemax", "560");
    expect(handle()).toHaveAttribute("tabindex", "0");
    expect(handle()).toHaveClass("hidden", "md:block");
  });

  it("on a pane's right edge, → widens and ← narrows, by 16 px or 64 px with Shift", async () => {
    const user = userEvent.setup();
    render(<Pane edge="end" />);
    handle().focus();
    await user.keyboard("{ArrowRight}");
    expect(handle()).toHaveAttribute("aria-valuenow", "336");
    await user.keyboard("{ArrowLeft}{ArrowLeft}");
    expect(handle()).toHaveAttribute("aria-valuenow", "304");
    await user.keyboard("{Shift>}{ArrowRight}{/Shift}");
    expect(handle()).toHaveAttribute("aria-valuenow", "368");
  });

  it("on a pane's left edge, ← widens", async () => {
    const user = userEvent.setup();
    render(<Pane edge="start" />);
    handle().focus();
    await user.keyboard("{ArrowLeft}");
    expect(handle()).toHaveAttribute("aria-valuenow", "336");
  });

  it("Home and End go to the limits, and the width never leaves them", async () => {
    const user = userEvent.setup();
    render(<Pane edge="end" />);
    handle().focus();
    await user.keyboard("{End}");
    expect(handle()).toHaveAttribute("aria-valuenow", "560");
    await user.keyboard("{ArrowRight}");
    expect(handle()).toHaveAttribute("aria-valuenow", "560");
    await user.keyboard("{Home}");
    expect(handle()).toHaveAttribute("aria-valuenow", "260");
  });

  it("a double-click resets the width", async () => {
    const user = userEvent.setup();
    render(<Pane edge="end" initial={500} />);
    await user.dblClick(handle());
    expect(handle()).toHaveAttribute("aria-valuenow", "320");
  });

  it("dragging changes the width by the pointer's movement", () => {
    render(<Pane edge="end" />);
    const el = handle();
    el.setPointerCapture = () => {};
    el.hasPointerCapture = () => true;
    el.releasePointerCapture = () => {};
    fireEvent.pointerDown(el, { button: 0, clientX: 100, pointerId: 1 });
    fireEvent.pointerMove(el, { clientX: 140, pointerId: 1 });
    expect(el).toHaveAttribute("aria-valuenow", "360");
    fireEvent.pointerUp(el, { clientX: 140, pointerId: 1 });
    fireEvent.pointerMove(el, { clientX: 200, pointerId: 1 });
    expect(el).toHaveAttribute("aria-valuenow", "360");
  });
});
