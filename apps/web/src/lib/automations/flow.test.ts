import { describe, expect, it } from "vitest";

import type { FlowDefinition } from "@/lib/api/types";

import {
  compile,
  decompile,
  dropIndex,
  endsFlow,
  flatten,
  legacyErrorStep,
  locate,
  makeStep,
  move,
  newId,
  placeErrors,
  removeStep,
  stepProblems,
  updateList,
  updateStep,
  walk,
  type EditorStep,
  type FlowContext,
  type SendNode,
} from "./flow";

const CTX: FlowContext = {
  disclosure: null,
  fields: [
    { key: "city", type: "text" },
    { key: "mail", type: "email" },
  ],
  tagIds: new Set(["tag-1"]),
};

function send(id: string, text = "Hi", extra: Partial<SendNode> = {}): SendNode {
  return { kind: "send", id, text, image_asset_id: null, buttons: [], replies: [], typed: { mode: "none" }, ...extra };
}

/** comment -> ask email -> a message with two quick replies -> send A or B. */
function guideOrPrices(): EditorStep[] {
  return [
    { kind: "ask", id: "ask", text: "Email?", expect: "email", field_key: null, retry_text: "", tries: 2, skip: [] },
    send("pick", "Which one?", {
      replies: [
        { title: "Guide", steps: [send("a", "Here's the guide.")] },
        { title: "Prices", steps: [send("b", "Prices start at 499.")] },
      ],
    }),
  ];
}

describe("compile", () => {
  it("makes the stored graph of a list: each step leads to the one below", () => {
    const { definition, ids } = compile([send("one"), send("two"), { kind: "end", id: "stop" }]);
    expect(definition.start).toBe("one");
    expect(ids).toEqual(["one", "two", "stop"]);
    expect(definition.steps).toMatchObject([
      { type: "send", id: "one", next: "two" },
      { type: "send", id: "two", next: "stop" },
      { type: "end", id: "stop" },
    ]);
  });

  it("quick replies lead to their first step, and an empty arm carries on with the step below", () => {
    const tree: EditorStep[] = [
      send("pick", "Which?", {
        replies: [
          { title: "A", steps: [send("a")] },
          { title: "B", steps: [] },
        ],
        typed: { mode: "same", index: 1 },
      }),
      send("after", "See you"),
    ];
    const { definition } = compile(tree);
    const pick = definition.steps[0];
    expect(pick).toMatchObject({
      quick_replies: [
        { title: "A", next: "a" },
        { title: "B", next: "after" },
      ],
      on_text: "after",
      next: null,
    });
    // The arm "a" also carries on with the step below the fork.
    expect(definition.steps.find((s) => s.id === "a")).toMatchObject({ next: "after" });
  });

  it("the steps come in the order the cards show, and the ids follow them", () => {
    const { ids } = compile(guideOrPrices());
    expect(ids).toEqual(["ask", "pick", "a", "b"]);
  });

  it("a branch and a split lead each rule or path to its steps, and an empty one to the end", () => {
    const tree: EditorStep[] = [
      {
        kind: "branch",
        id: "br",
        rules: [{ when: { kind: "follows_business", follows: true }, steps: [send("yes")] }],
        otherwise: [],
      },
    ];
    expect(compile(tree).definition.steps[0]).toMatchObject({
      type: "branch",
      rules: [{ next: "yes" }],
      otherwise: null,
    });
    const split: EditorStep[] = [
      { kind: "split", id: "sp", paths: [{ weight: 1, steps: [send("p")] }, { weight: 3, steps: [send("q")] }] },
    ];
    expect(compile(split).definition.steps[0]).toMatchObject({
      type: "randomize",
      paths: [
        { weight: 1, next: "p" },
        { weight: 3, next: "q" },
      ],
    });
  });

  it("a question that never gets a fitting answer ends the flow, or carries on", () => {
    const ask = (skip: EditorStep[] | null): EditorStep[] => [
      { kind: "ask", id: "q", text: "?", expect: "text", field_key: "city", retry_text: "", tries: 2, skip },
      send("next"),
    ];
    expect(compile(ask(null)).definition.steps[0]).toMatchObject({ next: "next", on_skip: null });
    expect(compile(ask([])).definition.steps[0]).toMatchObject({ next: "next", on_skip: "next" });
    expect(compile(ask([send("other")])).definition.steps[0]).toMatchObject({ on_skip: "other" });
  });
});

