import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it, vi } from "vitest";

import type { WidgetSettings, WidgetSettingsUpdate } from "@/lib/api/types";
import { json, problem, renderWithApi, workspace } from "@/test/api";

import { WidgetSettingsPage } from "./WidgetSettingsPage";

// Radix Select, ToggleGroup and Switch use pointer capture; jsdom has none (see ui/select.test.tsx).
beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.setPointerCapture ??= () => {};
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});

const SNIPPET = '<script src="https://api.example.com/widget.js" data-widget="wgt_abc123" async></script>';

function settings(overrides: Partial<WidgetSettings> = {}): WidgetSettings {
  return {
    account_id: "acct-web",
    widget_id: "wgt_abc123",
    enabled: true,
    allowed_domains: ["example.com"],
    accent_color: "#4467E6",
    title: "Chat with us",
    greeting: "Hi! How can we help?",
    position: "right",
    email_capture: "optional",
    email_prompt: "Leave your email so we can reply if you leave this page.",
    marketing_consent_enabled: false,
    marketing_consent_text: "Email me news and offers. You can unsubscribe at any time.",
    show_branding: true,
    can_remove_branding: false,
    ai_mode: "suggest",
    script_url: "https://api.example.com/widget.js",
    embed_snippet: SNIPPET,
    conversations_today: 3,
    conversations_daily_limit: 50,
    updated_at: "2026-10-27T09:00:00Z",
    ...overrides,
  };
}

type Handlers = NonNullable<Parameters<typeof renderWithApi>[1]>["handlers"];

function setup(data: WidgetSettings, handlers: Handlers = {}) {
  return renderWithApi(<WidgetSettingsPage />, {
    ws: workspace,
    handlers: { "GET /v1/w/:wid/widget": () => json(data), ...handlers },
  });
}

