import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Automation } from "@/lib/api/types";
import {
  DEFAULT_FOLLOW_NUDGE,
  DEFAULT_OPENING_BUTTON,
  DEFAULT_OPENING_TEXT,
  toDefinition,
  toRequestBody,
} from "@/lib/automations/definition";
import { account, automation, json, problem, renderWithApi, type Call } from "@/test/api";

import { AutomationEditor } from "./AutomationEditor";

const nav = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn(), search: "" }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: nav.push, replace: nav.replace }),
  useSearchParams: () => new URLSearchParams(nav.search),
  useParams: () => ({ slug: "maple", id: "au1" }),
  usePathname: () => "/w/maple/automations/au1",
}));

type Put = { at: number; body: unknown };

function validation(errors: { field: string; message: string }[]): Response {
  return new Response(
    JSON.stringify({ type: "about:blank", title: "validation_error", status: 422, code: "validation_error", errors }),
    { status: 422, headers: { "Content-Type": "application/problem+json" } },
  );
}

function renderEditor({
  initial = automation(),
  put,
  activate,
  disclosure = null,
}: {
  initial?: Automation;
  put?: (call: Call, count: number) => Response | undefined;
  activate?: () => Response;
  disclosure?: string | null;
} = {}) {
  const puts: Put[] = [];
  let current = initial;
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
          automation_disclosure: disclosure,
        }),
      "GET /v1/w/:wid/social-accounts": () => json({ items: [account({ id: "a1", username: "maple.bakery" })] }),
      "GET /v1/w/:wid/posts": () => json({ items: [], next_cursor: null }),
      "GET /v1/w/:wid/automations/:id": () => json(current),
      "PUT /v1/w/:wid/automations/:id": (call: Call) => {
        puts.push({ at: Date.now(), body: call.body });
        const custom = put?.(call, puts.length);
        if (custom) return custom;
        current = { ...current, ...(call.body as Partial<Automation>) };
        return json(current);
      },
      "POST /v1/w/:wid/automations/:id/activate": () =>
        activate ? activate() : json((current = { ...current, status: "active", display_status: "active" })),
      "POST /v1/w/:wid/automations/:id/pause": () =>
        json((current = { ...current, status: "paused", display_status: "paused" })),
    },
  });
  return { ...view, puts };
}

const saveStatus = () => screen.getByTestId("save-status");
const step = (id: string) => document.getElementById(`step-${id}`) as HTMLElement;

beforeEach(() => {
  nav.push.mockReset();
  nav.replace.mockReset();
  nav.search = "";
});

describe("AutomationEditor autosave (F-11)", () => {
  it("saves the whole definition once, 1 s after the last edit, and says Saving… until the API confirms", async () => {
    const user = userEvent.setup();
    const { puts } = renderEditor();
    const name = await screen.findByRole("textbox", { name: "Automation name" });
    expect(saveStatus()).toHaveTextContent("Saved");

    // The debounce restarts on every keystroke: time it from the last one.
    let lastInput = 0;
    name.addEventListener("input", () => (lastInput = Date.now()));
    await user.clear(name);
    await user.type(name, "Link DM");
    expect(saveStatus()).toHaveTextContent("Saving…");
    expect(puts).toHaveLength(0);

    await waitFor(() => expect(puts).toHaveLength(1), { timeout: 3000 });
    expect(puts[0].at - lastInput).toBeGreaterThanOrEqual(990);
    expect(puts[0].body).toEqual(toRequestBody({ ...toDefinition(automation()), name: "Link DM" }));
    await waitFor(() => expect(saveStatus()).toHaveTextContent("Saved"));
    expect(puts).toHaveLength(1);
  });

  it("says Not saved when the save fails, and Retry saves again", async () => {
    const user = userEvent.setup();
    const { puts } = renderEditor({ put: (_, count) => (count === 1 ? problem(500, "internal") : undefined) });
    const name = await screen.findByRole("textbox", { name: "Automation name" });
    await user.type(name, " 2");

    await waitFor(() => expect(saveStatus()).toHaveTextContent("Not saved"), { timeout: 3000 });
    expect(screen.getByRole("alert")).toHaveTextContent("Something went wrong on our side.");
    await user.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(saveStatus()).toHaveTextContent("Saved"));
    expect(puts).toHaveLength(2);
    expect(puts[1].body).toMatchObject({ name: "Comment LINK, DM the link 2" });
  });

  it("saves pending edits straight away when the editor is left", async () => {
    const user = userEvent.setup();
    const { puts, unmount } = renderEditor();
    const keywords = await screen.findByRole("textbox", { name: "Add a keyword" });
    await user.type(keywords, "price{Enter}");
    const leftAt = Date.now();
    unmount();
    await waitFor(() => expect(puts).toHaveLength(1));
    expect(puts[0].at - leftAt).toBeLessThan(900);
    expect(puts[0].body).toMatchObject({ keywords: ["link", "price"] });
  });
});

