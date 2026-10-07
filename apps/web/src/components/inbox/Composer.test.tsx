import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Conversation, MediaAsset } from "@/lib/api/types";
import { resetInboxStore, useInboxStore } from "@/lib/inbox/store";
import { conversation, json, problem, renderWithApi, type Call } from "@/test/api";

import { Composer, type Uploader } from "./Composer";

const now = new Date("2026-09-28T12:00:00Z");

function renderComposer(overrides: Partial<Conversation> = {}, props: Partial<Parameters<typeof Composer>[0]> = {}) {
  const onSend = vi.fn();
  const onChooseTemplate = vi.fn();
  const view = renderWithApi(
    <Composer
      wid="w1"
      slug="maple"
      timeZone="Asia/Kolkata"
      conversation={conversation(overrides)}
      lastInboundAt="2026-09-26T10:00:00Z"
      now={now}
      onSend={onSend}
      scheduleOpen={false}
      onScheduleOpenChange={() => {}}
      onChooseTemplate={onChooseTemplate}
      canAttach
      {...props}
    />,
  );
  return { ...view, onSend, onChooseTemplate };
}

function textbox() {
  return screen.getByRole("textbox", { name: "Reply to Priya Nair" }) as HTMLTextAreaElement;
}

// jsdom has no layout: give the textarea a content height so autosize has something to measure.
let scrollHeight = 0;
beforeEach(() => {
  resetInboxStore();
  scrollHeight = 0;
  Object.defineProperty(HTMLTextAreaElement.prototype, "scrollHeight", {
    configurable: true,
    get: () => scrollHeight,
  });
});
afterEach(() => {
  delete (HTMLTextAreaElement.prototype as { scrollHeight?: number }).scrollHeight;
});

