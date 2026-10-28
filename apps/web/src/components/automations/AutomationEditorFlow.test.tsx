import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import type { Automation } from "@/lib/api/types";
import { account, automation, json, renderWithApi, type Call } from "@/test/api";

import { AutomationEditor } from "./AutomationEditor";

/**
 * GR-13: the Then step of the editor as a flow. An automation on its message settings opens as one
 * message and turns into a flow when a step is added; a saved flow edits its steps, autosaves the
 * whole flow, and shows the API's activation errors on the steps they name.
 */
const nav = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: nav.push, replace: nav.replace }),
  useSearchParams: () => new URLSearchParams(""),
  useParams: () => ({ slug: "maple", id: "au1" }),
  usePathname: () => "/w/maple/automations/au1",
}));

beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});

beforeEach(() => {
  nav.push.mockReset();
  nav.replace.mockReset();
});

const SAVED_FLOW = {
  automation_id: "au1",
  version: 1,
  source: "flow",
  missing_for_activation: [],
  definition: {
    schema_version: 1,
    start: "hello",
    steps: [
      {
        type: "send",
        id: "hello",
        text: "Which one?",
        quick_replies: [
          { title: "A", next: "a" },
          { title: "B", next: "b" },
        ],
      },
      { type: "send", id: "a", text: "Option A" },
      { type: "send", id: "b", text: "Option B" },
    ],
  },
};

type FlowBody = { start: string; steps: { id: string; type: string; text?: string }[] };

function validation(errors: { field: string; message: string }[]): Response {
  return new Response(
    JSON.stringify({ type: "about:blank", title: "validation_error", status: 422, code: "validation_error", errors }),
    { status: 422, headers: { "Content-Type": "application/problem+json" } },
  );
}

/**
 * The editor against a fake API that keeps one automation and its flow: the flow compiled from the
 * settings (``compiled``) until a flow is saved, then the last one saved.
 */
function renderEditor(
  initial: Automation,
  { activate, compiled, flowLoaded }: { activate?: () => Response; compiled?: FlowBody; flowLoaded?: Promise<void> } = {},
) {
  let current = initial;
  let stored: FlowBody = SAVED_FLOW.definition as FlowBody;
  const saved: FlowBody[] = [];
  const view = renderWithApi(<AutomationEditor id={initial.id} />, {
    handlers: {
      "GET /v1/w/:wid": () =>
        json({
          id: "w1",
          name: "Maple Bakery",
          slug: "maple",
          plan: "pro",
          role: "owner",
          timezone: "Asia/Kolkata",
          reply_language: "auto",
          status: "active",
          created_at: "2026-09-01T00:00:00Z",
          automation_disclosure: null,
        }),
      "GET /v1/w/:wid/social-accounts": () => json({ items: [account({ id: "a1", username: "maple.bakery" })] }),
      "GET /v1/w/:wid/posts": () => json({ items: [], next_cursor: null }),
      "GET /v1/w/:wid/automations/:id": () => json(current),
      "PUT /v1/w/:wid/automations/:id": (call: Call) => {
        current = { ...current, ...(call.body as Partial<Automation>) };
        return json(current);
      },
      "POST /v1/w/:wid/automations/:id/activate": () =>
        activate ? activate() : json((current = { ...current, status: "active", display_status: "active" })),
      "GET /v1/w/:wid/automations/:id/flow": async () => {
        await flowLoaded;
        return current.flow_source === "flow"
          ? json({ ...SAVED_FLOW, definition: stored })
          : json({ ...SAVED_FLOW, version: 0, source: "legacy", definition: compiled ?? stored });
      },
      "PUT /v1/w/:wid/automations/:id/flow": (call: Call) => {
        stored = call.body as FlowBody;
        saved.push(stored);
        current = { ...current, flow_source: "flow" };
        return json({ ...SAVED_FLOW, definition: stored });
      },
      "GET /v1/w/:wid/tags": () => json({ items: [] }),
      "GET /v1/w/:wid/contact-fields": () => json({ items: [] }),
      "GET /v1/billing/plans": () => json({ items: [] }),
    },
  });
  return { ...view, saved };
}

const saveStatus = () => screen.getByTestId("save-status");
const step = (id: string) => document.getElementById(`step-${id}`) as HTMLElement;
const names = () => screen.getAllByRole("heading", { level: 3 }).map((heading) => heading.children[1]?.textContent);