describe("AutomationEditor activation (FR-AUT-02)", () => {
  it("marks each step activation found a problem in, with its message, and focuses the first", async () => {
    const user = userEvent.setup();
    renderEditor({
      initial: automation({ keywords: [] }),
      activate: () =>
        validation([
          { field: "keywords", message: "Add at least one keyword." },
          { field: "message_buttons.0.url", message: "Use a full link that starts with https://" },
        ]),
    });
    await user.click(await screen.findByRole("button", { name: "Activate" }));

    await waitFor(() => expect(step("keywords")).toHaveAttribute("data-state", "error"));
    expect(step("then")).toHaveAttribute("data-state", "error");
    expect(step("when")).toHaveAttribute("data-state", "complete");
    expect(within(step("keywords")).getAllByText("Add at least one keyword.").length).toBeGreaterThan(0);
    expect(screen.getByRole("textbox", { name: "Button 1 link" })).toHaveAttribute("aria-invalid", "true");
    await waitFor(() => expect(step("keywords")).toHaveFocus());
    expect(screen.getByTestId("status-pill")).toHaveTextContent("Draft");

    // Fixing a field clears its step's error; the others stay.
    await user.type(screen.getByRole("textbox", { name: "Add a keyword" }), "link{Enter}");
    expect(step("keywords")).toHaveAttribute("data-state", "complete");
    expect(step("then")).toHaveAttribute("data-state", "error");
  });

  it("activates: the pill turns Active, the line animates, Pause replaces Activate", async () => {
    const user = userEvent.setup();
    renderEditor();
    await user.click(await screen.findByRole("button", { name: "Activate" }));
    await waitFor(() => expect(screen.getByTestId("status-pill")).toHaveTextContent("Active"));
    expect(screen.getByTestId("step-line")).toHaveAttribute("data-active", "true");
    expect(screen.getByTestId("step-line")).toHaveClass("automation-line-active");
    expect(screen.getByRole("button", { name: "Pause" })).toBeInTheDocument();
  });

  it("⋯ Delete is a destructive item; cancelling its confirmation puts focus back on ⋯", async () => {
    const user = userEvent.setup();
    renderEditor();
    const more = await screen.findByRole("button", { name: "More actions" });
    await user.click(more);
    const remove = await screen.findByRole("menuitem", { name: "Delete" });
    expect(remove).toHaveAttribute("data-variant", "destructive");
    await user.click(remove);
    const dialog = await screen.findByRole("alertdialog", { name: /^Delete / });
    expect(within(dialog).getByRole("button", { name: "Delete" })).toHaveAttribute("data-variant", "destructive");
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    await waitFor(() => expect(more).toHaveFocus());
  });

  it("saves pending edits before activating", async () => {
    const user = userEvent.setup();
    const { puts } = renderEditor();
    await user.type(await screen.findByRole("textbox", { name: "Add a keyword" }), "price{Enter}");
    await user.click(screen.getByRole("button", { name: "Activate" }));
    await waitFor(() => expect(screen.getByTestId("status-pill")).toHaveTextContent("Active"));
    expect(puts).toHaveLength(1);
  });
});

