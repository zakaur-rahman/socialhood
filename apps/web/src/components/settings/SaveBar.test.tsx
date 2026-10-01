import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Link from "next/link";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LEAVE_WARNING, SaveBar } from "./SaveBar";

/** An in-app link as the sidebar has; jsdom can't navigate, so reaching the click is "leaving". */
function InboxLink({ onNavigate }: { onNavigate: () => void }) {
  return (
    <Link
      href="/w/maple/inbox"
      onClick={(event) => {
        event.preventDefault();
        onNavigate();
      }}
    >
      Inbox
    </Link>
  );
}

function renderBar(props: Partial<Parameters<typeof SaveBar>[0]> = {}) {
  const onReset = vi.fn();
  const onSave = vi.fn();
  const navigated = vi.fn();
  const view = render(
    <>
      <InboxLink onNavigate={navigated} />
      <SaveBar dirty={false} saving={false} onReset={onReset} onSave={onSave} {...props} />
    </>,
  );
  const bar = () => screen.getByRole("region", { name: "Save changes" });
  const rerender = (next: Partial<Parameters<typeof SaveBar>[0]>) =>
    view.rerender(
      <>
        <InboxLink onNavigate={navigated} />
        <SaveBar dirty={false} saving={false} onReset={onReset} onSave={onSave} {...props} {...next} />
      </>,
    );
  return { bar, onReset, onSave, navigated, rerender };
}

function unload(): Event {
  const event = new Event("beforeunload", { cancelable: true });
  window.dispatchEvent(event);
  return event;
}

afterEach(() => vi.restoreAllMocks());

describe("SaveBar (C-066)", () => {
  it("clean: all changes saved, no buttons, leaving is free", async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, "confirm");
    const { bar, navigated } = renderBar();
    expect(within(bar()).getByRole("status")).toHaveTextContent("All changes saved");
    expect(within(bar()).queryByRole("button")).toBeNull();
    expect(unload().defaultPrevented).toBe(false);
    await user.click(screen.getByRole("link", { name: "Inbox" }));
    expect(confirm).not.toHaveBeenCalled();
    expect(navigated).toHaveBeenCalledOnce();
  });

  it("dirty: unsaved changes with Reset and Save", async () => {
    const user = userEvent.setup();
    const { bar, onReset, onSave } = renderBar({ dirty: true });
    expect(within(bar()).getByRole("status")).toHaveTextContent("Unsaved changes");
    await user.click(within(bar()).getByRole("button", { name: "Reset" }));
    expect(onReset).toHaveBeenCalledOnce();
    await user.click(within(bar()).getByRole("button", { name: "Save" }));
    expect(onSave).toHaveBeenCalledOnce();
  });

  it("saving: a spinner, and neither button can be pressed again", () => {
    const { bar } = renderBar({ dirty: true, saving: true });
    expect(within(bar()).getByRole("status")).toHaveTextContent("Saving…");
    expect(within(bar()).getByRole("button", { name: "Save" })).toBeDisabled();
    expect(within(bar()).getByRole("button", { name: "Reset" })).toBeDisabled();
  });

  it("a failed save shows its error in place and keeps the changes", () => {
    const { bar } = renderBar({ dirty: true, error: "Couldn't save. Try again." });
    expect(within(bar()).getByRole("alert")).toHaveTextContent("Couldn't save. Try again.");
    expect(within(bar()).getByRole("status")).toHaveTextContent("Unsaved changes");
    expect(within(bar()).getByRole("button", { name: "Save" })).toBeEnabled();
  });

  it("warns before leaving with unsaved changes: reload/close and in-app links", async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const { navigated, rerender } = renderBar({ dirty: true });

    expect(unload().defaultPrevented).toBe(true);

    await user.click(screen.getByRole("link", { name: "Inbox" }));
    expect(confirm).toHaveBeenCalledWith(LEAVE_WARNING);
    expect(navigated).not.toHaveBeenCalled(); // stayed

    confirm.mockReturnValue(true);
    await user.click(screen.getByRole("link", { name: "Inbox" }));
    expect(navigated).toHaveBeenCalledOnce(); // chose to leave

    // Once saved, nothing asks.
    confirm.mockClear();
    rerender({ dirty: false });
    expect(unload().defaultPrevented).toBe(false);
    await user.click(screen.getByRole("link", { name: "Inbox" }));
    expect(confirm).not.toHaveBeenCalled();
    expect(navigated).toHaveBeenCalledTimes(2);
  });

  it("floats opaque, without blur; sticks, but not on short viewports (UI-ISS-014, UI-ISS-031)", () => {
    const { bar } = renderBar();
    expect(bar()).toHaveClass("sticky", "bottom-0", "[@media(max-height:500px)]:static");
    const surface = bar().firstElementChild;
    expect(surface).toHaveClass("bg-panel", "shadow-xl");
    expect(surface?.className).not.toMatch(/backdrop-blur|bg-panel\/|shadow-2xl/);
  });

  it("status only (switches that save as they change): saving, saved, or the error", () => {
    const { bar, rerender } = renderBar({ onReset: undefined, onSave: undefined, saving: true });
    expect(within(bar()).getByRole("status")).toHaveTextContent("Saving…");
    expect(within(bar()).queryByRole("button")).toBeNull();
    rerender({ onReset: undefined, onSave: undefined, saving: false, error: "Something went wrong." });
    expect(within(bar()).getByRole("status")).toHaveTextContent("Last change not saved");
    expect(within(bar()).getByRole("alert")).toHaveTextContent("Something went wrong.");
  });
});
