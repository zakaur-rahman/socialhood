import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { account } from "@/test/api";

import { AccountPicker } from "./AccountPicker";

describe("AccountPicker (UX-SCR-13 Accounts)", () => {
  it("toggles accounts as pressed chips", async () => {
    const user = userEvent.setup();
    const onToggle = vi.fn();
    render(
      <AccountPicker
        accounts={[account({ id: "a1", username: "maple.bakery", capabilities: ["publish"] }), account({ id: "a2", username: "maple.studio", capabilities: ["publish"] })]}
        loading={false}
        selected={["a2"]}
        onToggle={onToggle}
        slug="maple"
      />,
    );
    expect(screen.getByRole("button", { name: "@maple.studio" })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: "@maple.bakery" }));
    expect(onToggle).toHaveBeenCalledWith("a1");
  });

  it("disables an account without publishing permission, with the reason and Reconnect", () => {
    render(
      <AccountPicker accounts={[account({ id: "a1", username: "maple.bakery", capabilities: ["dm_send"] })]} loading={false} selected={[]} onToggle={vi.fn()} slug="maple" />,
    );
    const chip = screen.getByRole("button", { name: "@maple.bakery" });
    expect(chip).toBeDisabled();
    expect(chip).toHaveAccessibleDescription("Reconnect to allow publishing · Reconnect");
    expect(screen.getByRole("link", { name: "Reconnect" })).toHaveAttribute("href", "/w/maple/settings/connections");
  });

  it("points to Connections when no Instagram account is connected", () => {
    render(<AccountPicker accounts={[]} loading={false} selected={[]} onToggle={vi.fn()} slug="maple" />);
    expect(screen.getByRole("link", { name: "Connect Instagram" })).toHaveAttribute("href", "/w/maple/settings/connections");
  });

  it("shows placeholders while accounts load", () => {
    render(<AccountPicker accounts={[]} loading selected={[]} onToggle={vi.fn()} slug="maple" />);
    expect(screen.getByLabelText("Loading accounts")).toHaveAttribute("aria-busy", "true");
  });
});