describe("decompile", () => {
  it("is the inverse of compile for what the editor builds", () => {
    const trees: EditorStep[][] = [
      guideOrPrices(),
      [send("one"), { kind: "delay", id: "wait", seconds: 600 }, send("two")],
      [
        {
          kind: "branch",
          id: "br",
          rules: [
            { when: { kind: "contact", has: "email", known: true }, steps: [send("have")] },
            { when: { kind: "platform", platform: "instagram" }, steps: [{ kind: "end", id: "stop" }] },
          ],
          otherwise: [],
        },
        send("everyone", "Thanks"),
      ],
      [
        { kind: "split", id: "sp", paths: [{ weight: 1, steps: [send("p")] }, { weight: 1, steps: [send("q")] }] },
        send("then", "After the split"),
      ],
    ];
    for (const tree of trees) {
      const { definition } = compile(tree);
      const back = decompile(definition);
      expect(back).not.toBeNull();
      // Same graph after another round trip (ids of arms that end in a new End aside, there are none here).
      expect(compile(back as EditorStep[]).definition).toEqual(definition);
    }
  });

  it("reads a quick reply and a typed answer that lead to the same step", () => {
    // tap first: the opening's quick reply and any typed answer both lead to the message.
    const definition: FlowDefinition = {
      schema_version: 1,
      start: "opening",
      steps: [
        { type: "send", id: "opening", text: "Tap!", quick_replies: [{ title: "Send it", next: "message" }], on_text: "message" },
        { type: "send", id: "message", text: "Here you go", next: "follows" },
        { type: "branch", id: "follows", rules: [{ when: { kind: "follows_business", follows: false }, next: "nudge" }] },
        { type: "send", id: "nudge", text: "Follow us", buttons: [{ title: "View profile", profile: true }] },
      ],
    };
    const tree = decompile(definition);
    expect(tree?.map((s) => s.id)).toEqual(["opening", "message", "follows"]);
    const opening = tree?.[0] as SendNode;
    expect(opening.replies).toEqual([{ title: "Send it", steps: [] }]);
    expect(opening.typed).toEqual({ mode: "own", steps: [] });
    expect(compile(tree as EditorStep[]).definition.steps.map((s) => s.id)).toEqual(["opening", "message", "follows", "nudge"]);
  });

  it("a typed answer that goes where an option goes is read as the option's own steps carrying on", () => {
    const definition: FlowDefinition = {
      schema_version: 1,
      start: "hello",
      steps: [
        {
          type: "send",
          id: "hello",
          text: "Hi",
          quick_replies: [
            { title: "Catalogue", next: "email" },
            { title: "Prices", next: "prices" },
          ],
          on_text: "email",
        },
        { type: "ask", id: "email", text: "Email?", expect: "email", retry_text: "", tries: 2, next: "catalogue" },
        { type: "send", id: "catalogue", text: "Here it is." },
        { type: "send", id: "prices", text: "From 499." },
      ],
    };
    const tree = decompile(definition) as EditorStep[];
    // "Catalogue" and a typed answer meet at the question, which then follows the message.
    expect(tree.map((s) => s.id)).toEqual(["hello", "email", "catalogue"]);
    const hello = tree[0] as SendNode;
    expect(hello.replies[0].steps).toEqual([]);
    expect(hello.typed).toEqual({ mode: "own", steps: [] });
    // "Prices" stops: its path says so with an End.
    expect(hello.replies[1].steps.map((s) => s.kind)).toEqual(["send", "end"]);
    const back = compile(tree).definition;
    expect(back.steps[0]).toMatchObject({
      quick_replies: [
        { title: "Catalogue", next: "email" },
        { title: "Prices", next: "prices" },
      ],
      on_text: "email",
    });
    expect(back.steps.find((s) => s.id === "prices")).toMatchObject({ next: expect.any(String) });
  });


  it("gives a path that stops where others carry on a lone End, so the stop is kept", () => {
    const definition: FlowDefinition = {
      schema_version: 1,
      start: "br",
      steps: [
        {
          type: "branch",
          id: "br",
          rules: [
            { when: { kind: "contact", has: "email", known: true }, next: "a" },
            { when: { kind: "contact", has: "phone", known: true }, next: "join" },
          ],
          otherwise: "join",
        },
        { type: "send", id: "a", text: "A", next: "join" },
        { type: "send", id: "join", text: "Everyone" },
      ],
    };
    const tree = decompile(definition);
    expect(tree?.map((s) => s.id)).toEqual(["br", "join"]);
    const again = compile(tree as EditorStep[]).definition;
    expect(again.steps.find((s) => s.id === "a")).toMatchObject({ next: "join" });
    expect(again.steps[0]).toMatchObject({ rules: [{ next: "a" }, { next: "join" }], otherwise: "join" });

    const stops: FlowDefinition = {
      schema_version: 1,
      start: "br",
      steps: [
        {
          type: "branch",
          id: "br",
          rules: [
            { when: { kind: "contact", has: "email", known: true }, next: "a" },
            { when: { kind: "contact", has: "phone", known: true }, next: "join" },
          ],
          otherwise: null,
        },
        { type: "send", id: "a", text: "A", next: "join" },
        { type: "send", id: "join", text: "Everyone" },
      ],
    };
    const kept = decompile(stops) as EditorStep[];
    const branch = kept[0];
    expect(branch.kind === "branch" && branch.otherwise.map((s) => s.kind)).toEqual(["end"]);
    expect(compile(kept).definition.steps[0]).toMatchObject({ otherwise: expect.any(String) });
  });

  it("cannot show paths that share steps without one place they meet, or steps nothing leads to", () => {
    // x leads to p; y chooses p or q; z leads to q. p and q are each reached by two paths.
    const tangled: FlowDefinition = {
      schema_version: 1,
      start: "br",
      steps: [
        {
          type: "branch",
          id: "br",
          rules: [
            { when: { kind: "contact", has: "email", known: true }, next: "x" },
            { when: { kind: "contact", has: "phone", known: true }, next: "y" },
          ],
          otherwise: "z",
        },
        { type: "send", id: "x", text: "X", next: "p" },
        {
          type: "branch",
          id: "y",
          rules: [{ when: { kind: "follows_business", follows: true }, next: "p" }],
          otherwise: "q",
        },
        { type: "send", id: "z", text: "Z", next: "q" },
        { type: "send", id: "p", text: "P" },
        { type: "send", id: "q", text: "Q" },
      ],
    };
    expect(decompile(tangled)).toBeNull();

    const orphan: FlowDefinition = {
      schema_version: 1,
      start: "a",
      steps: [
        { type: "send", id: "a", text: "A" },
        { type: "send", id: "lost", text: "Nothing leads here" },
      ],
    };
    expect(decompile(orphan)).toBeNull();
  });
});

