import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
  AiSettings,
  KnowledgeGap,
  KnowledgeSource,
  KnowledgeSourceCreate,
  KnowledgeTestResult,
  MediaAsset,
} from "@/lib/api/types";
import {
  aiSettings,
  billingState,
  json,
  knowledgeGap,
  knowledgeSource,
  noContent,
  planList,
  problem,
  renderWithApi,
  type Call,
} from "@/test/api";

import { KnowledgePage } from "./KnowledgePage";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

const hoursAgo = (h: number) => new Date(Date.now() - h * 3_600_000).toISOString();

type State = {
  settings: AiSettings;
  sources: KnowledgeSource[];
  gaps: KnowledgeGap[];
  limit: number | null;
  used: number;
  create?: (call: Call) => Response;
  test?: KnowledgeTestResult;
  testFails?: () => Response;
};

function setup(partial: Partial<State> = {}, upload?: (file: File) => Promise<MediaAsset>) {
  const state: State = {
    settings: aiSettings({ business_description: "Handmade linen dresses for women in India.", sign_off: "Team Maple" }),
    sources: [knowledgeSource()],
    gaps: [],
    limit: 200_000,
    used: 1_240,
    ...partial,
  };
  let seq = 0;
  const view = renderWithApi(
    <KnowledgePage
      upload={
        upload
          ? async (file, { onProgress }) => {
              onProgress(0.5);
              return upload(file);
            }
          : undefined
      }
    />,
    {
      handlers: {
        "GET /v1/w/:wid/ai-settings": () => json(state.settings),
        "PUT /v1/w/:wid/ai-settings": (call) => {
          state.settings = { ...(call.body as AiSettings), updated_at: "2026-09-28T12:00:00Z" };
          return json(state.settings);
        },
        "GET /v1/w/:wid/knowledge-sources": () =>
          json({ items: state.sources, usage: { characters_used: state.used, characters_limit: state.limit } }),
        "POST /v1/w/:wid/knowledge-sources": (call) => {
          if (state.create) return state.create(call);
          const body = call.body as KnowledgeSourceCreate;
          seq += 1;
          const created = knowledgeSource({
            id: `new${seq}`,
            type: body.type,
            title: body.title ?? body.question ?? body.url ?? "Uploaded file",
            question: body.question ?? null,
            body: body.body ?? null,
            url: body.url ?? null,
            file_asset_id: body.file_asset_id ?? null,
            status: "pending",
            char_count: 0,
            chunk_count: 0,
          });
          state.sources = [created, ...state.sources];
          if (body.gap_id) state.gaps = state.gaps.filter((gap) => gap.id !== body.gap_id);
          return json(created, 201);
        },
        "PATCH /v1/w/:wid/knowledge-sources/:id": (call, p) => {
          const updated = { ...state.sources.find((s) => s.id === p.id)!, ...(call.body as object), status: "processing" as const };
          state.sources = state.sources.map((s) => (s.id === p.id ? updated : s));
          return json(updated);
        },
        "DELETE /v1/w/:wid/knowledge-sources/:id": (_, p) => {
          state.sources = state.sources.filter((s) => s.id !== p.id);
          return noContent();
        },
        "POST /v1/w/:wid/knowledge/test": () =>
          state.testFails?.() ??
          json(state.test ?? { can_answer: true, answer: "Yes, in 5–7 days.", missing_info: null, sources: [] }),
        "GET /v1/w/:wid/knowledge-gaps": () => json({ items: state.gaps }),
        "POST /v1/w/:wid/knowledge-gaps/:id/dismiss": (_, p) => {
          const gap = state.gaps.find((g) => g.id === p.id)!;
          state.gaps = state.gaps.filter((g) => g.id !== p.id);
          return json({ ...gap, status: "dismissed" });
        },
        "GET /v1/w/:wid/billing": () => json(billingState()),
        "GET /v1/billing/plans": () => json(planList()),
      },
      upgradeDialog: true,
    },
  );
  const posted = () =>
    view.calls.filter((c) => c.method === "POST" && c.path === "/v1/w/w1/knowledge-sources").map((c) => c.body);
  return { ...view, state, posted };
}

