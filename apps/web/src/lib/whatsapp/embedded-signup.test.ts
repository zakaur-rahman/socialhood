import { describe, expect, it, vi } from "vitest";

import { parseSessionInfo, runEmbeddedSignup, type FacebookSdk } from "./embedded-signup";

const finish = JSON.stringify({
  type: "WA_EMBEDDED_SIGNUP",
  event: "FINISH",
  data: { phone_number_id: "1098765", waba_id: "2045678", business_id: "33" },
  version: 3,
});

describe("session info (F-04)", () => {
  it("reads the WABA and phone number ids from Meta's message", () => {
    expect(parseSessionInfo("https://www.facebook.com", finish)).toEqual({
      event: "finish",
      waba_id: "2045678",
      phone_number_id: "1098765",
    });
  });

  it("ignores other origins and other messages", () => {
    expect(parseSessionInfo("https://evil.example", finish)).toBeNull();
    expect(parseSessionInfo("https://facebook.com.evil.example", finish)).toBeNull();
    expect(parseSessionInfo("https://www.facebook.com", "not json")).toBeNull();
    expect(parseSessionInfo("https://www.facebook.com", JSON.stringify({ type: "OTHER" }))).toBeNull();
  });

  it("reads cancel and error events", () => {
    const cancel = JSON.stringify({ type: "WA_EMBEDDED_SIGNUP", event: "CANCEL", data: { current_step: "PHONE_NUMBER" } });
    expect(parseSessionInfo("https://business.facebook.com", cancel)).toEqual({ event: "cancel" });
    const error = JSON.stringify({ type: "WA_EMBEDDED_SIGNUP", event: "ERROR", data: { error_message: "Number in use" } });
    expect(parseSessionInfo("https://www.facebook.com", error)).toEqual({ event: "error", message: "Number in use" });
  });
});

function fakeFacebook(onLogin: (callback: (response: { authResponse?: { code?: string } | null }) => void) => void): FacebookSdk {
  return { init: vi.fn(), login: vi.fn((callback) => onLogin(callback)) };
}

function postFromMeta(data: string) {
  window.dispatchEvent(new MessageEvent("message", { origin: "https://www.facebook.com", data }));
}

describe("runEmbeddedSignup", () => {
  it("waits for both the code and the session info, in either order", async () => {
    const fb = fakeFacebook((callback) => {
      postFromMeta(finish);
      callback({ authResponse: { code: "AQB-code" } });
    });
    await expect(runEmbeddedSignup(fb, "cfg-1")).resolves.toEqual({
      kind: "finished",
      code: "AQB-code",
      waba_id: "2045678",
      phone_number_id: "1098765",
    });
    expect(fb.login).toHaveBeenCalledWith(expect.any(Function), expect.objectContaining({ config_id: "cfg-1", response_type: "code" }));
  });

  it("the code first, then the session info", async () => {
    const fb = fakeFacebook((callback) => {
      callback({ authResponse: { code: "AQB-code" } });
      setTimeout(() => postFromMeta(finish), 5);
    });
    await expect(runEmbeddedSignup(fb, "cfg-1")).resolves.toMatchObject({ kind: "finished", waba_id: "2045678" });
  });

  it("closing the dialog is a cancel, with no request", async () => {
    const fb = fakeFacebook((callback) => callback({ authResponse: null }));
    await expect(runEmbeddedSignup(fb, "cfg-1")).resolves.toEqual({ kind: "cancelled" });
  });
});
