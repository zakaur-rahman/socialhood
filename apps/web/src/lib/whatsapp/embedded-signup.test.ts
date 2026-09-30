import { afterEach, describe, expect, it, vi } from "vitest";

import { parseSessionInfo, runEmbeddedSignup, SESSION_INFO_WAIT_MS, type FacebookSdk } from "./embedded-signup";

const finish = JSON.stringify({
  type: "WA_EMBEDDED_SIGNUP",
  event: "FINISH",
  data: { phone_number_id: "1098765", waba_id: "2045678", business_id: "33" },
  version: 3,
});
// The owner finished without adding a number: Meta names the account only.
const onlyWaba = JSON.stringify({
  type: "WA_EMBEDDED_SIGNUP",
  event: "FINISH_ONLY_WABA",
  data: { waba_id: "2045678", business_id: "33" },
  version: 3,
});
const CODE = "AQB-secret-code";

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("session info (F-04)", () => {
  it("reads the WABA and phone number ids from Meta's message", () => {
    expect(parseSessionInfo("https://www.facebook.com", finish)).toEqual({
      event: "finish",
      waba_id: "2045678",
      phone_number_id: "1098765",
    });
  });

  it("treats every FINISH variant as a finish with whatever ids it carries", () => {
    expect(parseSessionInfo("https://www.facebook.com", onlyWaba)).toStrictEqual({ event: "finish", waba_id: "2045678" });
    const coexistence = {
      type: "WA_EMBEDDED_SIGNUP",
      event: "FINISH_WHATSAPP_BUSINESS_APP_ONBOARDING",
      data: { waba_id: 2045678, phone_number_id: "1098765" },
    };
    // An object as well as a JSON string; a numeric id reads as its digits.
    expect(parseSessionInfo("https://business.facebook.com", coexistence)).toStrictEqual({
      event: "finish",
      waba_id: "2045678",
      phone_number_id: "1098765",
    });
    const bare = JSON.stringify({ type: "WA_EMBEDDED_SIGNUP", event: "FINISH_GRANT_ONLY_API_ACCESS" });
    expect(parseSessionInfo("https://www.facebook.com", bare)).toStrictEqual({ event: "finish" });
    const empty = JSON.stringify({ type: "WA_EMBEDDED_SIGNUP", event: "finish", data: { waba_id: "", phone_number_id: null } });
    expect(parseSessionInfo("https://www.facebook.com", empty)).toStrictEqual({ event: "finish" });
  });

  it("ignores other origins and other messages", () => {
    expect(parseSessionInfo("https://evil.example", finish)).toBeNull();
    expect(parseSessionInfo("https://facebook.com.evil.example", finish)).toBeNull();
    expect(parseSessionInfo("https://www.facebook.com", "not json")).toBeNull();
    expect(parseSessionInfo("https://www.facebook.com", JSON.stringify({ type: "OTHER" }))).toBeNull();
    const unknown = JSON.stringify({ type: "WA_EMBEDDED_SIGNUP", event: "PROGRESS", data: {} });
    expect(parseSessionInfo("https://www.facebook.com", unknown)).toBeNull();
  });

  it("reads cancel and error events", () => {
    const cancel = JSON.stringify({ type: "WA_EMBEDDED_SIGNUP", event: "CANCEL", data: { current_step: "PHONE_NUMBER" } });
    expect(parseSessionInfo("https://business.facebook.com", cancel)).toEqual({ event: "cancel" });
    const error = JSON.stringify({ type: "WA_EMBEDDED_SIGNUP", event: "ERROR", data: { error_message: "Number in use" } });
    expect(parseSessionInfo("https://www.facebook.com", error)).toEqual({ event: "error", message: "Number in use" });
  });
});

type Login = { authResponse?: { code?: string } | null; status?: string };

function fakeFacebook(onLogin: (callback: (response: Login) => void) => void): FacebookSdk {
  return { init: vi.fn(), login: vi.fn((callback) => onLogin(callback)) };
}

function postFromMeta(data: string) {
  window.dispatchEvent(new MessageEvent("message", { origin: "https://www.facebook.com", data }));
}

