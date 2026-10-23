import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { toDefinition } from "@/lib/automations/definition";
import { automation, renderWithApi } from "@/test/api";

import { AdsStep } from "./AdsStep";

function setup(patch: Parameters<typeof automation>[0]) {
  const draft = toDefinition(automation({ trigger: "ad_click", keywords: [], ...patch }));
  const change = vi.fn();
  renderWithApi(<AdsStep draft={draft} change={change} errors={{}} state="incomplete" />);
  return change;
}

describe("AdsStep (GR-09)", () => {
  it("answers any ad without asking for ids", () => {
    setup({ post_scope: "all" });
    expect(screen.queryByLabelText("Ad id")).not.toBeInTheDocument();
  });

  it("adds a typed ad id", async () => {
    const user = userEvent.setup();
    const change = setup({ post_scope: "selected", ad_ids: ["1"] });
    await user.type(screen.getByLabelText("Ad id"), " 22 ");
    await user.click(screen.getByRole("button", { name: "Add" }));
    expect(change).toHaveBeenCalledWith({ ad_ids: ["1", "22"] });
  });

  it("does not add the same id twice", async () => {
    const user = userEvent.setup();
    const change = setup({ post_scope: "selected", ad_ids: ["1"] });
    await user.type(screen.getByLabelText("Ad id"), "1");
    await user.click(screen.getByRole("button", { name: "Add" }));
    expect(change).not.toHaveBeenCalled();
  });

  it("removes a chosen ad", async () => {
    const user = userEvent.setup();
    const change = setup({ post_scope: "selected", ad_ids: ["1", "2"] });
    await user.click(screen.getByRole("button", { name: "Remove ad 1" }));
    expect(change).toHaveBeenCalledWith({ ad_ids: ["2"] });
  });

  it("switches to chosen ads", async () => {
    const user = userEvent.setup();
    const change = setup({ post_scope: "all" });
    await user.click(screen.getByRole("radio", { name: "Chosen ads" }));
    expect(change).toHaveBeenCalledWith({ post_scope: "selected" });
  });
});
