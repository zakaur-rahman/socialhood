import { describe, expect, it } from "vitest";

import type { WidgetSettings } from "@/lib/api/types";

import { isDirty, isLive, problem, toBody, toForm } from "./form";

const saved: WidgetSettings = {
  account_id: "a",
  widget_id: "wgt_abc123",
  enabled: true,
  allowed_domains: ["example.com"],
  accent_color: "#4467e6",
  title: "Chat with us",
  greeting: "Hi! How can we help?",
  position: "right",
  email_capture: "optional",
  email_prompt: "Leave your email.",
  marketing_consent_enabled: false,
  marketing_consent_text: "Email me offers.",
  show_branding: true,
  can_remove_branding: false,
  ai_mode: "suggest",
  script_url: "https://api.example.com/widget.js",
  embed_snippet: "<script></script>",
  conversations_today: 0,
  conversations_daily_limit: 50,
  updated_at: "2026-10-27T09:00:00Z",
};

describe("website chat form (GR-28)", () => {
  it("starts clean and sends nothing", () => {
    const form = toForm(saved);
    expect(isDirty(form, saved)).toBe(false);
    expect(toBody(form, saved)).toEqual({});
    expect(form.accent).toBe("#4467E6"); // compared in capitals, so a case difference is no change
  });

  it("sends only what changed, trimmed", () => {
    const form = { ...toForm(saved), title: "  Ask Maple  ", domains: ["example.com", "shop.example.com"], position: "left" as const };
    expect(toBody(form, saved)).toEqual({
      title: "Ask Maple",
      allowed_domains: ["example.com", "shop.example.com"],
      position: "left",
    });
    expect(isDirty(form, saved)).toBe(true);
  });

  it("a title with only spaces round-trips as unchanged text but blocks the save", () => {
    const form = { ...toForm(saved), title: "   " };
    expect(problem(form)).toBe("Give the chat a title.");
  });

  it("names what is missing", () => {
    const base = toForm(saved);
    expect(problem(base)).toBeNull();
    expect(problem({ ...base, greeting: " " })).toBe("Write a greeting.");
    expect(problem({ ...base, emailPrompt: "" })).toBe("Write what the email form says.");
    expect(problem({ ...base, emailPrompt: "", emailCapture: "off" })).toBeNull(); // not asked, not needed
    expect(problem({ ...base, consentEnabled: true, consentText: "" })).toBe("Write the words next to the consent box.");
    expect(problem({ ...base, emailCapture: "off", consentEnabled: true, consentText: "" })).toBeNull();
  });

  it("is live only when it is on and has a site", () => {
    const base = toForm(saved);
    expect(isLive(base)).toBe(true);
    expect(isLive({ ...base, enabled: false })).toBe(false);
    expect(isLive({ ...base, domains: [] })).toBe(false);
  });

  it("sends the branding choice only when it changed", () => {
    const pro = { ...saved, can_remove_branding: true };
    expect(toBody({ ...toForm(pro), branding: false }, pro)).toEqual({ show_branding: false });
    expect(toBody(toForm(pro), pro)).toEqual({});
  });
});
