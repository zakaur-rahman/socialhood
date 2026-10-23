import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { FlowDefinition } from "@/lib/api/types";
import { toDefinition } from "@/lib/automations/definition";
import { automation } from "@/test/api";

import { PreviewPane } from "./PreviewPane";

function renderPreview(overrides: Parameters<typeof automation>[0] = {}, disclosure: string | null = null) {
  return render(
    <PreviewPane
      draft={toDefinition(automation(overrides))}
      accountUsername="maple.bakery"
      disclosure={disclosure}
      mediaUrl={null}
    />,
  );
}

describe("PreviewPane (UX-SCR-03 Preview)", () => {
  it("renders the comment, public reply and DM for the sample contact", () => {
    renderPreview({
      message_text: "Hi {first_name}! Here's the link.",
      public_reply_texts: ["Check your DMs, {first_name}!"],
    });
    const preview = screen.getByTestId("preview");
    expect(preview).toHaveTextContent("priya.styles LINK");
    expect(preview).toHaveTextContent("maple.bakery Check your DMs, Priya!");
    expect(screen.getByTestId("preview-message")).toHaveTextContent("Hi Priya! Here's the link.");
    expect(preview).toHaveTextContent("Shop now");
  });

  it("renders the fallback when the name is unknown", async () => {
    const user = userEvent.setup();
    renderPreview({ message_text: "Hi {first_name}! Or {first_name|friend}." });
    await user.click(screen.getByRole("radio", { name: "Name unknown" }));
    expect(screen.getByTestId("preview-message")).toHaveTextContent("Hi there! Or friend.");
    expect(screen.getByTestId("preview")).not.toHaveTextContent("{first_name");
  });

  it("adds the disclosure line and shows a DM trigger as a conversation", () => {
    renderPreview({ trigger: "dm_keyword", keywords: ["price"], message_text: "Prices are on the site." }, "Sent automatically");
    expect(screen.getByTestId("preview")).toHaveTextContent("PRICE");
    expect(screen.getByTestId("preview")).not.toHaveTextContent("Direct message");
    expect(screen.getByTestId("preview-message").textContent).toBe("Prices are on the site.\n\nSent automatically");
  });

  it("says the AI writes the reply for Reply with AI", () => {
    renderPreview({ action: "ai_reply" });
    expect(screen.getByTestId("preview")).toHaveTextContent("The AI writes a reply from your knowledge base.");
  });
});

/** The preview's parts, top to bottom. */
function sequence(): string[] {
  return Array.from(screen.getByTestId("preview").querySelectorAll<HTMLElement>("[data-testid]")).map(
    (element) => element.dataset.testid ?? "",
  );
}

const TAP_FIRST = {
  confirm_first: true,
  opening_text: "Hi {first_name|there}! Tap below and I'll send it over 👇",
  opening_button: "Send me the link",
} as const;

