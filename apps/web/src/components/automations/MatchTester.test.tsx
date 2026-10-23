import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { AutomationTestResult } from "@/lib/api/types";
import { json, renderWithApi, type Call } from "@/test/api";

import { MatchTester } from "./MatchTester";

function renderTester(
  result: Omit<AutomationTestResult, "flow_path"> & Partial<Pick<AutomationTestResult, "flow_path">>,
  beforeTest = vi.fn(async () => true),
  isFlow = false,
) {
  const bodies: unknown[] = [];
  const view = renderWithApi(
    <MatchTester wid="w1" automationId="au1" trigger="comment_keyword" beforeTest={beforeTest} isFlow={isFlow} />,
    {
      handlers: {
        "POST /v1/w/:wid/automations/:id/test": (call: Call) => {
          bodies.push(call.body);
          return json({ flow_path: [], ...result });
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

  it("tap first and the nudge: the opening with its button before the DM, the nudge after it", async () => {
    const user = userEvent.setup();
    renderWithApi(
      <MatchTester
        wid="w1"
        automationId="au1"
        trigger="comment_keyword"
        openingButton="Send me the link"
        beforeTest={vi.fn(async () => true)}
      />,
      {
        handlers: {
          "POST /v1/w/:wid/automations/:id/test": () =>
            json({
              matched: true,
              matched_keyword: "link",
              winner: { id: "au1", name: "Comment LINK" },
              rendered_public_reply: "Sent you a DM!",
              rendered_opening: "Hi there! Tap below and I'll send it over 👇",
              rendered_message: "Hi Priya! Here's the link.",
              rendered_nudge: "Enjoying this? Follow us for more.",
              flow_path: [],
            } satisfies AutomationTestResult),
        },
      },
    );
    await user.type(screen.getByRole("textbox", { name: "Comment" }), "LINK");
    await user.click(screen.getByRole("button", { name: "Test" }));

    const opening = await screen.findByTestId("test-opening");
    expect(opening).toHaveTextContent("Opening");
    expect(opening).toHaveTextContent("Hi there! Tap below and I'll send it over 👇");
    expect(within(opening).getByText("Send me the link")).toBeInTheDocument();
    const message = screen.getByTestId("test-message");
    expect(message).toHaveTextContent("DM after they tap or reply");
    expect(message).toHaveTextContent("Hi Priya! Here's the link.");
    const nudge = screen.getByTestId("test-nudge");
    expect(nudge).toHaveTextContent("Follow nudge · only if they don't follow you");
    expect(nudge).toHaveTextContent("Enjoying this? Follow us for more.");
    // Opening, then the message, then the nudge.
    expect(opening.compareDocumentPosition(message) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(message.compareDocumentPosition(nudge) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("without tap first the DM keeps its label and nothing else shows", async () => {
    const user = userEvent.setup();
    renderTester({
      matched: true,
      matched_keyword: "link",
      winner: { id: "au1", name: "Comment LINK" },
      rendered_message: "Hi Priya! Here's the link.",
    });
    await user.type(screen.getByRole("textbox", { name: "Comment" }), "LINK");
    await user.click(screen.getByRole("button", { name: "Test" }));
    expect(await screen.findByTestId("test-message")).toHaveTextContent(/^DMHi Priya/);
    expect(screen.queryByTestId("test-opening")).toBeNull();
    expect(screen.queryByTestId("test-nudge")).toBeNull();
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
  it("a flow: the walk shows one way through, and picking another way tests again", async () => {
    const user = userEvent.setup();
    const step = {
      buttons: [],
      quick_replies: [],
      exits: [],
    };
    const first = {
      matched: true,
      matched_keyword: "link",
      winner: { id: "au1", name: "Flow" },
      rendered_message: "Which one?",
      flow_path: [
        {
          ...step,
          step_id: "ask",
          kind: "send",
          title: "Message",
          text: "Which one?",
          quick_replies: ["Guide", "Prices"],
          exits: ["Taps Guide", "Taps Prices", "Types an answer"],
          picked: 0,
        },
        { ...step, step_id: "guide", kind: "send", title: "Message", text: "Here's the guide.", picked: null },
      ],
    } satisfies AutomationTestResult;
    const prices = {
      ...first,
      flow_path: [
        { ...first.flow_path[0], picked: 1 },
        { ...step, step_id: "prices", kind: "send", title: "Message", text: "Prices start at 499.", picked: null },
      ],
    } satisfies AutomationTestResult;
    const bodies: unknown[] = [];
    renderWithApi(
      <MatchTester wid="w1" automationId="au1" trigger="dm_keyword" beforeTest={vi.fn(async () => true)} isFlow />,
      {
        handlers: {
          "POST /v1/w/:wid/automations/:id/test": (call: Call) => {
            bodies.push(call.body);
            const picked = (call.body as { choices?: number[] }).choices?.[0];
            return json(picked === 1 ? prices : first);
          },
        },
      },
    );
    await user.click(screen.getByRole("radio", { name: "A DM" }));
    await user.type(screen.getByRole("textbox", { name: "Message" }), "link");
    await user.click(screen.getByRole("button", { name: "Test" }));

    const flow = await screen.findByTestId("test-flow");
    expect(within(flow).getByText("Here's the guide.")).toBeInTheDocument();
    // The first message is part of the walk, not shown twice.
    expect(screen.queryByTestId("test-message")).toBeNull();
    expect(bodies[0]).toMatchObject({ choices: [] });

    await user.selectOptions(within(flow).getByRole("combobox", { name: "Branch 1" }), "Taps Prices");
    expect(await within(await screen.findByTestId("test-flow")).findByText("Prices start at 499.")).toBeInTheDocument();
    expect(bodies[1]).toMatchObject({ choices: [1] });
  });
});
