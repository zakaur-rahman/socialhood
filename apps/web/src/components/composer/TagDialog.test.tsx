import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { assetInfo } from "@/test/composer-fixtures";

import { fractionAt, TagDialog, type TagPoint } from "./TagDialog";

function renderTags(tags: TagPoint[] = []) {
  const onSave = vi.fn();
  const onOpenChange = vi.fn();
  render(<TagDialog open onOpenChange={onOpenChange} asset={assetInfo({ id: "as1" })} label="Photo 1" tags={tags} onSave={onSave} />);
  const stage = screen.getByTestId("tag-stage");
  stage.getBoundingClientRect = () => ({ left: 10, top: 20, width: 200, height: 100, right: 210, bottom: 120, x: 10, y: 20, toJSON: () => ({}) });
  return { onSave, onOpenChange, stage };
}

describe("fractionAt (FR-PUB-07)", () => {
  it("gives fractions of the photo from its top left, kept inside it", () => {
    const rect = { left: 10, top: 20, width: 200, height: 100 };
    expect(fractionAt(rect, 60, 45)).toEqual({ x: 0.25, y: 0.25 });
    expect(fractionAt(rect, -50, 500)).toEqual({ x: 0, y: 1 });
    expect(fractionAt({ left: 0, top: 0, width: 0, height: 0 }, 5, 5)).toEqual({ x: 0.5, y: 0.5 });
  });
});

describe("TagDialog", () => {
  it("places a tag where the photo is tapped and saves it with the username", async () => {
    const user = userEvent.setup();
    const { onSave, stage } = renderTags();
    fireEvent.pointerDown(stage, { pointerId: 1, clientX: 60, clientY: 45 });

    const marker = screen.getByTestId("tag-marker-0");
    expect(marker).toHaveAttribute("data-x", "0.250");
    expect(marker).toHaveAttribute("data-y", "0.250");
    await user.type(screen.getByRole("textbox", { name: "Username for tag 1" }), "@Bread.Fan");
    await user.click(screen.getByRole("button", { name: "Save tags" }));
    expect(onSave).toHaveBeenCalledWith([{ username: "bread.fan", x: 0.25, y: 0.25 }]);
  });

  it("will not save a tag without a valid username", async () => {
    const user = userEvent.setup();
    const { onSave, stage } = renderTags();
    fireEvent.pointerDown(stage, { pointerId: 1, clientX: 60, clientY: 45 });
    expect(screen.getByRole("button", { name: "Save tags" })).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent("Every tag needs an Instagram username");
    await user.type(screen.getByRole("textbox", { name: "Username for tag 1" }), "bad name");
    expect(screen.getByRole("button", { name: "Save tags" })).toBeDisabled();
    expect(onSave).not.toHaveBeenCalled();
  });

  it("moves a tag by dragging its marker and with the arrow keys", () => {
    const { stage } = renderTags([{ username: "bread.fan", x: 0.5, y: 0.5 }]);
    const marker = screen.getByTestId("tag-marker-0");
    fireEvent.pointerDown(marker, { pointerId: 2, clientX: 110, clientY: 70 });
    fireEvent.pointerMove(marker, { pointerId: 2, clientX: 160, clientY: 95 });
    fireEvent.pointerUp(marker, { pointerId: 2 });
    expect(marker).toHaveAttribute("data-x", "0.750");
    expect(marker).toHaveAttribute("data-y", "0.750");
    expect(stage).toBeInTheDocument();

    fireEvent.keyDown(marker, { key: "ArrowLeft" });
    fireEvent.keyDown(marker, { key: "ArrowUp" });
    expect(marker).toHaveAttribute("data-x", "0.730");
    expect(marker).toHaveAttribute("data-y", "0.730");
  });

  it("keeps a dragged tag inside the photo", () => {
    renderTags([{ username: "bread.fan", x: 0.5, y: 0.5 }]);
    const marker = screen.getByTestId("tag-marker-0");
    fireEvent.pointerDown(marker, { pointerId: 3, clientX: 110, clientY: 70 });
    fireEvent.pointerMove(marker, { pointerId: 3, clientX: 900, clientY: -40 });
    expect(marker).toHaveAttribute("data-x", "1.000");
    expect(marker).toHaveAttribute("data-y", "0.000");
  });

  it("removes a tag", async () => {
    const user = userEvent.setup();
    const { onSave } = renderTags([
      { username: "one", x: 0.1, y: 0.1 },
      { username: "two", x: 0.9, y: 0.9 },
    ]);
    await user.click(screen.getByRole("button", { name: "Remove tag 1" }));
    expect(screen.queryByTestId("tag-marker-1")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Save tags" }));
    expect(onSave).toHaveBeenCalledWith([{ username: "two", x: 0.9, y: 0.9 }]);
  });

  it("stops at 20 tags", () => {
    const tags = Array.from({ length: 20 }, (_, i) => ({ username: `u${i}`, x: 0.5, y: 0.5 }));
    const { stage } = renderTags(tags);
    fireEvent.pointerDown(stage, { pointerId: 1, clientX: 60, clientY: 45 });
    expect(screen.queryByTestId("tag-marker-20")).toBeNull();
  });
});
