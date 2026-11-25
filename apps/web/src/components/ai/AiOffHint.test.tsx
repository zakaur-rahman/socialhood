import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { SocialAccount } from "@/lib/api/types";
import { account, conversation, json, renderWithApi, workspace, type Call } from "@/test/api";

import { AiOffHint } from "./AiOffHint";

const off = account({ ai_mode: "off" });
const offConversation = conversation({ ai: { effective_mode: "off", override: null, paused_until: null } });

function setup({ accounts = [off], ws = workspace, onPatch }: { accounts?: SocialAccount[]; ws?: typeof workspace; onPatch?: (call: Call) => void } = {}) {
  return renderWithApi(<AiOffHint conversation={offConversation} />, {
    ws,
    handlers: {
      "GET /v1/w/:wid/social-accounts": () => json({ items: accounts }),
      "PATCH /v1/w/:wid/social-accounts/:id": (call) => {
        onPatch?.(call);
        return json({ ...off, ai_mode: "suggest" });
      },
    },
  });
}

describe("AiOffHint (C-204)", () => {
  it("offers Suggest when the account's AI is off, and turns it on", async () => {
    const user = userEvent.setup();
    const patches: unknown[] = [];
    setup({ onPatch: (call) => patches.push(call.body) });
    expect(await screen.findByText("AI drafts are off for @maple.bakery.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Turn on Suggest" }));
    await waitFor(() => expect(patches).toEqual([{ ai_mode: "suggest" }]));
  });

  it("can be hidden, and stays hidden for that account", async () => {
    const user = userEvent.setup();
    const first = setup();
    await user.click(await screen.findByRole("button", { name: "Hide this" }));
    expect(screen.queryByTestId("ai-off-hint")).not.toBeInTheDocument();
    first.unmount();
    setup();
    await screen.findByText(/./, { selector: "body" }).catch(() => null);
    expect(screen.queryByTestId("ai-off-hint")).not.toBeInTheDocument();
  });

  it("isn't shown to agents, or when the account's AI is on", async () => {
    const agent = setup({ ws: { ...workspace, role: "agent" } });
    await waitFor(() => expect(screen.queryByTestId("ai-off-hint")).not.toBeInTheDocument());
    agent.unmount();
    setup({ accounts: [account({ ai_mode: "suggest" })] });
    await waitFor(() => expect(screen.queryByTestId("ai-off-hint")).not.toBeInTheDocument());
  });
});
