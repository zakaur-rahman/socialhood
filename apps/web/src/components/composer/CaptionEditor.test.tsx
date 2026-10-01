import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState, type ComponentProps } from "react";
import { describe, expect, it, vi } from "vitest";

import { billingState, json, planList, problem, renderWithApi, type Call } from "@/test/api";
import { hashtagGroup } from "@/test/composer-fixtures";

import { CaptionEditor, CaptionField } from "./CaptionEditor";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

/** A caption box that keeps its value, as the composer does. */
function Harness(props: Partial<ComponentProps<typeof CaptionField>> & { initial?: string; onValue?: (value: string) => void }) {
  const { initial = "", onValue, ...rest } = props;
  const [value, setValue] = useState(initial);
  return (
    <CaptionField
      id="composer-caption"
      label="Caption"
      value={value}
      onChange={(next) => {
        setValue(next);
        onValue?.(next);
      }}
      wid="w1"
      slug="maple"
      groups={[hashtagGroup()]}
      groupsLoading={false}
      {...rest}
    />
  );
}

const caption = () => screen.getByRole("textbox", { name: "Caption" }) as HTMLTextAreaElement;
const counts = () => screen.getByTestId("composer-caption-counts");

describe("CaptionField (UX-SCR-13, FR-PUB-10)", () => {
  it("counts characters, hashtags and mentions as you type", async () => {
    const user = userEvent.setup();
    renderWithApi(<Harness />);
    expect(counts()).toHaveTextContent("0 / 2,200 characters");
    await user.type(caption(), "Hi @priya #linen #summer 👋");
    expect(counts()).toHaveTextContent("26 / 2,200 characters");
    expect(counts()).toHaveTextContent("2 / 30 hashtags");
    expect(counts()).toHaveTextContent("1 / 20 mentions");
    expect(caption()).not.toHaveAttribute("aria-invalid");
  });

  it("over limits: marks the counter and the box", () => {
    const tags = Array.from({ length: 31 }, (_, index) => `#t${index}`).join(" ");
    renderWithApi(<Harness initial={`${"a".repeat(2200)} ${tags}`} />);
    expect(counts().querySelectorAll(".text-danger-fg")).toHaveLength(2);
    expect(within(counts()).getByText(/31 \/ 30 hashtags/)).toHaveClass("text-danger-fg");
    expect(caption()).toHaveAttribute("aria-invalid", "true");
  });

  it("inserts a hashtag group; the counter includes it", async () => {
    const user = userEvent.setup();
    renderWithApi(<Harness initial="New dresses" />);
    await user.click(screen.getByRole("button", { name: "Insert hashtag group" }));
    await user.click(await screen.findByRole("menuitem", { name: /Summer/ }));
    expect(caption().value).toBe("New dresses\n\n#summer #linen #ootd");
    expect(counts()).toHaveTextContent("3 / 30 hashtags");
  });

  it("says when there are no hashtag groups yet", async () => {
    const user = userEvent.setup();
    renderWithApi(<Harness groups={[]} />);
    await user.click(screen.getByRole("button", { name: "Insert hashtag group" }));
    expect(await screen.findByRole("menuitem", { name: "No hashtag groups yet" })).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByRole("menuitem", { name: "Manage hashtag groups" })).toHaveAttribute("href", "/w/maple/schedule");
  });

  it("suggests hashtags not already used; one or all can be added", async () => {
    const user = userEvent.setup();
    const calls: Call[] = [];
    renderWithApi(<Harness initial="Linen dresses #linen" />, {
      handlers: {
        "POST /v1/w/:wid/ai/hashtags": (call) => {
          calls.push(call);
          return json({ hashtags: ["summerstyle", "slowfashion", "linen"] });
        },
      },
    });
    await user.click(screen.getByRole("button", { name: "Suggest hashtags" }));
    const group = await screen.findByRole("group", { name: "Suggested hashtags" });
    expect(calls[0].body).toEqual({ caption: "Linen dresses #linen", count: 20, exclude: ["linen"] });
    expect(within(group).queryByRole("button", { name: "Add #linen" })).not.toBeInTheDocument();
    await user.click(within(group).getByRole("button", { name: "Add #summerstyle" }));
    expect(caption().value).toBe("Linen dresses #linen\n\n#summerstyle");
    await user.click(within(group).getByRole("button", { name: "Add all" }));
    expect(caption().value).toBe("Linen dresses #linen\n\n#summerstyle #slowfashion");
    expect(screen.queryByRole("group", { name: "Suggested hashtags" })).not.toBeInTheDocument();
  });

  it("asks for a caption before suggesting hashtags", async () => {
    const user = userEvent.setup();
    renderWithApi(<Harness />);
    await user.click(screen.getByRole("button", { name: "Suggest hashtags" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Write a caption first, then suggest hashtags.");
  });

  it("writes a caption with AI from a brief", async () => {
    const user = userEvent.setup();
    const calls: Call[] = [];
    renderWithApi(<Harness />, {
      handlers: {
        "POST /v1/w/:wid/ai/caption": (call) => {
          calls.push(call);
          return json({ caption: "Linen season is here ☀️ #linen" });
        },
      },
    });
    await user.click(screen.getByRole("button", { name: "Write with AI" }));
    await user.type(screen.getByRole("textbox", { name: "What's the post about?" }), "linen dresses");
    expect(screen.queryByRole("button", { name: "Improve my caption" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Write caption" }));
    await waitFor(() => expect(caption().value).toBe("Linen season is here ☀️ #linen"));
    expect(calls[0].body).toEqual({ mode: "write", brief: "linen dresses" });
    expect(toast.success).toHaveBeenCalledWith(
      "Caption written. Change anything you like.",
      expect.objectContaining({ duration: 10_000, action: expect.objectContaining({ label: "Undo" }) }),
    );
  });

  it.each([
    ["write", "Write caption", "Caption written. Change anything you like."],
    ["improve", "Improve my caption", "Caption improved. Change anything you like."],
  ])("Undo on the toast puts back the caption %s replaced, exactly", async (_mode, button, message) => {
    const user = userEvent.setup();
    const before = "  Linen dresses,\n\nback in stock 🌿  #linen #summer\n";
    const onValue = vi.fn();
    toast.success.mockClear();
    renderWithApi(<Harness initial={before} onValue={onValue} />, {
      handlers: { "POST /v1/w/:wid/ai/caption": () => json({ caption: "Linen season is here ☀️ #linen" }) },
    });
    await user.click(screen.getByRole("button", { name: "Write with AI" }));
    await user.type(screen.getByRole("textbox", { name: "What's the post about?" }), "linen dresses");
    await user.click(screen.getByRole("button", { name: button }));
    await waitFor(() => expect(caption().value).toBe("Linen season is here ☀️ #linen"));

    const [text, options] = toast.success.mock.calls.at(-1) as [string, { action: { label: string; onClick: () => void } }];
    expect(text).toBe(message);
    expect(options.action.label).toBe("Undo");
    act(() => options.action.onClick());
    expect(caption().value).toBe(before);
    expect(onValue).toHaveBeenLastCalledWith(before);
  });

  it("improves the caption, and shows the credit limit when AI credits are used up", async () => {
    const user = userEvent.setup();
    let count = 0;
    renderWithApi(<Harness initial="new dresses" />, {
      handlers: {
        "POST /v1/w/:wid/ai/caption": () => {
          count += 1;
          return count === 1
            ? problem(402, "quota_exceeded", "You've used all 500 AI credits for this month. They reset on 1 Oct.")
            : json({ caption: "New dresses, fresh for autumn." });
        },
      },
      upgradeDialog: true,
    });
    await user.click(screen.getByRole("button", { name: "Write with AI" }));
    await user.click(screen.getByRole("button", { name: "Improve my caption" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("You've used all 500 AI credits for this month. They reset on 1 Oct.");
    // One message: the inline one, beside the brief; the dialog doesn't open by itself.
    expect(screen.queryByTestId("upgrade-dialog")).not.toBeInTheDocument(); // the popover is a dialog too
    expect(caption().value).toBe("new dresses");
    await user.click(screen.getByRole("button", { name: "Improve my caption" }));
    await waitFor(() => expect(caption().value).toBe("New dresses, fresh for autumn."));
  });

  it("Upgrade beside the credit limit opens the upgrade dialog", async () => {
    const user = userEvent.setup();
    renderWithApi(<Harness initial="new dresses" />, {
      handlers: {
        "POST /v1/w/:wid/ai/caption": () =>
          problem(402, "quota_exceeded", "You've used all 500 AI credits for this month.", {
            entitlement: "ai_credits_monthly",
            limit: 500,
          }),
        "GET /v1/w/:wid/billing": () => json(billingState({ plan: "free", status: "free" })),
        "GET /v1/billing/plans": () => json(planList()),
      },
      upgradeDialog: true,
    });
    await user.click(screen.getByRole("button", { name: "Write with AI" }));
    await user.click(screen.getByRole("button", { name: "Improve my caption" }));
    const alert = await screen.findByRole("alert");
    expect(screen.queryByTestId("upgrade-dialog")).not.toBeInTheDocument(); // the popover is a dialog too
    await user.click(within(alert).getByRole("button", { name: "Upgrade" }));
    expect(await screen.findByRole("dialog", { name: "AI credits used up" })).toHaveTextContent(
      "You've used all 500 AI credits for this month.",
    );
  });

  it("Suggest hashtags over the credit limit: the note under the box, with Upgrade, and no dialog", async () => {
    const user = userEvent.setup();
    renderWithApi(<Harness initial="new linen dresses" />, {
      handlers: {
        "POST /v1/w/:wid/ai/hashtags": () =>
          problem(402, "quota_exceeded", "You've used all 500 AI credits for this month.", {
            entitlement: "ai_credits_monthly",
            limit: 500,
          }),
      },
      upgradeDialog: true,
    });
    await user.click(screen.getByRole("button", { name: "Suggest hashtags" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("You've used all 500 AI credits for this month.");
    expect(within(alert).getByRole("button", { name: "Upgrade" })).toBeInTheDocument();
    expect(screen.queryByTestId("upgrade-dialog")).not.toBeInTheDocument(); // the popover is a dialog too
    expect(toast.error).not.toHaveBeenCalled();
  });

  it("other failures get no Upgrade", async () => {
    const user = userEvent.setup();
    renderWithApi(<Harness initial="new linen dresses" />, {
      handlers: { "POST /v1/w/:wid/ai/hashtags": () => problem(409, "conflict", "Try again in a moment.") },
    });
    await user.click(screen.getByRole("button", { name: "Suggest hashtags" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Try again in a moment.");
    expect(within(alert).queryByRole("button", { name: "Upgrade" })).not.toBeInTheDocument();
  });
});

describe("CaptionEditor per-account captions", () => {
  it("shows the switch with two accounts and a box per account when on", async () => {
    const user = userEvent.setup();
    const onPerAccountChange = vi.fn();
    const onAccountCaptionChange = vi.fn();
    const props = {
      wid: "w1",
      slug: "maple",
      groups: [],
      groupsLoading: false,
      caption: "Hello",
      onCaptionChange: vi.fn(),
      canPerAccount: true,
      onPerAccountChange,
      accountCaptions: [
        { accountId: "a1", label: "@maple.bakery", value: "Hello" },
        { accountId: "a2", label: "@maple.studio", value: "Hi studio" },
      ],
      onAccountCaptionChange,
    };
    const { rerender } = renderWithApi(<CaptionEditor {...props} perAccount={false} />);
    expect(screen.getByRole("textbox", { name: "Caption" })).toHaveValue("Hello");
    await user.click(screen.getByRole("switch", { name: "Different caption per account" }));
    expect(onPerAccountChange).toHaveBeenCalledWith(true);

    rerender(<CaptionEditor {...props} perAccount />);
    expect(screen.queryByRole("textbox", { name: "Caption" })).not.toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Caption for @maple.studio" })).toHaveValue("Hi studio");
    await user.type(screen.getByRole("textbox", { name: "Caption for @maple.studio" }), "!");
    expect(onAccountCaptionChange).toHaveBeenCalledWith(1, "Hi studio!");
  });

  it("hides the switch with one account", () => {
    renderWithApi(
      <CaptionEditor
        wid="w1"
        slug="maple"
        groups={[]}
        groupsLoading={false}
        caption=""
        onCaptionChange={vi.fn()}
        perAccount={false}
        canPerAccount={false}
        onPerAccountChange={vi.fn()}
        accountCaptions={[]}
        onAccountCaptionChange={vi.fn()}
      />,
    );
    expect(screen.queryByRole("switch")).not.toBeInTheDocument();
  });
});