describe("AutomationEditor flow (GR-13)", () => {
  it("opens an automation on its message settings as one message; adding a step turns it into a flow", async () => {
    const user = userEvent.setup();
    const { saved } = renderEditor(
      automation({ trigger: "dm_keyword", public_reply_texts: [], message_text: "Here is the link.", message_buttons: [] }),
      { compiled: { start: "message", steps: [{ type: "send", id: "message", text: "Here is the link." }] } },
    );
    // The single message is the first step: its fields are the ones the editor always had.
    expect(await screen.findByRole("textbox", { name: "Message" })).toHaveValue("Here is the link.");
    await user.click(within(screen.getByTestId("more-steps")).getByRole("button", { name: "Add step" }));
    await user.click(await screen.findByRole("menuitem", { name: /^Delay/ }));

    // The message and the new step are saved as a flow, and the flow editor takes over.
    await waitFor(() => expect(saved).toHaveLength(1));
    expect(saved[0]).toMatchObject({
      start: "message",
      steps: [
        { type: "send", id: "message", text: "Here is the link.", next: expect.any(String) },
        { type: "delay", seconds: 600, next: null },
      ],
    });
    expect(await screen.findByTestId("flow-editor")).toBeInTheDocument();
    expect(names()).toEqual(["Message", "Wait 10 minutes"]);
    expect(screen.queryByTestId("more-steps")).toBeNull();
  });

  it("can't add a step to an active automation until it is paused", async () => {
    renderEditor(automation({ status: "active", display_status: "active", trigger: "dm_keyword", public_reply_texts: [] }));
    const more = await screen.findByTestId("more-steps");
    expect(within(more).getByRole("button", { name: "Add step" })).toBeDisabled();
    expect(within(more).getAllByText("Pause this automation to add steps.").length).toBeGreaterThan(0);
  });

  it("edits a saved flow's steps and saves the whole flow after the last edit", async () => {
    const user = userEvent.setup();
    const { saved } = renderEditor(automation({ flow_source: "flow", trigger: "dm_keyword", public_reply_texts: [] }));
    const editor = await screen.findByTestId("flow-editor");
    expect(within(editor).getAllByRole("region")).toHaveLength(3);
    // The steps replace the message settings: no settings message around them.
    expect(screen.queryByTestId("more-steps")).toBeNull();

    await user.type(within(editor).getAllByRole("textbox", { name: "Message" })[2], "!");
    expect(saveStatus()).toHaveTextContent("Saving…");
    await waitFor(() => expect(saved).toHaveLength(1), { timeout: 3000 });
    expect(saved[0].steps.find((item) => item.id === "b")?.text).toBe("Option B!");
    await waitFor(() => expect(saveStatus()).toHaveTextContent("Saved"));
  });

  it("puts the API's activation errors on the steps they name, and goes to the first", async () => {
    const user = userEvent.setup();
    renderEditor(automation({ flow_source: "flow", trigger: "dm_keyword", public_reply_texts: [] }), {
      activate: () =>
        validation([
          { field: "flow.steps.2.text", message: "Write the message to send." },
          { field: "flow.steps.0.quick_replies", message: "A message can have link buttons or quick replies, not both." },
        ]),
    });
    await screen.findByTestId("flow-editor");
    await user.click(screen.getByRole("button", { name: "Activate" }));

    const attention = await screen.findByTestId("flow-attention");
    expect(attention).toHaveTextContent("2 steps need attention");
    expect(step("then")).toHaveAttribute("data-state", "error");
    const cards = within(screen.getByTestId("flow-editor")).getAllByRole("region");
    expect(cards[0]).toHaveAttribute("data-state", "error");
    expect(cards[1]).toHaveAttribute("data-state", "complete");
    expect(cards[2]).toHaveAttribute("data-state", "error");
    // The first step with a problem takes focus; the link goes to the other.
    await waitFor(() => expect(within(cards[0]).getAllByRole("textbox", { name: "Message" })[0]).toHaveFocus());
    await user.click(within(attention).getByRole("button", { name: /^Go to step 3/ }));
    expect(within(cards[2]).getByRole("textbox", { name: "Message" })).toHaveFocus();
    expect(screen.getByTestId("status-pill")).toHaveTextContent("Draft");
  });

  it("waits for the steps before it activates, so the API's errors land on them (C-154)", async () => {
    const user = userEvent.setup();
    let release = () => {};
    const flowLoaded = new Promise<void>((resolve) => (release = resolve));
    renderEditor(automation({ flow_source: "flow", trigger: "dm_keyword", public_reply_texts: [] }), {
      flowLoaded,
      activate: () => validation([{ field: "flow.steps.2.text", message: "Write the message to send." }]),
    });
    const activateButton = await screen.findByRole("button", { name: "Activate" });
    expect(activateButton).toBeDisabled();

    release();
    await screen.findByTestId("flow-editor");
    expect(activateButton).toBeEnabled();
    await user.click(activateButton);
    const attention = await screen.findByTestId("flow-attention");
    expect(attention).toHaveTextContent("Write the message to send.");
    expect(within(attention).getByRole("button", { name: /^Go to step 3/ })).toBeVisible();
  });
});
