import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog";

// Opened through DialogTrigger, as the app's dialogs are: Radix returns focus to the trigger on
// close (with no trigger it has nowhere to return focus).
function Page() {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <button>Open</button>
      </DialogTrigger>
      <DialogContent>
        <DialogTitle>Templates</DialogTitle>
        <DialogDescription>Pick one</DialogDescription>
        <button>Use</button>
      </DialogContent>
    </Dialog>
  );
}

describe("a modal makes the page behind it inert (aria-hidden-focus)", () => {
  it("marks the other body children inert while open, and returns focus on Esc", async () => {
    const user = userEvent.setup();
    const live = document.body.appendChild(document.createElement("section"));
    live.setAttribute("aria-live", "polite");
    const { container } = render(<Page />);
    const opener = screen.getByRole("button", { name: "Open" });
    await user.click(opener);
    await screen.findByRole("dialog");
    expect(container).toHaveAttribute("inert");
    expect(live).not.toHaveAttribute("inert");
    await user.keyboard("{Escape}");
    expect(container).not.toHaveAttribute("inert");
    // Radix returns focus in a timeout after the content unmounts (and inert is already gone).
    await waitFor(() => expect(opener).toHaveFocus());
    live.remove();
  });
});