async function addFromMenu(type: "FAQ" | "Note" | "Web page" | "File") {
  const user = userEvent.setup();
  await user.click(screen.getAllByRole("button", { name: "Add knowledge" })[0]);
  await user.click(await screen.findByRole("menuitem", { name: type }));
  return user;
}

beforeEach(() => {
  toast.success.mockReset();
  toast.error.mockReset();
});

describe("Brand voice (FR-KB-04, F-14)", () => {
  it("the first visit opens the form with the description hint; Save sends the whole settings object", async () => {
    const user = userEvent.setup();
    const { calls } = setup({
      settings: aiSettings({ escalation_phrases: ["lawyer"], takeover_minutes: 30 }),
    });
    const form = await screen.findByRole("form", { name: "Brand voice" });
    expect(within(form).getByLabelText("Business description")).toHaveValue("");
    expect(within(form).getByText("Two or three sentences about what you sell and who buys it.")).toBeInTheDocument();

    await user.type(within(form).getByLabelText("Business name"), "Maple Studio");
    await user.type(within(form).getByLabelText("Business description"), "Handmade linen dresses.");
    await user.click(within(form).getByRole("radio", { name: "Professional" }));
    await user.click(within(form).getByRole("radio", { name: "None" }));
    await user.type(within(form).getByRole("textbox", { name: "Add to Always" }), "Mention free shipping over ₹3,000{Enter}");
    await user.type(within(form).getByRole("textbox", { name: "Add to Never" }), "Promise delivery dates{Enter}");
    await user.type(within(form).getByLabelText("Sign-off"), "Team Maple");
    await user.click(within(form).getByRole("button", { name: "Save" }));

    await waitFor(() => expect(calls.some((c) => c.method === "PUT")).toBe(true));
    expect(calls.find((c) => c.method === "PUT")?.body).toEqual({
      business_name: "Maple Studio",
      business_description: "Handmade linen dresses.",
      tone: "professional",
      emoji_policy: "none",
      do_list: ["Mention free shipping over ₹3,000"],
      dont_list: ["Promise delivery dates"],
      escalation_phrases: ["lawyer"],
      sign_off: "Team Maple",
      takeover_minutes: 30,
    });
    // Saved with a description: the card shows the summary.
    const card = await screen.findByRole("region", { name: "Brand voice" });
    await waitFor(() => expect(within(card).queryByRole("form")).not.toBeInTheDocument());
    expect(within(card).getByText("Maple Studio")).toBeInTheDocument();
    expect(within(card).getByText(/Professional · None emoji · Signs off “Team Maple”/)).toBeInTheDocument();
  });

  it("once described, it shows a summary with Edit", async () => {
    const user = userEvent.setup();
    setup();
    const card = await screen.findByRole("region", { name: "Brand voice" });
    expect(within(card).getByText("Handmade linen dresses for women in India.")).toBeInTheDocument();
    expect(within(card).getByText("Maple Bakery")).toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Edit" }));
    expect(within(card).getByLabelText("Business description")).toHaveValue("Handmade linen dresses for women in India.");
    await user.click(within(card).getByRole("button", { name: "Cancel" }));
    expect(within(card).queryByRole("form")).not.toBeInTheDocument();
  });
});

