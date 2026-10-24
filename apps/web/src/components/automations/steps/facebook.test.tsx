import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it, vi } from "vitest";

import { toDefinition } from "@/lib/automations/definition";
import { account, automation, renderWithApi } from "@/test/api";

import { ThenStep } from "./ThenStep";
import { WhenStep } from "./WhenStep";

beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});

const page = account({ id: "f1", platform: "facebook", username: "maplebakery", display_name: "Maple Bakery" });
const ig = account({ id: "a1", username: "maple.bakery" });

function renderWhen(accountId: string, accounts = [ig, page]) {
  const draft = toDefinition(automation({ social_account_id: accountId, trigger: "comment_keyword" }));
  return renderWithApi(
    <WhenStep draft={draft} change={vi.fn()} errors={{}} state="complete" accounts={accounts} slug="maple" />,
  );
}

describe("When, on a Facebook Page (GR-29)", () => {
  it("says Facebook in the trigger names and disables the story triggers, with the reason", () => {
    renderWhen("f1");
    expect(screen.getByRole("radio", { name: "Facebook comment keyword" })).toBeEnabled();
    expect(screen.getByRole("radio", { name: "Facebook DM keyword" })).toBeEnabled();
    expect(screen.getByRole("radio", { name: "Facebook entry link" })).toBeEnabled();
    expect(screen.getByRole("radio", { name: "Facebook ad click" })).toBeEnabled();
    expect(screen.getByRole("radio", { name: "Facebook story reply" })).toBeDisabled();
    expect(screen.getByRole("radio", { name: "Facebook story mention" })).toBeDisabled();
    expect(screen.getByRole("radio", { name: "Facebook comment keyword" })).toHaveAttribute("aria-checked", "true");
  });

  it("an Instagram account keeps every trigger", () => {
    renderWhen("a1");
    expect(screen.getByRole("radio", { name: "Instagram story reply" })).toBeEnabled();
    expect(screen.getByRole("radio", { name: "Instagram story mention" })).toBeEnabled();
  });

  it("explains a story trigger left over from an Instagram account", async () => {
    const draft = toDefinition(automation({ social_account_id: "f1", trigger: "story_reply" }));
    renderWithApi(<WhenStep draft={draft} change={vi.fn()} errors={{}} state="complete" accounts={[page]} slug="maple" />);
    expect(screen.getByText("Facebook Pages have no story replies. Choose another trigger.")).toBeInTheDocument();
  });

  it("the account field is just 'Account', and the empty link covers both networks", () => {
    renderWithApi(<WhenStep draft={toDefinition(automation())} change={vi.fn()} errors={{}} state="incomplete" accounts={[]} slug="maple" />);
    expect(screen.getByText(/Connect an Instagram account or a Facebook Page to use automations\./)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Connect an account" })).toHaveAttribute("href", "/w/maple/settings/connections");
  });
});

function renderThen(patch: Partial<ReturnType<typeof automation>>, platform: "facebook" | "instagram", change = vi.fn()) {
  const draft = toDefinition(automation({ trigger: "dm_keyword", public_reply_texts: [], action: "send_message", ...patch }));
  renderWithApi(
    <ThenStep
      wid="w1"
      draft={draft}
      change={change}
      errors={{}}
      state="incomplete"
      plan="pro"
      platform={platform}
      disclosure={null}
      mediaUrl={null}
      onMediaChange={vi.fn()}
    />,
  );
  return change;
}

describe("Then, on a Facebook Page (GR-29)", () => {
  it("counts the message in characters out of 2,000", () => {
    renderThen({ message_text: "m".repeat(1500), message_buttons: [] }, "facebook");
    expect(screen.getByText("1,500 / 2,000 characters")).toBeInTheDocument();
    expect(screen.queryByText(/allows 2,000 characters/)).toBeNull();
  });

  it("warns past the limit in Facebook's words", () => {
    renderThen({ message_text: "m".repeat(2100), message_buttons: [] }, "facebook");
    expect(
      screen.getByText("Facebook allows 2,000 characters in a message, counting the longest name. Shorten the message."),
    ).toBeInTheDocument();
  });

  it("an Instagram account still counts bytes out of 1,000", () => {
    renderThen({ message_text: "m".repeat(1500), message_buttons: [] }, "instagram");
    expect(screen.getByText("1,500 / 1,000 bytes")).toBeInTheDocument();
  });

  it("the follow message isn't offered, and one left on can be turned off", async () => {
    const user = userEvent.setup();
    const change = renderThen({ follow_nudge: true, follow_nudge_text: "Follow us" }, "facebook");
    expect(screen.getByTestId("follow-nudge-unavailable")).toHaveTextContent(
      "Messenger doesn't say whether someone follows your Page, so the follow message isn't available on Facebook.",
    );
    expect(screen.queryByLabelText(/Suggest following/)).toBeNull();
    await user.click(screen.getByRole("button", { name: "Turn it off" }));
    expect(change).toHaveBeenCalledWith({ follow_nudge: false });
  });

  it("with the follow message off there is nothing to turn off", () => {
    renderThen({ follow_nudge: false }, "facebook");
    expect(screen.getByTestId("follow-nudge-unavailable")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Turn it off" })).toBeNull();
  });

  it("Instagram keeps its follow message", () => {
    renderThen({ follow_nudge: false }, "instagram");
    expect(screen.queryByTestId("follow-nudge-unavailable")).toBeNull();
    expect(screen.getByLabelText(/Suggest following to people who don/)).toBeInTheDocument();
  });
});