describe("AutomationEditor steps (UX-SCR-03)", () => {
  it("opens from the gallery on the first incomplete step", async () => {
    nav.search = "focus=first";
    renderEditor({ initial: automation({ keywords: [] }) });
    const keywords = await screen.findByRole("textbox", { name: "Add a keyword" });
    await waitFor(() => expect(keywords).toHaveFocus());
    expect(nav.replace).toHaveBeenCalledWith("/w/maple/automations/au1");
    expect(step("keywords")).toHaveAttribute("data-state", "incomplete");
    expect(step("when")).toHaveAttribute("data-state", "complete");
  });

  it("names the other automation when a keyword overlaps (FR-AUT-15)", async () => {
    renderEditor({
      initial: automation({
        overlaps: [{ keyword: "link", automation_id: "au9", automation_name: "Price list DM", this_runs_first: false }],
      }),
    });
    const warning = await screen.findByText("Price list DM");
    expect(warning.closest("li")).toHaveTextContent("“link” is also used by Price list DM, which runs first.");
  });

  it("previews the message as you type and counts bytes with the disclosure line", async () => {
    const user = userEvent.setup();
    renderEditor({ initial: automation({ message_text: "" }), disclosure: "Sent automatically" });
    const message = await screen.findByRole("textbox", { name: "Message" });
    await user.type(message, "Hi {{first_name}!");
    expect(screen.getByTestId("preview-message")).toHaveTextContent("Hi Priya!");
    // 30 (longest name) + "Hi !" (4) + "\n\n" (2) + "Sent automatically" (18)
    expect(screen.getByText("54 / 1,000 bytes")).toBeInTheDocument();
  });

  it("checks link button URLs as you type", async () => {
    const user = userEvent.setup();
    renderEditor();
    const url = await screen.findByRole("textbox", { name: "Button 1 link" });
    await user.clear(url);
    await user.type(url, "http://maple.example");
    expect(url).toHaveAttribute("aria-invalid", "true");
    expect(url).toHaveAccessibleDescription("Use a full link that starts with https://");
    await user.clear(url);
    await user.type(url, "https://maple.example");
    expect(url).not.toHaveAttribute("aria-invalid");
  });

  it("offers an image only for DM triggers: replies to comments are text and buttons", async () => {
    const user = userEvent.setup();
    renderEditor();
    await screen.findByRole("textbox", { name: "Message" });
    expect(screen.queryByRole("button", { name: "Add an image" })).toBeNull();
    expect(screen.getByText(/Replies to comments are text and link buttons/)).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: "DM keyword" }));
    expect(screen.getByRole("button", { name: "Add an image" })).toBeInTheDocument();
  });

  it("holds a message with link buttons to 640 characters", async () => {
    renderEditor({ initial: automation({ message_text: "a".repeat(641) }) });
    const message = await screen.findByRole("textbox", { name: "Message" });
    expect(message).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText(/With link buttons Instagram allows 640 characters/)).toBeInTheDocument();
  });

  it("shows only the steps the trigger uses", async () => {
    const user = userEvent.setup();
    renderEditor();
    await screen.findByRole("textbox", { name: "Automation name" });
    expect(step("posts")).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: "DM keyword" }));
    expect(step("posts")).toBeNull();
    expect(screen.queryByRole("group", { name: /Reply publicly/ })).toBeNull();
    await user.click(screen.getByRole("radio", { name: "Any comment" }));
    expect(step("keywords")).toBeNull();
    expect(step("posts")).toBeInTheDocument();
  });
});

const tapFirstSwitch = () => screen.queryByRole("switch", { name: /Tap first/ });
const NUDGE_SWITCH = "Suggest following to people who don't follow you yet";