describe("Sources (FR-KB-01, FR-KB-02)", () => {
  it("shows Processing, Ready with counts, and Failed with the reason", async () => {
    setup({
      sources: [
        knowledgeSource({ id: "a", title: "Returns policy", type: "text", status: "processing", char_count: 0, chunk_count: 0 }),
        knowledgeSource({ id: "b", title: "Shipping", type: "text", status: "ready", char_count: 12_400, chunk_count: 11 }),
        knowledgeSource({
          id: "c",
          title: "maple.example/faq",
          type: "url",
          url: "https://maple.example/faq",
          status: "failed",
          error: "The page didn't load (404).",
        }),
      ],
    });
    const table = await screen.findByRole("table", { name: "Knowledge sources" });
    const rows = within(table).getAllByRole("row").slice(1);
    // Each status is in the row twice: under the name below 768 px and in the Status column from there (CSS
    // shows one; see "keeps the source name readable on phones").
    expect(within(rows[0]).getAllByText("Processing")).toHaveLength(2);
    expect(within(rows[1]).getAllByText("Ready")).toHaveLength(2);
    expect(within(rows[1]).getByText("12,400")).toBeInTheDocument();
    expect(within(rows[1]).getByText("11 chunks")).toBeInTheDocument();
    expect(within(rows[2]).getAllByText("Failed")).toHaveLength(2);
    expect(within(rows[2]).getByText("The page didn't load (404).")).toBeInTheDocument();
    expect(within(rows[2]).getByText("https://maple.example/faq")).toBeInTheDocument();
  });

  it("keeps the source name readable on phones: the status goes under it below 768 px (UI-038)", async () => {
    setup({ sources: [knowledgeSource({ title: "Shipping", status: "ready" })] });
    const table = await screen.findByRole("table", { name: "Knowledge sources" });
    expect(within(table).getByRole("columnheader", { name: "Status" })).toHaveClass("hidden", "md:table-cell");
    const [, row] = within(table).getAllByRole("row");
    const [source, status] = within(row).getAllByRole("cell");
    expect(within(source).getByText("Ready")).toHaveClass("md:hidden");
    expect(status).toHaveClass("hidden", "md:table-cell");
    expect(within(status).getByText("Ready")).not.toHaveClass("md:hidden");
    // Edit and Delete: 32 px icon Buttons, 40 px on touch, without a viewport patch.
    for (const name of ["Edit Shipping", "Delete Shipping"]) {
      const button = within(row).getByRole("button", { name });
      expect(button).toHaveClass("size-8", "pointer-coarse:size-10");
      expect(button.className).not.toMatch(/md:size-/);
    }
  });

  it("empty: Teach the AI your business", async () => {
    setup({ sources: [], used: 0 });
    expect(await screen.findByText("Teach the AI your business")).toBeInTheDocument();
    expect(screen.getByText("Add prices, shipping and FAQs so suggested replies are accurate.")).toBeInTheDocument();
  });

  it("adds an FAQ, which appears as Processing", async () => {
    const { posted } = setup();
    await screen.findByRole("table", { name: "Knowledge sources" });
    const user = await addFromMenu("FAQ");
    const form = await screen.findByRole("form", { name: "Add an FAQ" });
    await user.click(within(form).getByRole("button", { name: "Add" }));
    expect(within(form).getByText("Enter the customer's question.")).toBeInTheDocument();
    expect(posted()).toHaveLength(0);

    await user.type(within(form).getByLabelText("Question"), "Is COD available?");
    await user.type(within(form).getByLabelText("Answer"), "Yes, across India.");
    await user.click(within(form).getByRole("button", { name: "Add" }));

    await waitFor(() => expect(posted()).toEqual([{ type: "faq", question: "Is COD available?", body: "Yes, across India.", gap_id: null }]));
    const row = (await screen.findByText("Is COD available?")).closest("tr") as HTMLElement;
    expect(within(row).getAllByText("Processing")).toHaveLength(2);
    expect(toast.success).toHaveBeenCalledWith("Added to knowledge");
  });

  it("adds a note", async () => {
    const { posted } = setup();
    await screen.findByRole("table", { name: "Knowledge sources" });
    const user = await addFromMenu("Note");
    const form = await screen.findByRole("form", { name: "Add a note" });
    await user.type(within(form).getByLabelText("Title"), "Shipping policy");
    await user.type(within(form).getByLabelText("Text"), "We ship across India in 3–5 days.");
    await user.click(within(form).getByRole("button", { name: "Add" }));
    await waitFor(() =>
      expect(posted()).toEqual([{ type: "text", title: "Shipping policy", body: "We ship across India in 3–5 days." }]),
    );
  });

  it("adds a web page after checking the address", async () => {
    const { posted } = setup();
    await screen.findByRole("table", { name: "Knowledge sources" });
    const user = await addFromMenu("Web page");
    const form = await screen.findByRole("form", { name: "Add a web page" });
    await user.type(within(form).getByLabelText("Web address"), "maple faq");
    await user.click(within(form).getByRole("button", { name: "Add" }));
    expect(within(form).getByText("Enter a web address starting with http:// or https://.")).toBeInTheDocument();

    await user.clear(within(form).getByLabelText("Web address"));
    await user.type(within(form).getByLabelText("Web address"), "https://maple.example/shipping");
    await user.click(within(form).getByRole("button", { name: "Add" }));
    await waitFor(() => expect(posted()).toEqual([{ type: "url", url: "https://maple.example/shipping", title: null }]));
  });

  it("adds a file through the signed upload, then registers it", async () => {
    const upload = vi.fn(async (file: File) => ({ id: "asset-1", original_filename: file.name }) as MediaAsset);
    const { posted } = setup({}, upload);
    await screen.findByRole("table", { name: "Knowledge sources" });
    const user = await addFromMenu("File");
    const form = await screen.findByRole("form", { name: "Add a file" });

    // The picker offers only these types; a file dropped past it is still checked.
    await userEvent
      .setup({ applyAccept: false })
      .upload(within(form).getByTestId("knowledge-file-input"), new File(["x"], "photo.png", { type: "image/png" }));
    expect(within(form).getByText("Use a PDF, DOCX, TXT or MD file.")).toBeInTheDocument();

    await user.upload(within(form).getByTestId("knowledge-file-input"), new File(["%PDF"], "size-guide.pdf", { type: "application/pdf" }));
    expect(within(form).getByText(/size-guide\.pdf/)).toBeInTheDocument();
    await user.click(within(form).getByRole("button", { name: "Add" }));

    await waitFor(() => expect(posted()).toEqual([{ type: "file", file_asset_id: "asset-1", title: null }]));
    expect(upload).toHaveBeenCalledOnce();
  });

  it("over the plan's knowledge limit (402): says which limit, with Upgrade", async () => {
    const { state } = setup();
    state.create = () =>
      problem(402, "quota_exceeded", "Plan limit reached", { entitlement: "knowledge_characters", limit: 200_000 });
    await screen.findByRole("table", { name: "Knowledge sources" });
    const user = await addFromMenu("FAQ");
    const form = await screen.findByRole("form", { name: "Add an FAQ" });
    await user.type(within(form).getByLabelText("Question"), "Q?");
    await user.type(within(form).getByLabelText("Answer"), "A.");
    await user.click(within(form).getByRole("button", { name: "Add" }));
    const alert = await within(form).findByRole("alert");
    expect(alert).toHaveTextContent("Your plan includes 200,000 characters of knowledge.");
    // One message: the form's (the create opts out of the automatic dialog); Upgrade opens it.
    expect(screen.queryByTestId("upgrade-dialog")).not.toBeInTheDocument();
    await user.click(within(alert).getByRole("button", { name: "Upgrade" }));
    expect(await screen.findByRole("dialog", { name: "Knowledge limit reached" })).toHaveTextContent(
      "includes 200,000 characters of knowledge.",
    );
  });

  it("the usage meter turns full at the limit", async () => {
    setup({ used: 200_000 });
    const meter = await screen.findByRole("meter", { name: "Knowledge used" });
    expect(meter).toHaveAttribute("aria-valuetext", "200,000 of 200,000 characters");
    expect(meter.closest("[data-level]")).toHaveAttribute("data-level", "full");
    expect(screen.getByText("Your plan includes 200,000 characters of knowledge.")).toBeInTheDocument();
  });

  it("edits an FAQ, sending only what changed", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    await user.click(await screen.findByRole("button", { name: "Edit Do you ship to Dubai?" }));
    const form = await screen.findByRole("form", { name: "Edit FAQ" });
    const answer = within(form).getByLabelText("Answer");
    await user.clear(answer);
    await user.type(answer, "Yes, 4–6 business days.");
    await user.click(within(form).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(calls.some((c) => c.method === "PATCH")).toBe(true));
    const patch = calls.find((c) => c.method === "PATCH");
    expect(patch?.path).toBe("/v1/w/w1/knowledge-sources/ks1");
    expect(patch?.body).toEqual({ reingest: false, body: "Yes, 4–6 business days." });
  });

  it("deletes after confirming", async () => {
    const user = userEvent.setup();
    const { calls } = setup();
    const trigger = await screen.findByRole("button", { name: "Delete Do you ship to Dubai?" });
    expect(trigger).toHaveAttribute("data-variant", "destructive-ghost");
    await user.click(trigger);
    const dialog = await screen.findByRole("alertdialog", { name: "Delete “Do you ship to Dubai?”?" });
    expect(within(dialog).getByRole("button", { name: "Delete" })).toHaveAttribute("data-variant", "destructive");
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
    await user.click(within(dialog).getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(calls.some((c) => c.method === "DELETE" && c.path === "/v1/w/w1/knowledge-sources/ks1")).toBe(true));
    await waitFor(() => expect(screen.queryByText("Do you ship to Dubai?")).not.toBeInTheDocument());
  });

  it("returns focus to Edit and Delete when the sheet or the confirmation closes (UX-A11Y-02)", async () => {
    const user = userEvent.setup();
    setup();
    const edit = await screen.findByRole("button", { name: "Edit Do you ship to Dubai?" });
    await user.click(edit);
    const form = await screen.findByRole("form", { name: "Edit FAQ" });
    await user.click(within(form).getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(screen.queryByRole("form", { name: "Edit FAQ" })).not.toBeInTheDocument());
    await waitFor(() => expect(edit).toHaveFocus());

    const remove = screen.getByRole("button", { name: "Delete Do you ship to Dubai?" });
    await user.click(remove);
    await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(remove).toHaveFocus());

    // From the Add knowledge menu: back to the menu's button, not <body> (the item is gone by then).
    await addFromMenu("Note");
    const note = await screen.findByRole("form", { name: "Add a note" });
    await user.click(within(note).getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(screen.queryByRole("form", { name: "Add a note" })).not.toBeInTheDocument());
    await waitFor(() => expect(screen.getAllByRole("button", { name: "Add knowledge" })[0]).toHaveFocus());
  });
});

