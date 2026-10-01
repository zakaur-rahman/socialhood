import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { MODAL_MOTION_CLASSES, classes, expectModalScrim, expectReducedMotionCancels } from "@/test/overlays";

/** The danger override every confirming delete uses today (AutomationEditor, AutomationRow,
 * CommentRow, PostComposer, ListView, SchedulePage, SourcesCard, DisconnectDialog). */
const DANGER = "bg-danger-fill text-white hover:bg-danger-fill/90";

function Confirm({
  onConfirm = () => {},
  action = {},
  cancel = {},
}: {
  onConfirm?: () => void;
  action?: React.ComponentProps<typeof AlertDialogAction>;
  cancel?: React.ComponentProps<typeof AlertDialogCancel>;
}) {
  return (
    <AlertDialog>
      <AlertDialogTrigger>Disconnect</AlertDialogTrigger>
      <AlertDialogContent className="border-line bg-panel">
        <AlertDialogHeader>
          <AlertDialogTitle>Disconnect @sandbox.shop?</AlertDialogTitle>
          <AlertDialogDescription>You can connect it again later.</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel {...cancel}>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={onConfirm} {...action}>
            Confirm
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

async function open() {
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Disconnect" }));
  return { user, dialog: screen.getByRole("alertdialog") };
}

describe("AlertDialog (UI-012)", () => {
  it("a call-site danger fill replaces the variant's colour instead of losing to it (QA baseline)", async () => {
    render(<Confirm action={{ className: DANGER }} />);
    await open();
    const confirm = screen.getByRole("button", { name: "Confirm" });
    const list = classes(confirm);
    expect(list).toContain("bg-danger-fill");
    expect(list).toContain("hover:bg-danger-fill/90");
    // Merged through Button's cn: no second background colour, hover or text colour left to win.
    expect(list.filter((c) => /^bg-(primary|brand|destructive)/.test(c))).toEqual([]);
    expect(list.filter((c) => c.startsWith("hover:bg-"))).toEqual(["hover:bg-danger-fill/90"]);
    expect(list.filter((c) => /^text-(primary|white)/.test(c))).toEqual(["text-white"]);
    expect(confirm).toHaveAttribute("data-slot", "alert-dialog-action");
  });

  it("the variant goes to buttonVariants: the confirming button is exactly a Button", async () => {
    render(<Confirm action={{ variant: "destructive" }} />);
    await open();
    const confirm = screen.getByRole("button", { name: "Confirm" });
    expect(confirm).toHaveAttribute("data-variant", "destructive");
    expect(confirm.getAttribute("class")).toBe(cn(buttonVariants({ variant: "destructive", size: "default" })));
  });

  it("Cancel is an outline Button and takes call-site classes the same way", async () => {
    render(<Confirm cancel={{ className: "min-h-10 md:min-h-8" }} />);
    await open();
    const cancel = screen.getByRole("button", { name: "Cancel" });
    expect(cancel).toHaveAttribute("data-variant", "outline");
    expect(cancel).toHaveAttribute("data-slot", "alert-dialog-cancel");
    expect(cancel.getAttribute("class")).toBe(cn(buttonVariants({ variant: "outline", size: "default" }), "min-h-10 md:min-h-8"));
  });

  it("the action still confirms and closes; Esc returns focus to the trigger", async () => {
    const onConfirm = vi.fn();
    render(<Confirm onConfirm={onConfirm} />);
    const { user } = await open();
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    expect(onConfirm).toHaveBeenCalledOnce();
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Disconnect" }));
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Disconnect" })).toHaveFocus();
  });

  it("scrim, motion, shadow and scrolling match Dialog", async () => {
    render(<Confirm />);
    const { dialog } = await open();
    expectModalScrim(document.querySelector('[data-slot="alert-dialog-overlay"]')!);
    expect(dialog).toHaveClass(
      ...MODAL_MOTION_CLASSES,
      "data-open:zoom-in-95",
      "data-closed:zoom-out-95",
      "shadow-xl",
      "max-h-[calc(100dvh-2rem)]",
      "overflow-y-auto",
    );
    expect(dialog).not.toHaveClass("duration-100");
    expectReducedMotionCancels(dialog);
    // The call site's surface still applies.
    expect(dialog).toHaveClass("bg-panel");
    expect(dialog).not.toHaveClass("bg-popover");
  });

  it("title: 16 px semibold with normal leading", async () => {
    render(<Confirm />);
    await open();
    const title = screen.getByRole("heading", { name: "Disconnect @sandbox.shop?" });
    expect(title).toHaveClass("text-base", "font-semibold");
    expect(title).not.toHaveClass("font-medium");
    expect(title).not.toHaveClass("leading-none");
  });
});