describe("tree changes", () => {
  it("adds, updates, moves and removes steps in the right list", () => {
    const tree = guideOrPrices();
    const edited = updateStep(tree, "a", (node) => (node.kind === "send" ? { ...node, text: "Changed" } : node));
    expect(flatten(edited).find((s) => s.id === "a")).toMatchObject({ text: "Changed" });

    const added = updateList(tree, { parent: "pick", slot: "reply:0" }, (steps) => [...steps, makeStep("delay", new Set(["a"]))]);
    const pick = added[1] as SendNode;
    expect(pick.replies[0].steps.map((s) => s.kind)).toEqual(["send", "delay"]);

    const swapped = updateList(tree, { parent: null, slot: "root" }, (steps) => move(steps, 1, 0));
    expect(swapped.map((s) => s.id)).toEqual(["pick", "ask"]);

    expect(flatten(removeStep(tree, "b")).map((s) => s.id)).toEqual(["ask", "pick", "a"]);
    expect(locate(tree, "b")).toEqual({ ref: { parent: "pick", slot: "reply:1" }, index: 0, length: 1 });
    expect(locate(tree, "pick")).toEqual({ ref: { parent: null, slot: "root" }, index: 1, length: 2 });
  });

  it("new ids are valid for the API and not taken", () => {
    const taken = new Set<string>();
    for (let i = 0; i < 200; i += 1) {
      const id = newId(taken);
      expect(id).toMatch(/^[a-z0-9][a-z0-9_-]{0,39}$/);
      expect(taken.has(id)).toBe(false);
      taken.add(id);
    }
  });

  it("End and the AI reply stop a list", () => {
    expect(endsFlow({ kind: "end", id: "e" })).toBe(true);
    expect(endsFlow({ kind: "ai", id: "ai", instructions: "x" })).toBe(true);
    expect(endsFlow(send("s"))).toBe(false);
    expect(endsFlow(undefined)).toBe(false);
  });

  it("works out where a dragged card lands", () => {
    // Two other cards, middles at 100 and 300.
    expect(dropIndex([100, 300], 40)).toBe(0);
    expect(dropIndex([100, 300], 200)).toBe(1);
    expect(dropIndex([100, 300], 500)).toBe(2);
    expect(dropIndex([], 10)).toBe(0);
  });
});

