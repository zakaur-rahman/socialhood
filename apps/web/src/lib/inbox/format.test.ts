import { describe, expect, it } from "vitest";

import { IDENTITIES } from "@/lib/ui/identity";

import { AVATAR_GRADIENTS, avatarGradient, contactName, previewPrefix, signalChip, timeLeft, windowChip } from "./format";

const now = new Date("2026-09-28T12:00:00Z");
const inHours = (h: number) => new Date(now.getTime() + h * 3_600_000).toISOString();

describe("row previews (UX-INB-04)", () => {
  it.each([
    ["human", "You: "],
    ["native_app", "You: "],
    ["ai_auto", "AI: "],
    ["automation", "Auto: "],
  ] as const)("outbound from %s starts %j", (source, prefix) => {
    expect(previewPrefix({ last_message_direction: "outbound", last_message_source: source })).toBe(prefix);
  });

  it("gives inbound previews no prefix", () => {
    expect(previewPrefix({ last_message_direction: "inbound", last_message_source: "customer" })).toBe("");
  });

  it("names a contact without a name by platform", () => {
    expect(contactName({ display_name: null, username: null }, "whatsapp")).toBe("WhatsApp user");
    expect(contactName({ display_name: " ", username: "priya" }, "instagram")).toBe("priya");
  });
});

describe("signal chips", () => {
  it.each([
    ["needs_you", "Needs you", "danger"],
    ["complaint", "Complaint", "danger"],
    ["lead", "Lead", "brand"],
    ["negative", "Negative", "danger"],
  ] as const)("%s → %s", (signal, label, tone) => {
    expect(signalChip({ signal, reply_window_closes_at: null }, now)).toEqual({ label, tone });
  });

  it("counts down Closing soon from the window", () => {
    expect(signalChip({ signal: "closing_soon", reply_window_closes_at: inHours(3) }, now)).toEqual({
      label: "Closing in 3h",
      tone: "warning",
    });
  });

  it("shows nothing without a signal", () => {
    expect(signalChip({ signal: null, reply_window_closes_at: null }, now)).toBeNull();
  });
});

describe("reply window chip (UX-INB-05)", () => {
  it("shows hours left, in warning under 2 h", () => {
    expect(windowChip({ state: "open", closes_at: inHours(18) }, now)).toEqual({ label: "Window: 18h left", tone: "neutral" });
    expect(windowChip({ state: "open", closes_at: inHours(1.5) }, now)).toEqual({ label: "Window: 1h left", tone: "warning" });
    expect(windowChip({ state: "open", closes_at: inHours(0.25) }, now).label).toBe("Window: 15m left");
  });

  it("covers Human Agent, closed and template only", () => {
    expect(windowChip({ state: "human_agent", closes_at: inHours(24 * 5) }, now).label).toBe("Human Agent: 5d left");
    expect(windowChip({ state: "closed" }, now)).toEqual({ label: "Window closed", tone: "danger" });
    expect(windowChip({ state: "template_only" }, now).label).toBe("Template only");
  });

  it("formats time left", () => {
    expect(timeLeft(inHours(-1), now)).toBe("0m");
    expect(timeLeft(inHours(47), now)).toBe("47h");
    expect(timeLeft(inHours(72), now)).toBe("3d");
  });
});

describe("avatar gradients", () => {
  it("picks the same pair for the same contact, from the identity palette (D-13)", () => {
    expect(avatarGradient("p1")).toBe(avatarGradient("p1"));
    expect(AVATAR_GRADIENTS).toEqual(IDENTITIES.map((i) => i.gradient));
    expect(AVATAR_GRADIENTS).toContain(avatarGradient("0d9f3c1e-8a55-4c3e-9c43-1f7a2e6b8d10"));
    const used = new Set(Array.from({ length: 60 }, (_, i) => avatarGradient(`contact-${i}`)));
    expect(used.size).toBe(AVATAR_GRADIENTS.length);
  });

  it("never paints a customer in a status or platform colour (UI-ISS-054)", () => {
    for (const gradient of AVATAR_GRADIENTS) {
      expect(gradient).not.toMatch(/success|warning|danger|instagram|whatsapp/);
    }
  });
});
