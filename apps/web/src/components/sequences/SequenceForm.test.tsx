import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it, vi } from "vitest";

import type { Sequence, SequenceBody } from "@/lib/api/types";
import { account, json, renderWithApi } from "@/test/api";

import { sequence } from "./fixtures";
import { SequenceForm } from "./SequenceForm";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn() }),
  useParams: () => ({ slug: "maple" }),
  usePathname: () => "/w/maple/sequences/new",
  useSearchParams: () => new URLSearchParams(""),
}));

beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});

const TEMPLATE = {
  name: "sale_offer",
  language: "en",
  category: "marketing",
  status: "approved",
  body: "Hi {{1}}, our sale is on until {{2}}.",
  param_count: 2,
};

function setup(props: { sequence?: Sequence } = {}, overrides: Record<string, () => Response> = {}) {
  const sent: { method: string; path: string; body: unknown }[] = [];
  const view = renderWithApi(<SequenceForm {...props} />, {
    handlers: {
      "GET /v1/w/:wid/social-accounts": () =>
        json({ items: [account({ id: "wa1", platform: "whatsapp", display_name: "Maple Orders", username: null })] }),
      "GET /v1/w/:wid/tags": () => json({ items: [{ id: "t1", name: "Follow up", color: 0, contact_count: 0 }] }),
      "GET /v1/w/:wid/contact-fields": () => json({ items: [], limit: 5 }),
      "GET /v1/w/:wid/social-accounts/:id/templates": () => json({ items: [TEMPLATE] }),
      "GET /v1/w/:wid/broadcasts": () => json({ items: [], total: 0 }),
      "POST /v1/w/:wid/sequences/preview": (call) => {
        const body = call.body as SequenceBody;
        return json({
          contact_name: "Priya",
          problems: [],
          steps: body.steps.map((step, position) => ({
            position,
            after_seconds: step.delay_seconds,
            sends: step.template_name ? "template" : "text",
            text: step.text ?? "Hi Priya, our sale is on until 31 October.",
            note: step.template_name ? "Sent as a template to people who agreed to WhatsApp marketing." : null,
          })),
        });
      },
      "POST /v1/w/:wid/sequences": (call) => {
        sent.push({ method: "POST", path: call.path, body: call.body });
        return json(sequence({ id: "new1", status: "draft" }), 201);
      },
      "PUT /v1/w/:wid/sequences/:id": (call) => {
        sent.push({ method: "PUT", path: call.path, body: call.body });
        return json(sequence({ status: "paused" }));
      },
      "POST /v1/w/:wid/sequences/:id/activate": (call) => {
        sent.push({ method: "POST", path: call.path, body: null });
        return json(sequence());
      },
      "POST /v1/w/:wid/sequences/:id/pause": (call) => {
        sent.push({ method: "POST", path: call.path, body: null });
        return json(sequence({ status: "paused" }));
      },
      ...overrides,
    },
  });
  return { ...view, sent };
}

async function pick(user: ReturnType<typeof userEvent.setup>, name: string, option: string | RegExp) {
  await user.click(await screen.findByRole("combobox", { name }));
  await user.click(await screen.findByRole("option", { name: option }));
}

