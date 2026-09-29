import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

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
