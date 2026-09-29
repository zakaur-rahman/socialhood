import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { AutomationTestResult } from "@/lib/api/types";
import { json, renderWithApi, type Call } from "@/test/api";

import { MatchTester } from "./MatchTester";

function renderTester(result: AutomationTestResult, beforeTest = vi.fn(async () => true)) {
  const bodies: unknown[] = [];
  const view = renderWithApi(
    <MatchTester wid="w1" automationId="au1" trigger="comment_keyword" beforeTest={beforeTest} />,
    {
      handlers: {
        "POST /v1/w/:wid/automations/:id/test": (call: Call) => {
          bodies.push(call.body);
          return json(result);
        },
      },
    },
  );
  return { ...view, bodies, beforeTest };
}

describe("MatchTester (UX-SCR-03 Test)", () => {
  it("match: the keyword, this automation wins, and the rendered messages", async () => {
    const user = userEvent.setup();
    const { bodies, beforeTest } = renderTester({
      matched: true,
      matched_keyword: "link",
      winner: { id: "au1", name: "Comment LINK" },
      rendered_message: "Hi Priya! Here's the link.",
      rendered_public_reply: "Sent you a DM!",
    });
    await user.type(screen.getByRole("textbox", { name: "Comment" }), "LINK please");
    await user.click(screen.getByRole("button", { name: "Test" }));

    const result = await screen.findByText("Match");
    const box = result.closest("[data-result]") as HTMLElement;
    expect(box).toHaveAttribute("data-result", "match");
    expect(box).toHaveTextContent(/Match\s*on “link”/);
    expect(within(box).getByText("This automation would run.")).toBeInTheDocument();
    expect(within(box).getByText("Hi Priya! Here's the link.")).toBeInTheDocument();
    expect(within(box).getByText("Sent you a DM!")).toBeInTheDocument();
    expect(beforeTest).toHaveBeenCalledOnce();
    expect(bodies).toEqual([{ kind: "comment", text: "LINK please", first_name: "Priya", username: "priya.styles" }]);
  });

  it("no match: says so, why, and which automation would run instead", async () => {
    const user = userEvent.setup();
    renderTester({
      matched: false,
      matched_keyword: null,
      winner: { id: "au9", name: "Price list DM" },
      reason: "None of the keywords appear in this text.",
      rendered_message: null,
      rendered_public_reply: null,
    });
    await user.click(screen.getByRole("radio", { name: "A DM" }));
    await user.type(screen.getByRole("textbox", { name: "Message" }), "what's the price");
    await user.click(screen.getByRole("button", { name: "Test" }));

    const box = (await screen.findByText("No match")).closest("[data-result]") as HTMLElement;
    expect(box).toHaveAttribute("data-result", "no-match");
    expect(within(box).getByText("Price list DM would run instead.")).toBeInTheDocument();
    expect(within(box).getByText("None of the keywords appear in this text.")).toBeInTheDocument();
  });

  it("does not test unsaved changes", async () => {
    const user = userEvent.setup();
    const { bodies } = renderTester(
      { matched: true, matched_keyword: "link", winner: null },
      vi.fn(async () => false),
    );
    await user.type(screen.getByRole("textbox", { name: "Comment" }), "LINK");
    await user.click(screen.getByRole("button", { name: "Test" }));
    expect(await screen.findByText(/aren't saved yet/)).toBeInTheDocument();
    expect(bodies).toEqual([]);
  });
});