describe("Test your knowledge (FR-KB-03)", () => {
  it("shows the drafted answer with the sources it used", async () => {
    const user = userEvent.setup();
    const { calls } = setup({
      test: {
        can_answer: true,
        answer: "Yes, we ship to the UAE in 5–7 business days.",
        missing_info: null,
        sources: [{ id: "k1", title: "Shipping policy" }],
      },
    });
    const box = await screen.findByRole("region", { name: "Test your knowledge" });
    await user.type(within(box).getByLabelText("Question"), "Do you ship to Dubai?");
    await user.click(within(box).getByRole("button", { name: "Ask" }));
    const answer = await within(box).findByTestId("test-answer");
    expect(answer).toHaveTextContent("Yes, we ship to the UAE in 5–7 business days.");
    expect(within(answer).getByText("From: Shipping policy")).toBeInTheDocument();
    expect(calls.find((c) => c.path === "/v1/w/w1/knowledge/test")?.body).toEqual({ question: "Do you ship to Dubai?" });
  });

  it("or Not in your knowledge", async () => {
    const user = userEvent.setup();
    setup({ test: { can_answer: false, answer: null, missing_info: "gift wrapping options", sources: [] } });
    const box = await screen.findByRole("region", { name: "Test your knowledge" });
    await user.type(within(box).getByLabelText("Question"), "Do you gift wrap?{Enter}");
    const answer = await within(box).findByTestId("test-answer");
    expect(answer).toHaveTextContent("Not in your knowledge");
    expect(answer).toHaveTextContent("Missing: gift wrapping options.");
  });

  it("out of credits (402): one message where the answer goes, with Upgrade", async () => {
    const user = userEvent.setup();
    setup({
      testFails: () =>
        problem(402, "quota_exceeded", "Your AI credits for this period are used up.", {
          entitlement: "ai_credits_monthly",
          limit: 5000,
        }),
    });
    const box = await screen.findByRole("region", { name: "Test your knowledge" });
    await user.type(within(box).getByLabelText("Question"), "Do you gift wrap?{Enter}");
    const alert = await within(box).findByRole("alert");
    expect(alert).toHaveTextContent("Your AI credits for this period are used up.");
    expect(screen.queryByTestId("upgrade-dialog")).not.toBeInTheDocument();
    await user.click(within(alert).getByRole("button", { name: "Upgrade" }));
    expect(await screen.findByRole("dialog", { name: "AI credits used up" })).toBeInTheDocument();
  });
});