describe("runEmbeddedSignup", () => {
  it("waits for both the code and the session info, in either order", async () => {
    const fb = fakeFacebook((callback) => {
      postFromMeta(finish);
      callback({ authResponse: { code: CODE }, status: "connected" });
    });
    await expect(runEmbeddedSignup(fb, "cfg-1")).resolves.toEqual({
      kind: "finished",
      code: CODE,
      waba_id: "2045678",
      phone_number_id: "1098765",
    });
    expect(fb.login).toHaveBeenCalledWith(expect.any(Function), expect.objectContaining({ config_id: "cfg-1", response_type: "code" }));
  });

  it("the code first, then the session info", async () => {
    const fb = fakeFacebook((callback) => {
      callback({ authResponse: { code: CODE } });
      setTimeout(() => postFromMeta(finish), 5);
    });
    await expect(runEmbeddedSignup(fb, "cfg-1")).resolves.toMatchObject({ kind: "finished", waba_id: "2045678" });
  });

  it("FINISH_ONLY_WABA completes with the account alone; the API finds the number", async () => {
    const fb = fakeFacebook((callback) => {
      postFromMeta(onlyWaba);
      callback({ authResponse: { code: CODE } });
    });
    await expect(runEmbeddedSignup(fb, "cfg-1")).resolves.toStrictEqual({ kind: "finished", code: CODE, waba_id: "2045678" });
  });

  it("a code without session info still completes, after a short wait", async () => {
    vi.useFakeTimers();
    const fb = fakeFacebook((callback) => callback({ authResponse: { code: CODE }, status: "connected" }));
    let result: unknown = null;
    void runEmbeddedSignup(fb, "cfg-1").then((r) => (result = r));
    await vi.advanceTimersByTimeAsync(SESSION_INFO_WAIT_MS - 1);
    expect(result).toBeNull();
    await vi.advanceTimersByTimeAsync(1);
    expect(result).toStrictEqual({ kind: "finished", code: CODE });
  });

  it("session info arriving during the wait is used", async () => {
    vi.useFakeTimers();
    const fb = fakeFacebook((callback) => {
      callback({ authResponse: { code: CODE } });
      setTimeout(() => postFromMeta(onlyWaba), 3_000);
    });
    const pending = runEmbeddedSignup(fb, "cfg-1");
    await vi.advanceTimersByTimeAsync(3_000);
    await expect(pending).resolves.toStrictEqual({ kind: "finished", code: CODE, waba_id: "2045678" });
  });

  it("closing the dialog is a cancel, with no request", async () => {
    const fb = fakeFacebook((callback) => callback({ authResponse: null, status: "unknown" }));
    await expect(runEmbeddedSignup(fb, "cfg-1")).resolves.toEqual({ kind: "cancelled" });
  });

  it("an explicit CANCEL is a cancel even with a code", async () => {
    const fb = fakeFacebook((callback) => {
      callback({ authResponse: { code: CODE } });
      postFromMeta(JSON.stringify({ type: "WA_EMBEDDED_SIGNUP", event: "CANCEL", data: { current_step: "PHONE_NUMBER" } }));
    });
    await expect(runEmbeddedSignup(fb, "cfg-1")).resolves.toEqual({ kind: "cancelled" });
  });

  it("an ERROR event shows Meta's message", async () => {
    const fb = fakeFacebook((callback) => {
      postFromMeta(JSON.stringify({ type: "WA_EMBEDDED_SIGNUP", event: "ERROR", data: { error_message: "Number in use" } }));
      callback({ authResponse: { code: CODE } });
    });
    await expect(runEmbeddedSignup(fb, "cfg-1")).resolves.toEqual({ kind: "error", message: "Number in use" });
  });
});

describe("development diagnostics", () => {
  it("log the event names, the login status and whether a code came, never the code", async () => {
    vi.useFakeTimers();
    const info = vi.spyOn(console, "info").mockImplementation(() => {});
    const withInfo = fakeFacebook((callback) => {
      postFromMeta(onlyWaba);
      callback({ authResponse: { code: CODE }, status: "connected" });
    });
    await runEmbeddedSignup(withInfo, "cfg-1");
    const without = fakeFacebook((callback) => callback({ authResponse: { code: CODE }, status: "connected" }));
    const pending = runEmbeddedSignup(without, "cfg-1");
    await vi.advanceTimersByTimeAsync(SESSION_INFO_WAIT_MS);
    await pending;

    const logged = JSON.stringify(info.mock.calls);
    expect(logged).toContain("FINISH_ONLY_WABA");
    expect(logged).toContain('"status":"connected"');
    expect(logged).toContain('"code":true');
    expect(logged).not.toContain(CODE);
  });

  it("are silent in production builds", async () => {
    vi.stubEnv("NODE_ENV", "production");
    const info = vi.spyOn(console, "info").mockImplementation(() => {});
    const fb = fakeFacebook((callback) => {
      postFromMeta(finish);
      callback({ authResponse: { code: CODE }, status: "connected" });
    });
    await runEmbeddedSignup(fb, "cfg-1");
    vi.unstubAllEnvs();
    expect(info).not.toHaveBeenCalled();
  });
});
