import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeAll, describe, expect, it } from "vitest";

import type { AutomationDefinition, TriggerName } from "@/lib/api/types";
import { toDefinition, type FieldErrors } from "@/lib/automations/definition";
import { account, automation, renderWithApi } from "@/test/api";

import { WhenStep } from "./WhenStep";

beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});

const ig = account({ id: "a1", username: "maple.bakery" });

function Harness({ trigger, errors = {} }: { trigger: TriggerName | null; errors?: FieldErrors }) {
  const [draft, setDraft] = useState<AutomationDefinition>(() =>
    toDefinition(automation({ social_account_id: "a1", trigger })),
  );
  return (
    <WhenStep
      draft={draft}
      change={(patch) => setDraft((current) => ({ ...current, ...patch }))}
      errors={errors}
      state="complete"
      accounts={[ig]}
      slug="maple"
    />
  );
}

describe("When's trigger", () => {
  it("is one row with Change once chosen, not the list", () => {
    renderWithApi(<Harness trigger="dm_keyword" />);
    expect(screen.queryByRole("radio")).toBeNull();
    expect(screen.getByRole("group", { name: "Trigger" })).toHaveTextContent("Instagram DM keyword");
    expect(screen.getByRole("button", { name: "Change trigger" })).toHaveAccessibleDescription(
      "Someone sends a DM with one of your keywords.",
    );
  });

  it("starts with the list open when there is no trigger, and closes on a choice, focus on Change", async () => {
    const user = userEvent.setup();
    renderWithApi(<Harness trigger={null} />);
    await user.click(screen.getByRole("radio", { name: "Instagram story reply" }));
    expect(screen.queryByRole("radio")).toBeNull();
    expect(screen.getByRole("group", { name: "Trigger" })).toHaveTextContent("Instagram story reply");
    expect(screen.getByRole("button", { name: "Change trigger" })).toHaveFocus();
  });

  it("works by keyboard: Change opens on the chosen trigger, arrows and Enter pick another", async () => {
    const user = userEvent.setup();
    renderWithApi(<Harness trigger="comment_keyword" />);
    screen.getByRole("button", { name: "Change trigger" }).focus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("radio", { name: "Instagram comment keyword" })).toHaveFocus();
    await user.keyboard("{ArrowDown}{Enter}");
    expect(screen.getByRole("group", { name: "Trigger" })).toHaveTextContent("Any Instagram comment");
    expect(screen.getByRole("button", { name: "Change trigger" })).toHaveFocus();
  });

  it("choosing the same trigger again closes the list and keeps it", async () => {
    const user = userEvent.setup();
    renderWithApi(<Harness trigger="dm_keyword" />);
    await user.click(screen.getByRole("button", { name: "Change trigger" }));
    await user.click(screen.getByRole("radio", { name: "Instagram DM keyword" }));
    expect(screen.getByRole("group", { name: "Trigger" })).toHaveTextContent("Instagram DM keyword");
  });

  it("stays open while the trigger has a problem", () => {
    renderWithApi(<Harness trigger="dm_keyword" errors={{ trigger: "Choose a trigger." }} />);
    expect(screen.getByRole("radio", { name: "Instagram DM keyword" })).toBeInTheDocument();
  });
});