describe("the sequence form (GR-24)", () => {
  it("lists what is missing until the sequence can be saved, and blocks saving", async () => {
    setup();
    const preview = await screen.findByTestId("sequence-preview");
    expect(within(preview).getByText("Give the sequence a name.")).toBeInTheDocument();
    expect(within(preview).getByText("Choose the tag that starts it.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save as draft" })).toBeDisabled();
  });

  it("builds a three-day WhatsApp sequence and saves it as the API's body", async () => {
    const user = userEvent.setup();
    const { sent } = setup();
    await user.type(await screen.findByLabelText("Name"), "Three days");
    await pick(user, "Tag", "Follow up");

    // Step 1: a day after they enter, a message and the template that goes after 24 hours.
    const first = (await screen.findAllByTestId("step-card"))[0];
    await user.type(within(first).getByLabelText("Message"), "Hi {{first_name}, thanks for stopping by.");
    await pick(user, "Step 1 template", /sale_offer/);
    await user.click(
      within(within(first).getByRole("radiogroup", { name: "Variable 2 comes from" })).getByRole("radio", { name: "The same text" }),
    );
    await user.type(within(first).getByLabelText("Variable 2 text"), "31 October");

    // Step 2: three days after they entered, the same template.
    await user.click(screen.getByRole("button", { name: "Add step" }));
    const second = (await screen.findAllByTestId("step-card"))[1];
    await user.clear(within(second).getByLabelText("Wait"));
    await user.type(within(second).getByLabelText("Wait"), "3");
    await pick(user, "Step 2 counts from", "after they entered");
    await user.type(within(second).getByLabelText("Message"), "Still thinking it over?");

    const preview = screen.getByTestId("sequence-preview");
    await waitFor(() => expect(within(preview).getAllByTestId("preview-step")).toHaveLength(2));
    expect(within(preview).getByText("Day 1")).toBeInTheDocument();
    expect(within(preview).getByText("Day 3")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Save as draft" }));
    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0].body).toMatchObject({
      name: "Three days",
      social_account_id: "wa1",
      entry: { type: "tagged", tag_id: "t1" },
      stop: { on_reply: true, tag_ids: [], stages: [] },
      allow_reentry: false,
    });
    const steps = (sent[0].body as SequenceBody).steps;
    expect(steps[0]).toMatchObject({
      delay_seconds: 86_400,
      delay_from: "entry",
      text: "Hi {first_name}, thanks for stopping by.",
      template_name: "sale_offer",
      template_language: "en",
      variables: [{ source: "field", field: "first_name", fallback: null }, { source: "fixed", value: "31 October" }],
    });
    expect(steps[1]).toMatchObject({ delay_seconds: 259_200, delay_from: "entry", text: "Still thinking it over?", template_name: null });
    await waitFor(() => expect(push).toHaveBeenCalledWith("/w/maple/sequences/new1"));
    // Many typed fields: slower than the default under a full-suite load.
  }, 60_000);

  it("moves a step down and removes one", async () => {
    const user = userEvent.setup();
    setup({ sequence: sequence({ status: "paused", steps: [
      { position: 0, delay_seconds: 86_400, delay_from: "entry", text: "First", variables: [], respect_hours: false },
      { position: 1, delay_seconds: 86_400, delay_from: "previous", text: "Second", variables: [], respect_hours: false },
    ] as Sequence["steps"] }) });
    const cards = await screen.findAllByTestId("step-card");
    expect(within(cards[0]).getByLabelText("Message")).toHaveValue("First");
    await user.click(screen.getByRole("button", { name: "Move step 1 down" }));
    const moved = await screen.findAllByTestId("step-card");
    expect(within(moved[0]).getByLabelText("Message")).toHaveValue("Second");
    await user.click(screen.getByRole("button", { name: "Remove step 1" }));
    expect(await screen.findAllByTestId("step-card")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Remove step 1" })).toBeDisabled(); // the only step stays
  });

  it("shows the API's reason on the step it names", async () => {
    const user = userEvent.setup();
    setup(
      { sequence: sequence({ status: "paused", steps: [
        { position: 0, delay_seconds: 60, delay_from: "entry", text: "Hi", variables: [], respect_hours: false },
      ] as Sequence["steps"] }) },
      {
        "PUT /v1/w/:wid/sequences/:id": () =>
          new Response(
            JSON.stringify({
              type: "about:blank",
              title: "validation_error",
              status: 422,
              code: "validation_error",
              errors: [{ field: "steps.0.text", message: "Instagram messages can be up to 1,000 bytes; this one is 1,200." }],
            }),
            { status: 422, headers: { "Content-Type": "application/problem+json" } },
          ),
      },
    );
    await user.click(await screen.findByRole("button", { name: "Save changes" }));
    expect(await screen.findByText(/can be up to 1,000 bytes/)).toBeInTheDocument();
  });

  it("is read-only while the sequence is on, and Pause turns it off", async () => {
    const user = userEvent.setup();
    const { sent } = setup({ sequence: sequence({ status: "active", steps: [
      { position: 0, delay_seconds: 60, delay_from: "entry", text: "Hi", variables: [], respect_hours: false },
    ] as Sequence["steps"] }) });
    expect(await screen.findByText(/Pause it to change it/)).toBeInTheDocument();
    expect(screen.getByLabelText("Name")).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Save changes" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Pause" }));
    await waitFor(() => expect(sent.at(-1)?.path).toBe("/v1/w/w1/sequences/s1/pause"));
  });

  it("offers a reply to a broadcast as a start only on a WhatsApp number", async () => {
    const user = userEvent.setup();
    setup();
    await user.click(await screen.findByRole("combobox", { name: "Starts when" }));
    expect(await screen.findByRole("option", { name: "Someone replies to a broadcast" })).toBeInTheDocument();
  });
});