describe("checking a step", () => {
  it("a message needs text (or an image), https links and titles", () => {
    expect(stepProblems(send("s", ""), CTX)).toEqual({ text: "Write the message to send." });
    expect(stepProblems(send("s", "Hi"), CTX)).toEqual({});
    const buttons = stepProblems(
      send("s", "Hi", { buttons: [
        { title: "", url: "http://x.test", profile: false },
        { title: "Shop", url: "", profile: false },
        { title: "Ok", url: "https://x.test", profile: false },
      ] }),
      CTX,
    );
    expect(buttons).toEqual({
      "buttons.0.title": "Give the button a title.",
      "buttons.0.url": "Use a link that starts with https://.",
      "buttons.1.url": "Add a link, or make it the profile button.",
    });
    expect(stepProblems(send("s", "", { image_asset_id: "img-1" }), CTX)).toEqual({});
  });

  it("quick replies have titles, and can't be mixed with link buttons or an image", () => {
    const problems = stepProblems(
      send("s", "Hi", {
        replies: [{ title: "", steps: [] }],
        buttons: [{ title: "Shop", url: "https://x.test", profile: false }],
        image_asset_id: "img-1",
      }),
      CTX,
    );
    expect(problems).toMatchObject({
      "quick_replies.0.title": "Give the option a title.",
      quick_replies: "A message can have link buttons or quick replies, not both.",
      image_asset_id: expect.stringContaining("Quick replies go on a text message"),
    });
  });

  it("a message over Instagram's limit says so, counting the disclosure line", () => {
    const long = stepProblems(send("s", "x".repeat(990)), { ...CTX, disclosure: "Sent automatically, y".repeat(2) });
    expect(long.text).toMatch(/Instagram allows 1,000 bytes/);
  });

  it("a question needs its text and a field of the right type", () => {
    const ask = (field_key: string | null, expect: "text" | "email" | "phone"): Extract<EditorStep, { kind: "ask" }> => ({
      kind: "ask",
      id: "q",
      text: "Q?",
      expect,
      field_key,
      retry_text: "",
      tries: 2,
      skip: [],
    });
    expect(stepProblems(ask(null, "email"), CTX)).toEqual({});
    expect(stepProblems(ask(null, "text"), CTX)).toEqual({ field_key: "Choose the field to save the answer to." });
    expect(stepProblems(ask("city", "text"), CTX)).toEqual({});
    expect(stepProblems(ask("gone", "text"), CTX).field_key).toMatch(/doesn't exist/);
    expect(stepProblems(ask("city", "email"), CTX).field_key).toMatch(/same type/);
    expect(stepProblems({ ...ask(null, "email"), text: " " }, CTX)).toEqual({ text: "Write the question to ask." });
  });

  it("a branch, an action and the AI reply need what they point at", () => {
    const branch: EditorStep = {
      kind: "branch",
      id: "b",
      rules: [
        { when: { kind: "tag", tag_id: "tag-1", has: true }, steps: [] },
        { when: { kind: "tag", tag_id: "tag-2", has: true }, steps: [] },
        { when: { kind: "field", key: "city", op: "equals", value: " " }, steps: [] },
      ],
      otherwise: [],
    };
    expect(stepProblems(branch, CTX)).toEqual({ "rules.1.when": "Choose a tag.", "rules.2.when": "Write the value to compare with." });
    expect(stepProblems({ kind: "action", id: "a", action: { kind: "add_tag", tag_id: "tag-2" } }, CTX)).toEqual({ action: "Choose a tag." });
    expect(stepProblems({ kind: "action", id: "a", action: { kind: "set_field", key: "city", value: "" } }, CTX)).toEqual({
      "action.value": "Write the value to set.",
    });
    expect(stepProblems({ kind: "ai", id: "r", instructions: "" }, CTX)).toEqual({ instructions: "Write the instructions for the AI." });
    expect(stepProblems({ kind: "delay", id: "d", seconds: 60 }, CTX)).toEqual({});
  });
});

describe("the API's problems on steps", () => {
  it("places flow.steps.N fields on the step at that index", () => {
    const placed = placeErrors(
      [
        { field: "flow.steps.1.text", message: "Write the message to send." },
        { field: "flow.steps.1.buttons.0.url", message: "Use https." },
        { field: "flow.steps.0", message: "Nothing leads to this step." },
        { field: "flow.start", message: "Choose the first step." },
        { field: "name", message: "Not ours." },
      ],
      ["ask", "pick"],
    );
    expect(placed.byStep).toEqual({
      pick: { text: "Write the message to send.", "buttons.0.url": "Use https." },
      ask: { "": "Choose the first step." },
    });
    expect(placed.general).toEqual(["Not ours."]);
  });

  it("reads a message-settings error as the compiled flow's step", () => {
    expect(legacyErrorStep("message_text")).toEqual({ id: "message", field: "text" });
    expect(legacyErrorStep("message_buttons.0.url")).toEqual({ id: "message", field: "buttons.0.url" });
    expect(legacyErrorStep("opening_text")).toEqual({ id: "opening", field: "text" });
    expect(legacyErrorStep("keywords")).toBeNull();
  });
});

describe("walking a flow", () => {
  const { definition } = compile(guideOrPrices());
  const values = { first_name: "Priya", username: "priya" };

  it("follows the first way at each fork, and says the ways there are", () => {
    const path = walk(definition, { values, disclosure: null });
    expect(path.map((s) => s.step_id)).toEqual(["ask", "pick", "a"]);
    expect(path[0].exits).toEqual(["Answers", "Doesn't answer in a way that fits"]);
    expect(path[1]).toMatchObject({ quick_replies: ["Guide", "Prices"], picked: 0 });
    expect(path[1].exits).toEqual(["Taps Guide", "Taps Prices", "Types an answer"]);
  });

  it("follows the way chosen, fork by fork", () => {
    const path = walk(definition, { values, disclosure: null, choices: [0, 1] });
    expect(path.map((s) => s.step_id)).toEqual(["ask", "pick", "b"]);
    expect(path[2].text).toBe("Prices start at 499.");
    // A choice past the last way takes the last: here, a typed answer, which ends the flow.
    expect(walk(definition, { values, disclosure: null, choices: [0, 9] }).map((s) => s.step_id)).toEqual(["ask", "pick"]);
  });

  it("renders the name and the disclosure line", () => {
    const { definition: greeting } = compile([send("hi", "Hi {first_name|there}!")]);
    expect(walk(greeting, { values, disclosure: "Sent automatically" })[0].text).toBe("Hi Priya!\n\nSent automatically");
    expect(walk(greeting, { values: { first_name: null }, disclosure: null })[0].text).toBe("Hi there!");
  });

  it("titles the steps that send nothing", () => {
    const { definition: mixed } = compile([
      { kind: "delay", id: "w", seconds: 3600 },
      { kind: "action", id: "n", action: { kind: "notify_team", note: "" } },
      { kind: "end", id: "e" },
    ]);
    expect(walk(mixed, { values, disclosure: null }).map((s) => s.title)).toEqual(["Wait 1 hour", "Notify the team", "End"]);
  });
});