describe("AutomationEditor tap first (FR-AUT-21)", () => {
  it("is recommended and explained; switching it on fills the default opening, frees the image and saves", async () => {
    const user = userEvent.setup();
    const { puts } = renderEditor();
    await screen.findByRole("textbox", { name: "Message" });
    const tap = tapFirstSwitch() as HTMLElement;
    expect(tap).toHaveAccessibleName("Tap first Recommended");
    expect(tap).toHaveAccessibleDescription(/^Instagram allows one text-only reply to a comment until the person answers\./);
    expect(tap).not.toBeChecked();
    expect(screen.queryByRole("textbox", { name: "Opening message" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Add an image" })).toBeNull();

    await user.click(tap);
    expect(tap).toBeChecked();
    expect(screen.getByRole("textbox", { name: "Opening message" })).toHaveValue(DEFAULT_OPENING_TEXT);
    expect(screen.getByRole("textbox", { name: "Button title" })).toHaveValue(DEFAULT_OPENING_BUTTON);
    const after = screen.getByRole("group", { name: "Sent after they tap or reply" });
    expect(after).toContainElement(screen.getByRole("textbox", { name: "Message" }));
    expect(within(after).getByRole("button", { name: "Add an image" })).toBeInTheDocument();
    expect(screen.queryByText(/Replies to comments are text and link buttons/)).toBeNull();

    await waitFor(() => expect(puts).toHaveLength(1), { timeout: 3000 });
    expect(puts[0].body).toMatchObject({
      confirm_first: true,
      opening_text: DEFAULT_OPENING_TEXT,
      opening_button: DEFAULT_OPENING_BUTTON,
    });
    expect(step("then")).toHaveAttribute("data-state", "complete");
  });

  it("counts the opening's bytes with the disclosure line and the button's 20 characters as you type", async () => {
    const user = userEvent.setup();
    renderEditor({
      initial: automation({ confirm_first: true, opening_text: "", opening_button: "" }),
      disclosure: "Sent automatically",
    });
    const opening = await screen.findByRole("textbox", { name: "Opening message" });
    expect(opening).toHaveAttribute("aria-invalid", "true");
    expect(opening).toHaveAccessibleDescription(/Write the opening message\.$/);
    expect(step("then")).toHaveAttribute("data-state", "incomplete");

    await user.type(opening, "Hi {{first_name}!");
    // 30 (longest name) + "Hi !" (4) + "\n\n" (2) + "Sent automatically" (18)
    expect(opening).toHaveAccessibleDescription(/54 \/ 1,000 bytes$/);
    expect(opening).not.toHaveAttribute("aria-invalid");
    expect(screen.getByTestId("preview-opening")).toHaveTextContent("Hi Priya!");

    const button = screen.getByRole("textbox", { name: "Button title" });
    expect(button).toHaveAttribute("aria-invalid", "true");
    expect(button).toHaveAccessibleDescription("Add a button title.");
    await user.type(button, "Send");
    expect(button).toHaveAccessibleDescription("4 / 20");
    expect(button).not.toHaveAttribute("aria-invalid");
    await user.type(button, " me the link, please");
    expect(button).toHaveValue("Send me the link, pl");
    expect(button).toHaveAccessibleDescription("20 / 20");
    expect(screen.getByTestId("preview-quick-reply")).toHaveTextContent("Send me the link, pl");
    expect(step("then")).toHaveAttribute("data-state", "complete");
  });

  it("marks an opening over 1,000 bytes, counting the disclosure line", async () => {
    renderEditor({
      initial: automation({ confirm_first: true, opening_text: "x".repeat(990), opening_button: "Send it" }),
      disclosure: "Sent automatically",
    });
    const opening = await screen.findByRole("textbox", { name: "Opening message" });
    // 990 bytes fit until the workspace's disclosure line loads and counts too.
    await waitFor(() => expect(opening).toHaveAttribute("aria-invalid", "true"));
    expect(opening).toHaveAccessibleDescription(/1,010 \/ 1,000 bytes Instagram allows 1,000 bytes in a DM/);
    expect(step("then")).toHaveAttribute("data-state", "incomplete");
  });

  it("is off: no image on a comment's reply, and an attached one says what to do", async () => {
    const user = userEvent.setup();
    renderEditor({ initial: automation({ message_media_asset_id: "ma1", message_media_url: null }) });
    expect(
      await screen.findByText("Replies to comments can't carry an image. Turn on Tap first, or remove the image."),
    ).toBeInTheDocument();
    expect(step("then")).toHaveAttribute("data-state", "incomplete");
    await user.click(tapFirstSwitch() as HTMLElement);
    expect(screen.queryByText(/can't carry an image/)).toBeNull();
    expect(step("then")).toHaveAttribute("data-state", "complete");
  });

  it("is hidden for DM triggers and Reply with AI, and starts on when a DM automation becomes a comment one", async () => {
    const user = userEvent.setup();
    renderEditor({ initial: automation({ trigger: "dm_keyword", public_reply_texts: [] }) });
    await screen.findByRole("textbox", { name: "Message" });
    expect(tapFirstSwitch()).toBeNull();

    await user.click(screen.getByRole("radio", { name: "Comment keyword" }));
    expect(tapFirstSwitch()).toBeChecked();
    expect(screen.getByRole("textbox", { name: "Opening message" })).toHaveValue(DEFAULT_OPENING_TEXT);

    await user.click(screen.getByRole("radio", { name: /AI reply/ }));
    expect(tapFirstSwitch()).toBeNull();
    expect(screen.queryByRole("switch", { name: NUDGE_SWITCH })).toBeNull();
  });
});

describe("AutomationEditor follow nudge (FR-AUT-22)", () => {
  it("says it is never a gate; on, it fills the example, counts to 300 and shows the View profile button", async () => {
    const user = userEvent.setup();
    const { puts } = renderEditor();
    const nudge = await screen.findByRole("switch", { name: NUDGE_SWITCH });
    expect(nudge).toHaveAccessibleDescription(
      "Sent after your message, only to people who don't follow you. Your message is never held back: Instagram's rules don't allow asking for a follow or a share in exchange for content.",
    );
    expect(nudge).not.toBeChecked();

    await user.click(nudge);
    const text = screen.getByRole("textbox", { name: "Follow message" });
    expect(text).toHaveValue(DEFAULT_FOLLOW_NUDGE);
    expect(text).toHaveAccessibleDescription(`${DEFAULT_FOLLOW_NUDGE.length} / 300`);
    expect(screen.getByTestId("nudge-button-preview")).toHaveTextContent("View profile");
    expect(screen.getByTestId("preview-nudge")).toHaveTextContent(DEFAULT_FOLLOW_NUDGE);

    await user.clear(text);
    expect(text).toHaveAttribute("aria-invalid", "true");
    expect(text).toHaveAccessibleDescription("0 / 300 Write the follow message.");
    expect(step("then")).toHaveAttribute("data-state", "incomplete");

    await user.click(text);
    await user.paste("a".repeat(310));
    expect(text).toHaveValue("a".repeat(300));
    expect(text).toHaveAccessibleDescription("300 / 300");
    expect(step("then")).toHaveAttribute("data-state", "complete");
    await waitFor(() => expect(puts.at(-1)?.body).toMatchObject({ follow_nudge: true, follow_nudge_text: "a".repeat(300) }), {
      timeout: 3000,
    });
  });

  it("shows for DM triggers too", async () => {
    renderEditor({ initial: automation({ trigger: "dm_keyword", public_reply_texts: [] }) });
    expect(await screen.findByRole("switch", { name: NUDGE_SWITCH })).toBeInTheDocument();
  });
});

describe("AutomationEditor activation errors for tap first and the nudge", () => {
  it("marks Then with the opening's, the button's and the nudge's problems; switches settle theirs", async () => {
    const user = userEvent.setup();
    renderEditor({
      initial: automation({
        confirm_first: true,
        opening_text: DEFAULT_OPENING_TEXT,
        opening_button: DEFAULT_OPENING_BUTTON,
        follow_nudge: true,
        follow_nudge_text: "Follow us",
      }),
      activate: () =>
        validation([
          { field: "opening_text", message: "Shorten the opening to 1,000 bytes." },
          { field: "opening_button", message: "Use 20 characters or fewer." },
          { field: "follow_nudge_text", message: "Use 300 characters or fewer." },
        ]),
    });
    await user.click(await screen.findByRole("button", { name: "Activate" }));

    await waitFor(() => expect(step("then")).toHaveAttribute("data-state", "error"));
    expect(step("keywords")).toHaveAttribute("data-state", "complete");
    const then = within(step("then"));
    expect(then.getAllByText("Shorten the opening to 1,000 bytes.").length).toBeGreaterThan(0);
    expect(then.getAllByText("Use 20 characters or fewer.").length).toBeGreaterThan(0);
    expect(then.getAllByText("Use 300 characters or fewer.").length).toBeGreaterThan(0);
    expect(screen.getByRole("textbox", { name: "Opening message" })).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("textbox", { name: "Button title" })).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("textbox", { name: "Follow message" })).toHaveAttribute("aria-invalid", "true");
    await waitFor(() => expect(step("then")).toHaveFocus());

    // Tap first off settles the opening's problems; the nudge's stays until its text changes.
    await user.click(tapFirstSwitch() as HTMLElement);
    expect(then.queryByText("Shorten the opening to 1,000 bytes.")).toBeNull();
    expect(then.queryByText("Use 20 characters or fewer.")).toBeNull();
    expect(step("then")).toHaveAttribute("data-state", "error");
    await user.type(screen.getByRole("textbox", { name: "Follow message" }), "!");
    expect(step("then")).toHaveAttribute("data-state", "complete");
  });
});
