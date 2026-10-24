import type { WidgetEmailCapture, WidgetPosition, WidgetSettings, WidgetSettingsUpdate } from "@/lib/api/types";

/** Settings → Website chat (GR-28): the form's values, and how they turn into a save. */
export type WidgetForm = {
  enabled: boolean;
  domains: string[];
  accent: string;
  title: string;
  greeting: string;
  position: WidgetPosition;
  emailCapture: WidgetEmailCapture;
  emailPrompt: string;
  consentEnabled: boolean;
  consentText: string;
  branding: boolean;
};

export const TITLE_MAX = 40;
export const GREETING_MAX = 300;
export const EMAIL_PROMPT_MAX = 200;
export const CONSENT_TEXT_MAX = 300;
export const DOMAINS_MAX = 20;
export const DOMAIN_MAX_CHARS = 253;

export const EMAIL_CAPTURE_LABEL: Record<WidgetEmailCapture, string> = {
  off: "Don't ask",
  optional: "After the first message",
  required: "Before the first message",
};

export function toForm(s: WidgetSettings): WidgetForm {
  return {
    enabled: s.enabled,
    domains: [...s.allowed_domains],
    accent: s.accent_color.toUpperCase(),
    title: s.title,
    greeting: s.greeting,
    position: s.position,
    emailCapture: s.email_capture,
    emailPrompt: s.email_prompt,
    consentEnabled: s.marketing_consent_enabled,
    consentText: s.marketing_consent_text,
    branding: s.show_branding,
  };
}

/** The settings the form would save, only those that changed; empty when nothing did. */
export function toBody(form: WidgetForm, saved: WidgetSettings): WidgetSettingsUpdate {
  const before = toForm(saved);
  const body: WidgetSettingsUpdate = {};
  if (form.enabled !== before.enabled) body.enabled = form.enabled;
  if (JSON.stringify(form.domains) !== JSON.stringify(before.domains)) body.allowed_domains = form.domains;
  if (form.accent !== before.accent) body.accent_color = form.accent;
  if (form.title.trim() !== before.title) body.title = form.title.trim();
  if (form.greeting.trim() !== before.greeting) body.greeting = form.greeting.trim();
  if (form.position !== before.position) body.position = form.position;
  if (form.emailCapture !== before.emailCapture) body.email_capture = form.emailCapture;
  if (form.emailPrompt.trim() !== before.emailPrompt) body.email_prompt = form.emailPrompt.trim();
  if (form.consentEnabled !== before.consentEnabled) body.marketing_consent_enabled = form.consentEnabled;
  if (form.consentText.trim() !== before.consentText) body.marketing_consent_text = form.consentText.trim();
  if (form.branding !== before.branding) body.show_branding = form.branding;
  return body;
}

export function isDirty(form: WidgetForm, saved: WidgetSettings): boolean {
  return Object.keys(toBody(form, saved)).length > 0;
}

/** Why the form can't be saved yet, in a sentence; null when it can. */
export function problem(form: WidgetForm): string | null {
  if (!form.title.trim()) return "Give the chat a title.";
  if (!form.greeting.trim()) return "Write a greeting.";
  if (form.emailCapture !== "off" && !form.emailPrompt.trim()) return "Write what the email form says.";
  if (form.emailCapture !== "off" && form.consentEnabled && !form.consentText.trim()) {
    return "Write the words next to the consent box.";
  }
  return null;
}

/** Whether a visitor can see the chat anywhere: it is on and at least one site is allowed. */
export function isLive(form: WidgetForm): boolean {
  return form.enabled && form.domains.length > 0;
}