describe("PreviewPane with tap first and the follow nudge (FR-AUT-21, FR-AUT-22)", () => {
  it("tap first: the opening with its quick reply, their tap, then the message", () => {
    renderPreview({ ...TAP_FIRST, message_text: "Here you go, {first_name}!" }, "Sent automatically");
    expect(sequence()).toEqual(["preview-opening", "preview-quick-reply", "preview-tap", "preview-message"]);
    expect(screen.getByTestId("preview-opening").textContent).toBe(
      "Hi Priya! Tap below and I'll send it over 👇\n\nSent automatically",
    );
    expect(screen.getByTestId("preview-quick-reply")).toHaveTextContent("Send me the link");
    expect(screen.getByTestId("preview-tap")).toHaveTextContent("Send me the link");
    expect(screen.getByTestId("preview-message")).toHaveTextContent("Here you go, Priya!");
    expect(screen.getByTestId("preview")).toHaveTextContent("Shop now");
  });

  it("renders the opening's fallback when the name is unknown", async () => {
    const user = userEvent.setup();
    renderPreview(TAP_FIRST);
    await user.click(screen.getByRole("radio", { name: "Name unknown" }));
    expect(screen.getByTestId("preview-opening")).toHaveTextContent("Hi there! Tap below");
  });

  it("direct: no opening when tap first is off, or for Reply with AI", () => {
    const { unmount } = renderPreview({ ...TAP_FIRST, confirm_first: false });
    expect(sequence()).toEqual(["preview-message"]);
    unmount();
    renderPreview({ ...TAP_FIRST, action: "ai_reply", follow_nudge: true, follow_nudge_text: "Follow us" });
    expect(sequence()).toEqual([]);
    expect(screen.getByTestId("preview")).toHaveTextContent("The AI writes a reply");
  });

  it("the nudge comes last, labelled as shown to people who don't follow you", () => {
    renderPreview({ ...TAP_FIRST, follow_nudge: true, follow_nudge_text: "Enjoying this? Follow us for more." });
    expect(sequence()).toEqual(["preview-opening", "preview-quick-reply", "preview-tap", "preview-message", "preview-nudge"]);
    const nudge = screen.getByTestId("preview-nudge");
    expect(nudge).toHaveTextContent("Enjoying this? Follow us for more.");
    expect(nudge).toHaveTextContent("View profile");
    expect(nudge.parentElement).toHaveTextContent("Only to people who don't follow you");
  });

  it("DM triggers: the nudge follows the DM; no nudge when it is off", () => {
    const { unmount } = renderPreview({
      trigger: "dm_keyword",
      follow_nudge: true,
      follow_nudge_text: "Follow us, {first_name}!",
      confirm_first: true,
    });
    expect(sequence()).toEqual(["preview-message", "preview-nudge"]);
    expect(screen.getByTestId("preview-nudge")).toHaveTextContent("Follow us, Priya!");
    unmount();
    renderPreview({ trigger: "dm_keyword", follow_nudge: false, follow_nudge_text: "Follow us" });
    expect(sequence()).toEqual(["preview-message"]);
  });

  describe("a flow (GR-13)", () => {
    const flow: FlowDefinition = {
      schema_version: 1,
      start: "hello",
      steps: [
        {
          type: "send",
          id: "hello",
          text: "Hi {first_name|there}! Guide or prices?",
          quick_replies: [
            { title: "Guide", next: "guide" },
            { title: "Prices", next: "prices" },
          ],
        },
        { type: "send", id: "guide", text: "Here's the guide, {first_name}." },
        { type: "send", id: "prices", text: "Prices start at 499." },
      ],
    };

    function renderFlow() {
      return render(
        <PreviewPane
          draft={toDefinition(automation({ trigger: "dm_keyword", public_reply_texts: [] }))}
          accountUsername="maple.bakery"
          disclosure="Sent automatically"
          mediaUrl={null}
          flow={flow}
        />,
      );
    }

    it("walks one branch at a time, the first way to start with", () => {
      renderFlow();
      const preview = screen.getByTestId("preview");
      expect(preview).toHaveTextContent("Hi Priya! Guide or prices?");
      expect(preview).toHaveTextContent("Sent automatically");
      expect(preview).toHaveTextContent("Here's the guide, Priya.");
      expect(preview).not.toHaveTextContent("Prices start at 499.");
      // The flow replaces the message settings' own bubbles.
      expect(screen.queryByTestId("preview-message")).toBeNull();
    });

    it("the branch picker follows another way, and the sample name still applies", async () => {
      const user = userEvent.setup();
      renderFlow();
      const picker = screen.getByRole("combobox", { name: "Branch 1" });
      expect(within(picker).getAllByRole("option").map((option) => option.textContent)).toEqual([
        "Taps Guide",
        "Taps Prices",
        "Types an answer",
      ]);
      await user.selectOptions(picker, "Taps Prices");
      const preview = screen.getByTestId("preview");
      expect(preview).toHaveTextContent("Prices start at 499.");
      expect(preview).not.toHaveTextContent("Here's the guide");

      await user.click(screen.getByRole("radio", { name: "Name unknown" }));
      expect(preview).toHaveTextContent("Hi there! Guide or prices?");
    });
  });
});
