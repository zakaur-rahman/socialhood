/**
 * Meta's Embedded Signup for WhatsApp (F-04, FR-CON-02). The Facebook JS SDK is loaded only
 * when the user clicks Connect WhatsApp on Settings → Connections (TR-FE-08, SEC CSP note).
 * FB.login returns an authorization code; the WABA and phone number ids arrive separately in
 * a "session info" window message. The code is what matters: once it is in, the signup always
 * completes through the API, with whichever ids the session info gave. The API finds the rest
 * with the business token (FINISH_ONLY_WABA names no number; the message may not come at all).
 *
 * Verify at build time (docs/verification.md item 14): the session-info event shape for the
 * configuration's Embedded Signup version.
 */

export const META_SDK_URL = "https://connect.facebook.net/en_US/sdk.js";
const GRAPH_VERSION = "v25.0"; // same as the API's META_GRAPH_VERSION
/** How long to wait for the session info once the code is in, before going on without it. */
export const SESSION_INFO_WAIT_MS = 5_000;

type LoginResponse = { authResponse?: { code?: string } | null; status?: string };

export type FacebookSdk = {
  init: (options: { appId: string; autoLogAppEvents?: boolean; xfbml?: boolean; version: string }) => void;
  login: (callback: (response: LoginResponse) => void, options: Record<string, unknown>) => void;
};

declare global {
  interface Window {
    FB?: FacebookSdk;
    fbAsyncInit?: () => void;
  }
}

/** The ids Meta's session info named, when it did. */
export type SignupIds = { waba_id?: string; phone_number_id?: string };

export type SignupResult =
  | ({ kind: "finished"; code: string } & SignupIds)
  | { kind: "cancelled" }
  | { kind: "error"; message: string };

let sdk: Promise<FacebookSdk> | null = null;

export function loadFacebookSdk(appId: string): Promise<FacebookSdk> {
  if (typeof window === "undefined") return Promise.reject(new Error("No window"));
  if (window.FB) return Promise.resolve(window.FB);
  if (sdk) return sdk;
  sdk = new Promise<FacebookSdk>((resolve, reject) => {
    window.fbAsyncInit = () => {
      const fb = window.FB;
      if (!fb) return reject(new Error("Facebook's sign-in didn't load."));
      fb.init({ appId, autoLogAppEvents: true, xfbml: false, version: GRAPH_VERSION });
      resolve(fb);
    };
    const script = document.createElement("script");
    script.src = META_SDK_URL;
    script.async = true;
    script.defer = true;
    script.crossOrigin = "anonymous";
    script.onerror = () => {
      sdk = null;
      script.remove();
      reject(new Error("Facebook's sign-in didn't load. Check your connection and try again."));
    };
    document.body.appendChild(script);
  });
  return sdk;
}

type SessionInfo =
  | ({ event: "finish" } & SignupIds)
  | { event: "cancel" }
  | { event: "error"; message: string };

type SignupMessage = { name: string; data: Record<string, unknown> };

/** Meta's WA_EMBEDDED_SIGNUP window message from a facebook.com origin; null for anything else. */
function readSignupMessage(origin: string, data: unknown): SignupMessage | null {
  let host: string;
  try {
    host = new URL(origin).hostname;
  } catch {
    return null;
  }
  if (host !== "facebook.com" && !host.endsWith(".facebook.com")) return null;
  let payload: unknown = data;
  if (typeof data === "string") {
    try {
      payload = JSON.parse(data);
    } catch {
      return null;
    }
  }
  if (typeof payload !== "object" || payload === null) return null;
  const p = payload as { type?: unknown; event?: unknown; data?: unknown };
  if (p.type !== "WA_EMBEDDED_SIGNUP") return null;
  const fields = typeof p.data === "object" && p.data !== null ? (p.data as Record<string, unknown>) : {};
  return { name: String(p.event ?? "").toUpperCase(), data: fields };
}

