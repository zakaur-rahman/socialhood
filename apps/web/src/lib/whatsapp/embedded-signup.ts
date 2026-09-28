/**
 * Meta's Embedded Signup for WhatsApp (F-04, FR-CON-02). The Facebook JS SDK is loaded only
 * when the user clicks Connect WhatsApp on Settings → Connections (TR-FE-08, SEC CSP note).
 * FB.login returns an authorization code; the WABA and phone number ids arrive separately in
 * a "session info" window message. Both are needed before calling the API.
 *
 * Verify at build time (docs/verification.md item 14): the session-info event shape for the
 * configuration's Embedded Signup version.
 */

export const META_SDK_URL = "https://connect.facebook.net/en_US/sdk.js";
const GRAPH_VERSION = "v25.0"; // same as the API's META_GRAPH_VERSION

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

export type SignupResult =
  | { kind: "finished"; code: string; waba_id: string; phone_number_id: string }
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
  | { event: "finish"; waba_id: string; phone_number_id: string }
  | { event: "cancel" }
  | { event: "error"; message: string };

/** Reads Meta's WA_EMBEDDED_SIGNUP window message; null for anything else. */
export function parseSessionInfo(origin: string, data: unknown): SessionInfo | null {
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
  const p = payload as { type?: string; event?: string; data?: Record<string, unknown> };
  if (p.type !== "WA_EMBEDDED_SIGNUP") return null;
  const event = String(p.event ?? "").toUpperCase();
  if (event.startsWith("FINISH")) {
    const waba = p.data?.waba_id;
    const phone = p.data?.phone_number_id;
    if (typeof waba === "string" && typeof phone === "string" && waba && phone) {
      return { event: "finish", waba_id: waba, phone_number_id: phone };
    }
    return { event: "error", message: "Meta didn't say which number was chosen. Try again." };
  }
  if (event === "CANCEL") return { event: "cancel" };
  if (event === "ERROR") {
    const message = p.data?.error_message;
    return { event: "error", message: typeof message === "string" && message ? message : "Meta couldn't finish the signup." };
  }
  return null;
}

/**
 * Opens Meta's dialog and resolves once both the code (FB.login) and the session info
 * (message event) are in, or when the user closes the dialog.
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
      resolve(result);
    };
    const check = () => {
      if (info?.event === "error") return finish({ kind: "error", message: info.message });
      if (code && info?.event === "finish") {
        return finish({ kind: "finished", code, waba_id: info.waba_id, phone_number_id: info.phone_number_id });
      }
      if (loginDone && !code) return finish({ kind: "cancelled" });
      if (info?.event === "cancel" && loginDone) return finish({ kind: "cancelled" });
      if (loginDone && code && !info) {
        // The code came first; the session info should follow within moments.
        timer = window.setTimeout(
          () => finish({ kind: "error", message: "Meta didn't say which number was chosen. Try again." }),
          10_000,
        );
      }
    };
    const onMessage = (event: MessageEvent) => {
      const parsed = parseSessionInfo(event.origin, event.data);
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