describe("Questions the AI couldn't answer (FR-KB-06, F-17)", () => {
  it("lists open gaps above brand voice with times asked, last asked and an example", async () => {
    setup({ gaps: [knowledgeGap({ last_seen_at: hoursAgo(2.5) })] });
    const card = await screen.findByRole("region", { name: "Questions the AI couldn't answer" });
    expect(within(card).getByText("shipping to uae")).toBeInTheDocument();
    expect(within(card).getByText("Asked 14 times · last 2h ago")).toBeInTheDocument();
    expect(within(card).getByText("“Do you ship to Dubai?”")).toBeInTheDocument();
    const brandVoice = screen.getByRole("region", { name: "Brand voice" });
    expect(card.compareDocumentPosition(brandVoice) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("Add answer opens the FAQ form with the customer's question; saving answers the gap", async () => {
    const user = userEvent.setup();
    const { posted } = setup({ gaps: [knowledgeGap()] });
    const card = await screen.findByRole("region", { name: "Questions the AI couldn't answer" });
    await user.click(within(card).getByRole("button", { name: "Add answer: shipping to uae" }));
    const form = await screen.findByRole("form", { name: "Add an FAQ" });
    expect(within(form).getByLabelText("Question")).toHaveValue("Do you ship to Dubai?");
    await user.type(within(form).getByLabelText("Answer"), "Yes, 5–7 business days.");
    await user.click(within(form).getByRole("button", { name: "Add" }));

    await waitFor(() =>
      expect(posted()).toEqual([
        { type: "faq", question: "Do you ship to Dubai?", body: "Yes, 5–7 business days.", gap_id: "g1" },
      ]),
    );
    await waitFor(() => expect(screen.queryByText("shipping to uae")).not.toBeInTheDocument());
    expect(await screen.findByText("No unanswered questions")).toBeInTheDocument();
  });

  it("Dismiss hides the topic", async () => {
    const user = userEvent.setup();
    const { calls } = setup({ gaps: [knowledgeGap(), knowledgeGap({ id: "g2", topic: "gift wrapping", occurrences: 3 })] });
    const card = await screen.findByRole("region", { name: "Questions the AI couldn't answer" });
    await user.click(within(card).getByRole("button", { name: "Dismiss: gift wrapping" }));
    await waitFor(() => expect(calls.some((c) => c.path === "/v1/w/w1/knowledge-gaps/g2/dismiss")).toBe(true));
    await waitFor(() => expect(within(card).queryByText("gift wrapping")).not.toBeInTheDocument());
    expect(within(card).getByText("shipping to uae")).toBeInTheDocument();
  });

  it("shows five, then Show all", async () => {
    const user = userEvent.setup();
    setup({
      gaps: Array.from({ length: 7 }, (_, i) => knowledgeGap({ id: `g${i}`, topic: `topic ${i}`, occurrences: 10 - i })),
    });
    const card = await screen.findByRole("region", { name: "Questions the AI couldn't answer" });
    expect(within(card).getAllByRole("listitem")).toHaveLength(5);
    await user.click(within(card).getByRole("button", { name: "Show all 7" }));
    expect(within(card).getAllByRole("listitem")).toHaveLength(7);
  });

  it("with none open, the card sits below the sources with its empty state", async () => {
    setup();
    const card = await screen.findByRole("region", { name: "Questions the AI couldn't answer" });
    expect(within(card).getByText("No unanswered questions")).toBeInTheDocument();
    expect(
      within(card).getByText("When customers ask something your knowledge doesn't cover, it shows up here."),
    ).toBeInTheDocument();
  });
});
