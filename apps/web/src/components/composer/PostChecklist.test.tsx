import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { PostChecklist } from "./PostChecklist";

describe("PostChecklist (FR-PUB-10)", () => {
  it("lists failing items as links to their fix, then what passed", async () => {
    const user = userEvent.setup();
    const onFix = vi.fn();
    render(
      <PostChecklist
        failing={1}
        hrefFor={(field) => `#field-${field}`}
        onFix={onFix}
        items={[
          { key: "caption", ok: false, message: "The caption is 2,301 characters. Instagram allows 2,200.", field: "caption" },
          { key: "accounts", ok: true, message: "1 account can publish", field: null },
        ]}
      />,
    );
    expect(screen.getByTestId("checklist-summary")).toHaveTextContent("1 thing to fix");
    const [first, second] = within(screen.getByRole("list", { name: "Checks before scheduling" })).getAllByRole("listitem");
    const link = within(first).getByRole("link");
    expect(link).toHaveAccessibleName(/To fix: The caption is 2,301 characters/);
    expect(link).toHaveAttribute("href", "#field-caption");
    expect(second).toHaveTextContent("Passed: 1 account can publish");
    await user.click(link);
    expect(onFix).toHaveBeenCalledWith("caption");
  });

  it("says when everything passes", () => {
    render(<PostChecklist failing={0} hrefFor={() => "#"} onFix={vi.fn()} items={[{ key: "media", ok: true, message: "Reel", field: null }]} />);
    expect(screen.getByTestId("checklist-summary")).toHaveTextContent("Ready to schedule");
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