describe("WidgetSettingsPage (GR-28)", () => {
  it("shows the allowed sites, the embed code and today's chats", async () => {
    setup(settings());
    expect(await screen.findByRole("heading", { level: 1, name: "Website chat" })).toBeInTheDocument();
    const sites = await screen.findByRole("list", { name: "Allowed sites" });
    expect(within(sites).getByText("example.com")).toBeInTheDocument();
    expect(screen.getByText(SNIPPET)).toBeInTheDocument();
    expect(screen.getByText(/Chats started today: 3 of 50/)).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "Chat is on" })).toBeChecked();
    expect(screen.queryByRole("region", { name: "Save changes" })).toBeNull(); // nothing changed yet
  });

  it("copies the embed code", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    setup(settings());
    await user.click(await screen.findByRole("button", { name: "Copy code" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(SNIPPET));
  });

  it("says the chat shows nowhere until a site is added", async () => {
    setup(settings({ allowed_domains: [] }));
    expect(await screen.findByText(/No sites are allowed yet/)).toBeInTheDocument();
  });

  it("saves only what changed", async () => {
    const user = userEvent.setup();
    let sent: WidgetSettingsUpdate | undefined;
    setup(settings(), {
      "PUT /v1/w/:wid/widget": (call) => {
        sent = call.body as WidgetSettingsUpdate;
        return json(settings({ allowed_domains: ["example.com", "shop.example.com"] }));
      },
    });
    const field = await screen.findByRole("textbox", { name: /Sites that can show the chat/ });
    await user.type(field, "shop.example.com{Enter}");
    const bar = await screen.findByRole("region", { name: "Save changes" });
    expect(within(bar).getByText("Unsaved changes")).toBeInTheDocument();
    await user.click(within(bar).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(sent).toBeDefined());
    expect(sent).toEqual({ allowed_domains: ["example.com", "shop.example.com"] });
    await waitFor(() => expect(screen.queryByRole("region", { name: "Save changes" })).toBeNull());
  });

  it("shows the API's message under a site it refuses", async () => {
    const user = userEvent.setup();
    setup(settings(), {
      "PUT /v1/w/:wid/widget": () =>
        new Response(
          JSON.stringify({
            type: "about:blank",
            title: "The request is not valid",
            status: 422,
            code: "validation_error",
            errors: [{ field: "allowed_domains.1", message: "Enter a domain like example.com." }],
          }),
          { status: 422, headers: { "Content-Type": "application/problem+json" } },
        ),
    });
    await user.type(await screen.findByRole("textbox", { name: /Sites that can show the chat/ }), "not a domain{Enter}");
    await user.click(within(await screen.findByRole("region", { name: "Save changes" })).getByRole("button", { name: "Save" }));
    expect((await screen.findAllByText("Enter a domain like example.com.")).length).toBeGreaterThan(0);
  });

  it("changes the title and shows it in the preview", async () => {
    const user = userEvent.setup();
    setup(settings());
    const title = await screen.findByLabelText("Title");
    await user.clear(title);
    await user.type(title, "Ask Maple");
    expect(screen.getByText("Ask Maple")).toBeInTheDocument(); // the preview
    await user.click(screen.getByRole("button", { name: "Teal" }));
    expect(screen.getByRole("button", { name: "Teal" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Blue" })).toHaveAttribute("aria-pressed", "false");
  });

  it("will not save an empty title", async () => {
    const user = userEvent.setup();
    setup(settings());
    const title = await screen.findByLabelText("Title");
    await user.clear(title);
    expect(await screen.findByText("Give the chat a title.")).toBeInTheDocument();
    const bar = screen.getByRole("region", { name: "Save changes" });
    await user.click(within(bar).getByRole("button", { name: "Save" }));
    // The save is held back, so nothing was sent and the form stays dirty.
    expect(within(bar).getByText("Unsaved changes")).toBeInTheDocument();
  });

  it("asks for the email box's words only when it asks for an email", async () => {
    const user = userEvent.setup();
    setup(settings());
    expect(await screen.findByLabelText("What the email box says")).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: "Don't ask" }));
    expect(screen.queryByLabelText("What the email box says")).toBeNull();
    expect(screen.queryByText("Ask for marketing consent")).toBeNull();
  });

  it("the consent words appear when marketing consent is asked", async () => {
    const user = userEvent.setup();
    setup(settings());
    expect(screen.queryByLabelText("Words next to the box")).toBeNull();
    await user.click(await screen.findByRole("switch", { name: "Ask for marketing consent" }));
    expect(screen.getByLabelText("Words next to the box")).toHaveValue(
      "Email me news and offers. You can unsubscribe at any time.",
    );
  });

  it("Free keeps the branding: the switch is locked and says why", async () => {
    setup(settings());
    const branding = await screen.findByRole("switch", { name: /Powered by Social Hood/ });
    expect(branding).toBeChecked();
    expect(branding).toBeDisabled();
    expect(screen.getAllByText(/Turning it off is part of Pro/).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "See plans" })).toBeInTheDocument();
  });

  it("Pro can turn the branding off", async () => {
    const user = userEvent.setup();
    let sent: WidgetSettingsUpdate | undefined;
    setup(settings({ can_remove_branding: true }), {
      "PUT /v1/w/:wid/widget": (call) => {
        sent = call.body as WidgetSettingsUpdate;
        return json(settings({ can_remove_branding: true, show_branding: false }));
      },
    });
    const branding = await screen.findByRole("switch", { name: /Powered by Social Hood/ });
    expect(branding).toBeEnabled();
    await user.click(branding);
    await user.click(within(await screen.findByRole("region", { name: "Save changes" })).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(sent).toEqual({ show_branding: false }));
  });

  it("links to the AI settings for the chat's AI mode", async () => {
    setup(settings({ ai_mode: "auto" }));
    const link = await screen.findByRole("link", { name: "AI rules and takeover" });
    expect(link).toHaveAttribute("href", `/w/${workspace.slug}/settings/ai`);
    expect(screen.getByText("Auto")).toBeInTheDocument();
  });

  it("shows an error with a retry when the settings can't load", async () => {
    setup(settings(), { "GET /v1/w/:wid/widget": () => problem(500, "internal", "Something went wrong") });
    expect(await screen.findByRole("button", { name: /try again|retry/i })).toBeInTheDocument();
  });
});
