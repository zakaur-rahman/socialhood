import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeAll, describe, expect, it } from "vitest";

import { compile, type EditorStep, type SendNode, type StepErrors } from "@/lib/automations/flow";
import { json, renderWithApi } from "@/test/api";

import { FlowEditor } from "./FlowEditor";
import type { FlowDraft } from "./use-flow-draft";

beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.setPointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});

const TAG = { id: "tag-vip", name: "VIP", color: 0, contact_count: 0 };
const REPLIES = [
  { id: "r1", title: "Shipping times", shortcut: "shipping", body: "We ship in 2 days.", created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-01T00:00:00Z" },
  { id: "r2", title: "Returns", shortcut: "returns", body: "Returns are free for 30 days.", created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-01T00:00:00Z" },
];
const FIELDS = [
  { id: "f1", key: "city", label: "City", type: "text", options: [], position: 0 },
  { id: "f2", key: "mail", label: "Work email", type: "email", options: [], position: 1 },
];

function send(id: string, text = "Hi", extra: Partial<SendNode> = {}): SendNode {
  return { kind: "send", id, text, image_asset_id: null, buttons: [], replies: [], typed: { mode: "none" }, ...extra };
}

/** The editor around real state: what the autosave hook gives it, without the network. */
function Harness({
  initial,
  cap = null,
  comment = false,
  activationErrors = {},
  onTree,
}: {
  initial: EditorStep[];
  cap?: number | null;
  comment?: boolean;
  activationErrors?: StepErrors;
  onTree?: (tree: EditorStep[]) => void;
}) {
  const [tree, setTree] = useState(initial);
  const compiled = compile(tree);
  const draft: FlowDraft = {
    phase: "ready",
    loadError: null,
    retryLoad: () => {},
    tree,
    definition: compiled.definition,
    ids: compiled.ids,
    stored: compiled.definition,
    update: (change) =>
      setTree((current) => {
        const next = change(current);
        onTree?.(next);
        return next;
      }),
    begin: () => {},
    flush: async () => true,
    status: "saved",
    error: null,
    saveErrors: {},
    saveGeneral: [],
    capMessage: null,
  };
  return (
    <FlowEditor
      wid="w1"
      automationId="au1"
      plan="pro"
      draft={draft}
      comment={comment}
      disclosure={null}
      activationErrors={activationErrors}
      clearActivationErrors={() => {}}
      key={String(cap)}
    />
  );
}

function renderEditor(props: Parameters<typeof Harness>[0]) {
  return renderWithApi(<Harness {...props} />, {
    handlers: {
      "GET /v1/w/:wid/tags": () => json({ items: [TAG] }),
      "GET /v1/w/:wid/contact-fields": () => json({ items: FIELDS }),
      "GET /v1/w/:wid/saved-replies": () => json({ items: REPLIES, max_items: 50 }),
      "GET /v1/billing/plans": () =>
        json({
          items: [
            {
              plan: "pro",
              price: null,
              trial_days: 7,
              available: true,
              entitlements: [{ key: "flow_steps", value: props.cap ?? null }],
            },
          ],
        }),
      "DELETE /v1/w/:wid/automations/:id/flow": () => json({}),
    },
  });
}

/** "1Message": a card's number and name, without its state badge. */
const titles = () =>
  screen
    .getAllByRole("heading", { level: 3 })
    .map((heading) => `${heading.children[0]?.textContent ?? ""}${heading.children[1]?.textContent ?? ""}`);

describe("the flow editor (GR-13)", () => {
  it("shows the steps as numbered cards, each named, with the move and delete controls", () => {
    renderEditor({ initial: [send("a", "First message"), { kind: "delay", id: "d", seconds: 600 }, send("b", "Last one")] });
    expect(titles()).toEqual(["1Message", "2Wait 10 minutes", "3Message"]);
    const cards = screen.getAllByRole("region");
    expect(cards).toHaveLength(3);
    for (const card of cards) expect(card).toHaveAccessibleName();
    expect(screen.getByRole("button", { name: "Move step 1 up" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Move step 3 down" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Reorder step 2" })).toHaveAccessibleDescription(/arrow keys/);
    expect(screen.getByTestId("flow-count")).toHaveTextContent("3");
  });

  it("adds a step of each kind the engine runs from the Add step menu", async () => {
    const user = userEvent.setup();
    renderEditor({ initial: [send("a", "Hello")] });
    await user.click(screen.getByRole("button", { name: "Add step" }));
    const kinds = screen.getAllByRole("menuitem").map((item) => item.querySelector("span")?.textContent);
    expect(kinds).toEqual(["Send", "Ask", "Branch", "Action", "Delay", "Split", "End"]);

    await user.click(screen.getByRole("menuitem", { name: /^Delay/ }));
    expect(titles()).toEqual(["1Message", "2Wait 10 minutes"]);
    expect(screen.getByTestId("flow-count")).toHaveTextContent("2");
  });

  it("stops a list at End: nothing can follow it", async () => {
    const user = userEvent.setup();
    renderEditor({ initial: [send("a", "Hello")] });
    await user.click(screen.getByRole("button", { name: "Add step" }));
    await user.click(screen.getByRole("menuitem", { name: /^End/ }));
    expect(screen.queryByRole("button", { name: "Add step" })).toBeNull();
    expect(screen.getByText(/The flow stops at End/)).toBeInTheDocument();
  });

  it("moves a step down and up with the buttons, and says so", async () => {
    const user = userEvent.setup();
    renderEditor({ initial: [send("a", "First"), send("b", "Second")] });
    expect(screen.getAllByRole("textbox", { name: "Message" }).map((box) => (box as HTMLTextAreaElement).value)).toEqual([
      "First",
      "Second",
    ]);
    await user.click(screen.getByRole("button", { name: "Move step 1 down" }));
    expect(screen.getAllByRole("textbox", { name: "Message" }).map((box) => (box as HTMLTextAreaElement).value)).toEqual([
      "Second",
      "First",
    ]);
    expect(screen.getByText("Moved step 1 down")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Move step 2 up" }));
    expect(screen.getAllByRole("textbox", { name: "Message" }).map((box) => (box as HTMLTextAreaElement).value)).toEqual([
      "First",
      "Second",
    ]);
  });

  it("moves a step with the arrow keys on its handle", async () => {
    const user = userEvent.setup();
    renderEditor({ initial: [send("a", "First"), send("b", "Second")] });
    const handle = screen.getByRole("button", { name: "Reorder step 2" });
    handle.focus();
    await user.keyboard("{ArrowUp}");
    expect(screen.getAllByRole("textbox", { name: "Message" }).map((box) => (box as HTMLTextAreaElement).value)).toEqual([
      "Second",
      "First",
    ]);
  });

  it("reorders by dragging the handle past another card", () => {
    const seen: string[][] = [];
    renderEditor({ initial: [send("a", "First"), send("b", "Second"), send("c", "Third")], onTree: (tree) => seen.push(tree.map((s) => s.id)) });
    const items = screen.getAllByRole("listitem");
    // jsdom has no layout: give the three cards 100 px each.
    items.forEach((item, index) => {
      item.getBoundingClientRect = () => ({ top: index * 100, height: 100, bottom: index * 100 + 100, left: 0, right: 300, width: 300, x: 0, y: index * 100, toJSON: () => ({}) });
    });
    const handle = screen.getByRole("button", { name: "Reorder step 3" });
    fireEvent.pointerDown(handle, { button: 0, pointerId: 1, clientY: 250 });
    fireEvent.pointerMove(handle, { pointerId: 1, clientY: 20 });
    expect(screen.getByTestId("drop-marker")).toBeInTheDocument();
    fireEvent.pointerUp(handle, { pointerId: 1, clientY: 20 });
    expect(seen.at(-1)).toEqual(["c", "a", "b"]);
    expect(screen.queryByTestId("drop-marker")).toBeNull();
  });

  it("a branch has its rules and Otherwise as indented groups with their own steps", async () => {
    const user = userEvent.setup();
    renderEditor({ initial: [send("a", "Hello")] });
    await user.click(screen.getByRole("button", { name: "Add step" }));
    await user.click(screen.getByRole("menuitem", { name: /^Branch/ }));
    const rule = screen.getByRole("group", { name: "Rule 1 of step 2" });
    expect(within(rule).getByRole("combobox", { name: "Rule 1 of step 2: check" })).toHaveValue("email_known");
    expect(screen.getByRole("group", { name: "Otherwise of step 2" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Add step to Rule 1 of step 2" }));
    await user.click(screen.getByRole("menuitem", { name: /^Send/ }));
    expect(titles()).toEqual(["1Message", "2Branch", "3Message"]);
    expect(within(screen.getByRole("group", { name: "Rule 1 of step 2" })).getAllByRole("heading", { level: 3 })).toHaveLength(1);

    await user.click(screen.getByRole("button", { name: "Add a rule" }));
    expect(screen.getByRole("group", { name: "Rule 2 of step 2" })).toBeInTheDocument();
    await user.selectOptions(screen.getByRole("combobox", { name: "Rule 2 of step 2: check" }), "tag");
    expect(screen.getByRole("combobox", { name: "Rule 2 of step 2: tag" })).toBeInTheDocument();
  });

  it("quick replies are branches: each has a title and its own steps, and link buttons step aside", async () => {
    const user = userEvent.setup();
    renderEditor({ initial: [send("pick", "Which one?")] });
    expect(screen.getByRole("button", { name: "Add a link button" })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "Add a quick reply" }));
    await user.type(screen.getByRole("textbox", { name: "Quick reply 1" }), "Guide");
    await user.click(screen.getByRole("button", { name: "Add a quick reply" }));
    await user.type(screen.getByRole("textbox", { name: "Quick reply 2" }), "Prices");

    expect(screen.queryByRole("button", { name: "Add a link button" })).toBeNull();
    expect(screen.getByText(/link buttons or quick replies, not both/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Add step to Quick reply 2 of step 1" }));
    await user.click(screen.getByRole("menuitem", { name: /^Send/ }));
    expect(within(screen.getByRole("group", { name: "Quick reply 2 of step 1" })).getAllByRole("heading", { level: 3 })).toHaveLength(1);

    // A typed answer can do nothing, copy an option, or have its own steps.
    const typed = screen.getByRole("combobox", { name: "If they type an answer instead" });
    expect(within(typed).getAllByRole("option").map((o) => o.textContent)).toEqual([
      "Do nothing",
      'Same as "Guide"',
      'Same as "Prices"',
      "Their own steps",
    ]);
    await user.selectOptions(typed, "own");
    expect(screen.getByRole("group", { name: "Typed answer of step 1" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Remove quick reply 1" }));
    expect(screen.getByRole("textbox", { name: "Quick reply 1" })).toHaveValue("Prices");
  });

  it("an Ask step saves to a field of the right type, and says when none is chosen", async () => {
    const user = userEvent.setup();
    renderEditor({
      initial: [{ kind: "ask", id: "q", text: "Where are you?", expect: "text", field_key: null, retry_text: "", tries: 2, consent: false, consent_text: "", confirm_text: "", skip: [] }],
    });
    const save = screen.getByRole("combobox", { name: "Save the answer to" });
    // Text answers go to a text field: the email field isn't offered.
    await waitFor(() => expect(within(save).getAllByRole("option").map((o) => o.textContent)).toEqual(["Choose a field", "City"]));
    await user.selectOptions(save, "city");
    expect(save).toHaveValue("city");
    await user.selectOptions(screen.getByRole("combobox", { name: "They answer with" }), "email");
    expect(screen.getByRole("combobox", { name: "Save the answer to" })).toHaveValue("");
    expect(within(screen.getByRole("combobox", { name: "Save the answer to" })).getAllByRole("option").map((o) => o.textContent)).toEqual([
      "The contact's email",
      "Work email",
    ]);
    // If it never fits: carry on, or end.
    await user.selectOptions(screen.getByRole("combobox", { name: "If the answer never fits" }), "end");
    expect(screen.queryByRole("group", { name: /doesn't fit/ })).toBeNull();
  });

  it("checks a step as you go: an emptied message is marked on its card and listed at the top", async () => {
    const user = userEvent.setup();
    renderEditor({ initial: [send("a", "Hello"), send("b", "World")] });
    expect(screen.queryByTestId("flow-attention")).toBeNull();
    const second = screen.getAllByRole("textbox", { name: "Message" })[1];
    await user.clear(second);

    const summary = await screen.findByTestId("flow-attention");
    expect(summary).toHaveTextContent("One step needs attention");
    expect(summary).toHaveTextContent("Write the message to send.");
    expect(second).toHaveAttribute("aria-invalid", "true");
    expect(second).toHaveAccessibleDescription(expect.stringContaining("Write the message to send."));
    const cards = screen.getAllByRole("region");
    expect(cards[1]).toHaveAttribute("data-state", "error");
    expect(cards[0]).toHaveAttribute("data-state", "complete");
  });

  it("marks a message that still says [price] and tells what to replace (C-105)", async () => {
    const user = userEvent.setup();
    renderEditor({ initial: [send("a", "Hello"), send("b", "The small one is [price]. Reply to order.")] });
    const second = screen.getAllByRole("textbox", { name: "Message" })[1];
    // Problems show once a step has been touched, as with every other check.
    expect(screen.queryByTestId("flow-attention")).toBeNull();
    await user.type(second, "!");
    const summary = await screen.findByTestId("flow-attention");
    expect(summary).toHaveTextContent("One step needs attention");
    expect(summary).toHaveTextContent("Replace [price] with your price.");
    expect(second).toHaveAttribute("aria-invalid", "true");
    expect(second).toHaveAccessibleDescription(expect.stringContaining("Replace [price] with your price."));
    expect(screen.getAllByRole("region")[0]).toHaveAttribute("data-state", "complete");
  });

  it("shows the API's placeholder error on the step it names", () => {
    renderEditor({
      initial: [send("a", "Your code is [code]")],
      activationErrors: { a: { text: "Replace [code] with your code." } },
    });
    expect(screen.getByTestId("flow-attention")).toHaveTextContent("Replace [code] with your code.");
  });

  it("jumps to the step an error names", async () => {
    const user = userEvent.setup();
    renderEditor({
      initial: [send("a", "Hello"), send("b", ""), send("c", "Bye")],
      activationErrors: { b: { text: "Write the message to send." }, c: { "buttons.0.url": "Use https." } },
    });
    const summary = screen.getByTestId("flow-attention");
    expect(summary).toHaveTextContent("2 steps need attention");
    await user.click(within(summary).getByRole("button", { name: "Go to step 2: Message" }));
    expect(screen.getAllByRole("textbox", { name: "Message" })[1]).toHaveFocus();
    // The error of a field in the step's own controls shows there too.
    expect(screen.getAllByRole("textbox", { name: "Message" })[1]).toHaveAttribute("aria-invalid", "true");
  });

  it("the plan's cap on steps disables Add step and says why", async () => {
    renderEditor({ initial: [send("a", "One"), send("b", "Two")], cap: 2 });
    await waitFor(() => expect(screen.getByTestId("flow-count")).toHaveTextContent("2 of 2"));
    expect(screen.getByRole("button", { name: "Add step" })).toBeDisabled();
    expect(screen.getByText(/Your plan includes 2 steps in a flow/)).toBeInTheDocument();
  });

  it("the only step of a flow can't be deleted; others can", async () => {
    const user = userEvent.setup();
    renderEditor({ initial: [send("a", "One"), send("b", "Two")] });
    await user.click(screen.getByRole("button", { name: "Delete step 2" }));
    expect(titles()).toEqual(["1Message"]);
    expect(screen.getByRole("button", { name: "Delete step 1" })).toBeDisabled();
  });

  it("collapses a card to one line and opens it again", async () => {
    const user = userEvent.setup();
    renderEditor({ initial: [send("a", "A long message to read")] });
    const toggle = screen.getByRole("button", { name: "Collapse step 1" });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    await user.click(toggle);
    expect(screen.queryByRole("textbox", { name: "Message" })).toBeNull();
    expect(screen.getByText("A long message to read")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Expand step 1" }));
    expect(screen.getByRole("textbox", { name: "Message" })).toHaveValue("A long message to read");
  });

  it("a comment's first message can't carry an image", () => {
    renderEditor({ initial: [send("a", "Thanks!"), send("b", "More")], comment: true });
    const [first, second] = screen.getAllByRole("region");
    expect(within(first).queryByRole("button", { name: "Add an image" })).toBeNull();
    expect(within(first).getByText(/text and link buttons/)).toBeInTheDocument();
    expect(within(second).getByRole("button", { name: "Add an image" })).toBeInTheDocument();
  });

  it("an Ask step offers the retry prompt, a confirmation and a marketing consent question", async () => {
    const user = userEvent.setup();
    renderEditor({
      initial: [{ kind: "ask", id: "q", text: "Your email?", expect: "email", field_key: null, retry_text: "", tries: 2, consent: false, consent_text: "", confirm_text: "", skip: [] }],
    });
    // The retry prompt shows the default copy for the kind of answer.
    expect(screen.getByPlaceholderText("That doesn't look like an email address. Could you send it again?")).toBeInTheDocument();
    await user.selectOptions(screen.getByRole("combobox", { name: "They answer with" }), "phone");
    expect(screen.getByPlaceholderText(/look like a phone number/)).toBeInTheDocument();
    await user.selectOptions(screen.getByRole("combobox", { name: "Tries" }), "3");
    expect(screen.getByRole("combobox", { name: "Tries" })).toHaveValue("3");

    expect(screen.queryByRole("textbox", { name: "Consent question" })).toBeNull();
    await user.click(screen.getByRole("switch", { name: "Ask for marketing consent" }));
    const consent = screen.getByRole("textbox", { name: "Consent question" });
    expect(consent).toHaveAttribute("placeholder", expect.stringContaining("Can we message you"));
    await user.type(consent, "Want offers?");
    expect(consent).toHaveValue("Want offers?");
    await user.type(screen.getByRole("textbox", { name: "Then confirm with (optional)" }), "Thanks!");
    expect(screen.getByRole("textbox", { name: "Then confirm with (optional)" })).toHaveValue("Thanks!");
  });

  it("asks before going back to one message", async () => {
    const user = userEvent.setup();
    const { calls } = renderEditor({ initial: [send("a", "One")] });
    await user.click(screen.getByRole("button", { name: "Back to one message" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByText("Go back to one message?")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Keep the steps" }));
    expect(calls.filter((call) => call.method === "DELETE")).toHaveLength(0);
  });

  describe("sending a saved reply (GR-21)", () => {
    it("swaps the message for a picker, hiding the text, image, buttons and quick replies", async () => {
      const user = userEvent.setup();
      const seen: EditorStep[][] = [];
      renderEditor({ initial: [send("a", "Hello", { buttons: [{ title: "Open", url: "https://example.com", profile: false }] })], onTree: (tree) => seen.push(tree) });
      const source = screen.getByRole("radiogroup", { name: "What to send" });
      expect(within(source).getByRole("radio", { name: "Write a message" })).toBeChecked();
      expect(screen.getByRole("textbox", { name: "Message" })).toBeInTheDocument();

      await user.click(within(source).getByRole("radio", { name: "Send a saved reply" }));
      expect(screen.queryByRole("textbox", { name: "Message" })).toBeNull();
      expect(screen.queryByRole("button", { name: "Add a quick reply" })).toBeNull();
      expect(screen.queryByRole("button", { name: /Add a button to your profile/ })).toBeNull();
      expect(await screen.findByRole("option", { name: "Returns" })).toBeInTheDocument();

      await user.selectOptions(screen.getByRole("combobox", { name: "Saved reply" }), "r2");
      expect(screen.getByText("Returns are free for 30 days.")).toBeInTheDocument();
      const last = seen.at(-1)?.[0] as SendNode;
      expect(last).toMatchObject({ saved: true, saved_reply_id: "r2", buttons: [], image_asset_id: null });
      expect(compile(seen.at(-1) as EditorStep[]).definition.steps[0]).toMatchObject({ text: "", saved_reply_id: "r2" });

      await user.click(within(source).getByRole("radio", { name: "Write a message" }));
      expect(screen.getByRole("textbox", { name: "Message" })).toBeInTheDocument();
    });

    it("asks for a reply to be chosen", async () => {
      const user = userEvent.setup();
      renderEditor({ initial: [send("a", "Hello")] });
      await user.click(screen.getByRole("radio", { name: "Send a saved reply" }));
      expect((await screen.findAllByText("Choose a saved reply.")).length).toBeGreaterThan(0);
    });

    it("can't be chosen while the message has quick replies", () => {
      renderEditor({ initial: [send("a", "Which?", { replies: [{ title: "A", steps: [] }] })] });
      expect(screen.getByRole("radio", { name: "Send a saved reply" })).toBeDisabled();
      expect(screen.getByText(/Remove the quick replies to use one/)).toBeInTheDocument();
    });

    it("is refused as the first step of a comment flow, and fine later", async () => {
      const user = userEvent.setup();
      renderEditor({ initial: [send("a", "Hi"), send("b", "Then")], comment: true });
      const radios = screen.getAllByRole("radio", { name: "Send a saved reply" });
      await user.click(radios[0]);
      await user.selectOptions((await screen.findAllByRole("combobox", { name: "Saved reply" }))[0], "r1");
      const refused = (await screen.findAllByText(/can't be a saved reply/)).length;
      await user.click(screen.getAllByRole("radio", { name: "Send a saved reply" })[1]);
      await user.selectOptions(screen.getAllByRole("combobox", { name: "Saved reply" })[1], "r2");
      // The second step adds no refusal of its own.
      expect(screen.getAllByText(/can't be a saved reply/)).toHaveLength(refused);
    });

    it("says when the chosen reply was deleted", async () => {
      renderEditor({ initial: [send("a", "", { saved: true, saved_reply_id: "gone" })] });
      expect(await screen.findByRole("option", { name: "Deleted saved reply" })).toBeInTheDocument();
    });
  });
});
