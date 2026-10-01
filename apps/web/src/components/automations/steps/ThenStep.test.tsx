import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Role } from "@/lib/api/types";
import { toDefinition } from "@/lib/automations/definition";
import { automation, renderWithApi, workspace } from "@/test/api";

import { ThenStep } from "./ThenStep";

const NOTE =
  "The AI answers from your knowledge. When the answer isn't there, it sends nothing and moves the conversation to Needs you.";

function renderAiReply(role: Role) {
  const draft = toDefinition(
    automation({ trigger: "dm_keyword", public_reply_texts: [], action: "ai_reply", ai_instructions: "Answer price questions." }),
  );
  renderWithApi(
    <ThenStep
      wid="w1"
      draft={draft}
      change={vi.fn()}
      errors={{}}
      state="complete"
      plan="pro"
      disclosure={null}
      mediaUrl={null}
      onMediaChange={vi.fn()}
    />,
    { ws: { ...workspace, role } },
  );
}

describe("ThenStep Reply with AI (UX-SCR-03)", () => {
  it.each(["owner", "admin"] as const)("says what happens without an answer, and links an %s to Knowledge", (role) => {
    renderAiReply(role);
    expect(screen.getByRole("textbox", { name: "Instructions" })).toHaveAccessibleDescription(`23 / 2,000 ${NOTE}`);
    expect(screen.getByRole("link", { name: "Open Knowledge" })).toHaveAttribute("href", "/w/maple/knowledge");
    expect(screen.queryByText(/Knowledge arrives/)).toBeNull();
  });

  it("an agent gets the sentence without the link", () => {
    renderAiReply("agent");
    expect(screen.getByText(NOTE)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Open Knowledge" })).toBeNull();
  });
});