describe("Composer (UX-INB-07)", () => {
  it("sends on Enter, adds a line on Shift+Enter, and is disabled while empty", async () => {
    const user = userEvent.setup();
    const { onSend } = renderComposer();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    expect(textbox()).toHaveAttribute("placeholder", "Reply to Priya…");

    await user.type(textbox(), "Yes, we ship to Dubai");
    await user.keyboard("{Shift>}{Enter}{/Shift}");
    await user.type(textbox(), "5–7 days");
    expect(onSend).not.toHaveBeenCalled();
    expect(textbox().value).toBe("Yes, we ship to Dubai\n5–7 days");

    await user.keyboard("{Enter}");
    expect(onSend).toHaveBeenCalledWith({ text: "Yes, we ship to Dubai\n5–7 days", assets: [], humanAgent: false });
    expect(textbox().value).toBe("");
  });

  // UI-030: Send is the Button primitive (32 px, 40 px on coarse pointers). Empty, it is a disabled
  // secondary Button that keeps UX-INB-07's neutral look at full opacity (DESIGN_SYSTEM §8.3); with
  // something to send, the primary (gradient) Button with the scale-in.
  it("Send: neutral and disabled while empty, the primary Button once there is text", async () => {
    const user = userEvent.setup();
    renderComposer();
    const send = screen.getByRole("button", { name: "Send" });
    expect(send).toHaveAttribute("data-slot", "button");
    expect(send).toHaveAttribute("data-size", "default");
    expect(send).toHaveAttribute("data-variant", "secondary");
    expect(send).toHaveClass("bg-raised", "disabled:text-fg-disabled", "disabled:opacity-100", "pointer-coarse:min-h-10");
    expect(send).not.toHaveClass("disabled:opacity-50");

    await user.type(textbox(), "Yes");
    expect(send).toBeEnabled();
    expect(send).toHaveAttribute("data-variant", "default");
    expect(send).toHaveClass("bg-brand-gradient", "text-on-brand", "motion-safe:animate-in", "motion-safe:zoom-in-95");
    expect(send).not.toHaveClass("disabled:opacity-100");
  });

  it("the toolbar's icon buttons are the Button's icon size, with no touch patches", () => {
    renderComposer();
    for (const name of ["Attach files", "Add emoji", "Send a heart", "Schedule for later"]) {
      const tool = screen.getByRole("button", { name });
      expect(tool).toHaveAttribute("data-size", "icon");
      expect(tool.className).not.toMatch(/md:size-/);
    }
  });

  it("the reply box is 16 px on phones, where iOS zooms into smaller text (UI-ISS-017)", () => {
    renderComposer();
    expect(textbox()).toHaveClass("text-sm", "max-md:text-base", "focus-visible:outline-none");
  });

  it("grows with the text up to 160 px and resets its height after send", async () => {
    const user = userEvent.setup();
    renderComposer();
    scrollHeight = 120;
    await user.type(textbox(), "Line one");
    expect(textbox().style.height).toBe("120px");
    scrollHeight = 400;
    await user.type(textbox(), " and more");
    expect(textbox().style.height).toBe("160px");

    await user.keyboard("{Enter}");
    expect(textbox().style.height).toBe("");
  });

  it("keeps the draft per conversation in the store", async () => {
    const user = userEvent.setup();
    renderComposer();
    await user.type(textbox(), "Half a thought");
    expect(useInboxStore.getState().drafts).toEqual({ c1: "Half a thought" });
  });

  it("does not send on Enter while the schedule popover is open", async () => {
    const user = userEvent.setup();
    useInboxStore.getState().setDraft("c1", "Later");
    const { onSend } = renderComposer({}, { scheduleOpen: true });
    fireEvent.keyDown(textbox(), { key: "Enter" });
    expect(onSend).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(onSend).toHaveBeenCalledOnce();
  });

  it("Human Agent window: a note under the textarea, and the send is tagged", async () => {
    const user = userEvent.setup();
    const { onSend } = renderComposer({ reply_window: { state: "human_agent", closes_at: "2026-10-03T12:00:00Z" } });
    expect(screen.getByText("Replying with Human Agent tag. Window closes in 5d.")).toBeInTheDocument();
    await user.type(textbox(), "Hi{Enter}");
    expect(onSend).toHaveBeenCalledWith(expect.objectContaining({ humanAgent: true }));
  });

  it("Instagram window closed: no textarea, says when the customer last wrote", () => {
    renderComposer({ reply_window: { state: "closed", closes_at: null } });
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("You can reply after Priya messages again. Last message 2d ago.");
  });

  it("WhatsApp outside the window: template only", async () => {
    const user = userEvent.setup();
    const { onChooseTemplate } = renderComposer({ platform: "whatsapp", reply_window: { state: "template_only", closes_at: null } });
    expect(screen.getByRole("status")).toHaveTextContent(
      "The 24-hour window has closed. Send an approved template to restart the conversation.",
    );
    await user.click(screen.getByRole("button", { name: "Choose template" }));
    expect(onChooseTemplate).toHaveBeenCalledOnce();
  });

  it("account needs reconnecting: disabled with Reconnect", () => {
    renderComposer({ social_account: { id: "a1", username: "maple.bakery", display_name: null, status: "needs_reconnect" } });
    expect(screen.getByRole("status")).toHaveTextContent("@maple.bakery needs reconnecting before you can send from it.");
    expect(screen.getByRole("link", { name: "Reconnect" })).toHaveAttribute("href", "/w/maple/settings/connections");
  });

  it("uploads attachments with a progress ring; Send waits for them", async () => {
    const user = userEvent.setup();
    let finish: (asset: MediaAsset) => void = () => {};
    let progress: (fraction: number) => void = () => {};
    const upload: Uploader = (_file, options) => {
      progress = options.onProgress;
      return new Promise((resolve) => {
        finish = resolve;
      });
    };
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:preview");
    const revoke = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    const { onSend } = renderComposer({}, { upload });
    const file = new File(["x"], "dress.png", { type: "image/png" });
    await user.upload(screen.getByTestId("composer-file-input"), file);

    act(() => progress(0.4));
    expect(screen.getByRole("progressbar", { name: "Uploading" })).toHaveAttribute("aria-valuenow", "40");
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();

    const asset = { id: "asset-1", resource_type: "image", secure_url: "https://res.cloudinary.com/x.png", bytes: 1 } as MediaAsset;
    act(() => finish(asset));
    await waitFor(() => expect(screen.getByRole("button", { name: "Send" })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(onSend).toHaveBeenCalledWith({ text: "", assets: [asset], humanAgent: false });
    expect(screen.queryByRole("list", { name: "Attachments" })).not.toBeInTheDocument();
    expect(revoke).toHaveBeenCalledWith("blob:preview");
    vi.restoreAllMocks();
  });

  it("sends Instagram's heart sticker on its own", async () => {
    const user = userEvent.setup();
    const { onSend } = renderComposer({ platform: "instagram" });
    await user.type(textbox(), "Draft stays");
    await user.click(screen.getByRole("button", { name: "Send a heart" }));
    expect(onSend).toHaveBeenCalledWith({ heart: true, humanAgent: false });
    expect(textbox().value).toBe("Draft stays");
    expect(screen.queryByRole("button", { name: "Send a sticker" })).not.toBeInTheDocument();
  });

  it("uploads and sends a WhatsApp sticker", async () => {
    const user = userEvent.setup();
    const asset = { id: "sticker-1", resource_type: "image", secure_url: "https://res.cloudinary.com/s.webp", bytes: 40_000 } as MediaAsset;
    const upload = vi.fn<Uploader>().mockResolvedValue(asset);
    const { onSend } = renderComposer({ platform: "whatsapp" }, { upload });
    expect(screen.queryByRole("button", { name: "Send a heart" })).not.toBeInTheDocument();
    await user.upload(screen.getByTestId("composer-sticker-input"), new File(["x"], "wave.webp", { type: "image/webp" }));
    await waitFor(() => expect(onSend).toHaveBeenCalledWith({ sticker: asset, humanAgent: false }));
    expect(upload).toHaveBeenCalledOnce();
  });

  it("refuses a sticker that is too big before uploading", async () => {
    const upload = vi.fn<Uploader>();
    const { onSend } = renderComposer({ platform: "whatsapp" }, { upload });
    const big = new File([new Uint8Array(600 * 1024)], "big.webp", { type: "image/webp" });
    fireEvent.change(screen.getByTestId("composer-sticker-input"), { target: { files: [big] } });
    await waitFor(() => expect(upload).not.toHaveBeenCalled());
    expect(onSend).not.toHaveBeenCalled();
  });

  it("shows a failed upload with Retry, and removes it", async () => {
    const user = userEvent.setup();
    const upload = vi.fn<Uploader>().mockRejectedValueOnce(new Error("nope")).mockReturnValue(new Promise(() => {}));
    renderComposer({}, { upload });
    await user.upload(screen.getByTestId("composer-file-input"), new File(["x"], "look.jpg", { type: "image/jpeg" }));
    const retry = await screen.findByRole("button", { name: "Retry uploading look.jpg" });
    expect(screen.getByRole("listitem")).toHaveAttribute("data-status", "failed");
    await user.click(retry);
    expect(upload).toHaveBeenCalledTimes(2);
    expect(screen.getByRole("listitem")).toHaveAttribute("data-status", "uploading");
    await user.click(screen.getByRole("button", { name: "Remove look.jpg" }));
    expect(screen.queryByRole("list", { name: "Attachments" })).not.toBeInTheDocument();
  });

  it("refuses files the platform can't take", async () => {
    const user = userEvent.setup({ applyAccept: false });
    const upload = vi.fn<Uploader>();
    renderComposer({}, { upload });
    // Instagram takes PDFs but not Office documents.
    await user.upload(screen.getByTestId("composer-file-input"), new File(["x"], "menu.docx", { type: "" }));
    expect(upload).not.toHaveBeenCalled();
    expect(screen.queryByRole("list", { name: "Attachments" })).not.toBeInTheDocument();
  });
});

describe("Schedule popover (F-10)", () => {
  it("limits times to the window and schedules in the workspace timezone", async () => {
    const user = userEvent.setup();
    useInboxStore.getState().setDraft("c1", "Following up on your order");
    const posted: unknown[] = [];
    const onScheduleOpenChange = vi.fn();
    renderWithApi(
      <Composer
        wid="w1"
        slug="maple"
        timeZone="Asia/Kolkata"
        conversation={conversation({ reply_window: { state: "open", closes_at: "2026-09-28T18:00:00Z" } })}
        lastInboundAt={null}
        now={now}
        onSend={() => {}}
        scheduleOpen
        onScheduleOpenChange={onScheduleOpenChange}
        onChooseTemplate={() => {}}
        canAttach={false}
      />,
      {
        handlers: {
          "POST /v1/w/:wid/conversations/:id/scheduled-messages": (call) => {
            posted.push({ body: call.body, key: call.headers.get("Idempotency-Key") });
            return json(
              {
                id: "s1",
                conversation_id: "c1",
                text: "Following up on your order",
                attachment_asset_ids: [],
                send_at: (call.body as { send_at: string }).send_at,
                status: "scheduled",
                contact: { display_name: "Priya Nair" },
                platform: "instagram",
              },
              201,
            );
          },
        },
      },
    );
    // 18:00 UTC is 23:30 in Kolkata; the latest allowed time is 5 minutes earlier.
    expect(screen.getByText("Window closes Today 23:30")).toBeInTheDocument();

    const time = screen.getByLabelText("Time");
    expect(screen.getByLabelText("Date")).toHaveValue("2026-09-28");
    fireEvent.change(time, { target: { value: "23:45" } });
    await user.click(screen.getByRole("button", { name: "Schedule" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Pick a time before Today 23:25, when the reply window closes.");

    fireEvent.change(time, { target: { value: "17:30" } }); // 12:00 UTC: too soon
    await user.click(screen.getByRole("button", { name: "Schedule" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Pick a time at least 2 minutes from now.");

    fireEvent.change(time, { target: { value: "21:00" } });
    await user.click(screen.getByRole("button", { name: "Schedule" }));
    await waitFor(() => expect(onScheduleOpenChange).toHaveBeenCalledWith(false));
    expect(posted).toEqual([
      {
        body: { text: "Following up on your order", send_at: "2026-09-28T15:30:00.000Z", attachment_asset_ids: [] },
        key: expect.stringMatching(/^[0-9a-f-]{36}$/),
      },
    ]);
    expect(useInboxStore.getState().drafts).toEqual({});
  });
});

describe("AI Polish (C-063)", () => {
  function renderWithPolish(respond: (call: Call) => Response | Promise<Response>) {
    return renderWithApi(
      <Composer
        wid="w1"
        slug="maple"
        timeZone="Asia/Kolkata"
        conversation={conversation()}
        lastInboundAt="2026-09-28T11:55:00Z"
        now={now}
        onSend={vi.fn()}
        scheduleOpen={false}
        onScheduleOpenChange={() => {}}
        onChooseTemplate={() => {}}
        canAttach
      />,
      { handlers: { "POST /v1/w/:wid/conversations/:id/polish": respond } },
    );
  }

  it("is off while the reply is empty", async () => {
    const user = userEvent.setup();
    renderWithPolish(() => json({ text: "" }));
    const polish = screen.getByRole("button", { name: "AI Polish" });
    expect(polish).toBeDisabled();
    // An AI action on the soft Button (C-073), dimmed by the primitive's disabled rule, not greyed here.
    expect(polish).toHaveAttribute("data-variant", "soft");
    expect(polish).toHaveClass("bg-brand-soft", "text-brand-fg", "disabled:opacity-50");
    expect(polish.className).not.toMatch(/disabled:(border|text)-/);
    await user.type(textbox(), "   ");
    expect(polish).toBeDisabled();
    await user.type(textbox(), "hi");
    expect(polish).toBeEnabled();
  });

  // UI-030: a disabled control says why (DisabledReason), to keyboard, touch and screen reader users.
  it("says why it's off: a focusable reason while the reply is empty, none once there is text", async () => {
    const user = userEvent.setup();
    renderWithPolish(() => json({ text: "" }));
    const polish = screen.getByRole("button", { name: "AI Polish" });
    const reason = polish.closest('[data-slot="disabled-reason"]') as HTMLElement;
    expect(reason).toHaveAttribute("tabindex", "0");
    expect(reason).toHaveAccessibleDescription("Write a reply to polish");
    await user.type(textbox(), "hi");
    expect(reason).not.toHaveAttribute("tabindex");
    expect(reason).not.toHaveAttribute("aria-describedby");
    expect(polish).toHaveAttribute("title", "Fix grammar and clarity, in the same language (1 AI credit)");
  });

  it("replaces the reply with a spinner while it works, and Undo brings the original back", async () => {
    const user = userEvent.setup();
    let release: (response: Response) => void = () => {};
    const { calls } = renderWithPolish(() => new Promise<Response>((resolve) => (release = resolve)));
    await user.type(textbox(), "haan ji cake ready hai kal tak");

    await user.click(screen.getByRole("button", { name: "AI Polish" }));
    const busy = await screen.findByRole("button", { name: "Polishing…" });
    expect(busy).toBeDisabled();
    // The Spinner primitive: it spins only when motion is allowed (UI-030; was a bare animate-spin).
    expect(busy.querySelector('svg[data-slot="spinner"]')).toHaveClass("motion-safe:animate-spin");
    expect(calls.find((c) => c.path === "/v1/w/w1/conversations/c1/polish")?.body).toEqual({
      text: "haan ji cake ready hai kal tak",
    });

    await act(async () => release(json({ text: "Haan ji, cake kal tak ready ho jayega." })));
    await waitFor(() => expect(textbox()).toHaveValue("Haan ji, cake kal tak ready ho jayega."));
    expect(screen.getByRole("button", { name: "AI Polish" })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "Undo" }));
    expect(textbox()).toHaveValue("haan ji cake ready hai kal tak");
    expect(screen.queryByRole("button", { name: "Undo" })).not.toBeInTheDocument();
  });

  it("Undo goes once the member edits the polished reply", async () => {
    const user = userEvent.setup();
    renderWithPolish(() => json({ text: "Yes, we deliver on Sundays." }));
    await user.type(textbox(), "yes we deliver sunday");
    await user.click(screen.getByRole("button", { name: "AI Polish" }));
    await waitFor(() => expect(textbox()).toHaveValue("Yes, we deliver on Sundays."));
    expect(screen.getByRole("button", { name: "Undo" })).toBeInTheDocument();
    await user.type(textbox(), " See you!");
    expect(screen.queryByRole("button", { name: "Undo" })).not.toBeInTheDocument();
  });

  it("a failure keeps the reply as it was", async () => {
    const user = userEvent.setup();
    renderWithPolish(() => problem(503, "service_unavailable", "The AI couldn't polish this just now. Try again."));
    await user.type(textbox(), "yes we deliver sunday");
    await user.click(screen.getByRole("button", { name: "AI Polish" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "AI Polish" })).toBeEnabled());
    expect(textbox()).toHaveValue("yes we deliver sunday");
    expect(screen.queryByRole("button", { name: "Undo" })).not.toBeInTheDocument();
  });
});