function id(value: unknown): string | undefined {
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

/** Only the ids that are there, so an absent one is left out of the request. */
function presentIds(source: { waba_id?: unknown; phone_number_id?: unknown }): SignupIds {
  const ids: SignupIds = {};
  const waba = id(source.waba_id);
  const phone = id(source.phone_number_id);
  if (waba) ids.waba_id = waba;
  if (phone) ids.phone_number_id = phone;
  return ids;
}

/**
 * Every FINISH* event (FINISH, FINISH_ONLY_WABA, FINISH_WHATSAPP_BUSINESS_APP_ONBOARDING, …) is a
 * finish with whatever ids it carries; CANCEL and ERROR as before; anything else is ignored.
 */
function toSessionInfo({ name, data }: SignupMessage): SessionInfo | null {
  if (name.startsWith("FINISH")) return { event: "finish", ...presentIds(data) };
  if (name === "CANCEL") return { event: "cancel" };
  if (name === "ERROR") {
    const message = data.error_message;
    return { event: "error", message: typeof message === "string" && message ? message : "Meta couldn't finish the signup." };
  }
  return null;
}

/** Reads Meta's WA_EMBEDDED_SIGNUP window message; null for anything else. */
export function parseSessionInfo(origin: string, data: unknown): SessionInfo | null {
  const message = readSignupMessage(origin, data);
  return message && toSessionInfo(message);
}

/**
 * Development builds only: what Meta sent, to debug the flow in the console. Names, the login
 * status and whether a code came, never the code or a token.
 */
function diagnose(message: string, details: Record<string, unknown>): void {
  if (process.env.NODE_ENV === "production") return;
  console.info(`[whatsapp signup] ${message}`, details);
}

/**
 * Opens Meta's dialog and resolves once the code (FB.login) is in, with the session info's ids if
 * it came within SESSION_INFO_WAIT_MS of the code, or when the user closes the dialog.
 */
export function runEmbeddedSignup(fb: FacebookSdk, configId: string): Promise<SignupResult> {
  return new Promise((resolve) => {
    let code: string | null = null;
    let info: SessionInfo | null = null;
    let loginDone = false;
    let settled = false;
    let timer: number | undefined;

    const finish = (result: SignupResult) => {
      if (settled) return;
      settled = true;
      window.removeEventListener("message", onMessage);
      window.clearTimeout(timer);
      diagnose("result", { kind: result.kind });
      resolve(result);
    };
    const finished = (ids: SignupIds) => {
      if (code) finish({ kind: "finished", code, ...ids });
    };
    const check = () => {
      if (info?.event === "error") return finish({ kind: "error", message: info.message });
      if (info?.event === "cancel" && loginDone) return finish({ kind: "cancelled" });
      if (!loginDone) return;
      if (!code) return finish({ kind: "cancelled" }); // the dialog closed without a code
      if (info?.event === "finish") return finished(presentIds(info));
      // The code came first; the session info should follow within moments. Without it the API
      // finds the account and number itself.
      if (timer === undefined) {
        timer = window.setTimeout(() => {
          diagnose("no session info in time; completing with the code alone", {});
          finished({});
        }, SESSION_INFO_WAIT_MS);
      }
    };
    const onMessage = (event: MessageEvent) => {
      const message = readSignupMessage(event.origin, event.data);
      if (!message) return;
      diagnose("session info", {
        event: message.name,
        waba_id: "waba_id" in message.data,
        phone_number_id: "phone_number_id" in message.data,
      });
      const parsed = toSessionInfo(message);
      if (!parsed) return;
      info = parsed;
      check();
    };
    window.addEventListener("message", onMessage);

    // FB.login's callback must be a plain (non-async) function.
    fb.login(
      (response) => {
        loginDone = true;
        code = response.authResponse?.code ?? null;
        diagnose("FB.login", { status: response.status ?? null, code: Boolean(code) });
        check();
      },
      {
        config_id: configId,
        response_type: "code",
        override_default_response_type: true,
        extras: { setup: {}, sessionInfoVersion: "3" },
      },
    );
  });
}
